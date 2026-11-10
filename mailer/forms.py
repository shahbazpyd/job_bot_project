import csv
import io
import re
from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import EmailTemplate, ResumeDocument

class ApplicationDispatchForm(forms.Form):
    recipient_emails = forms.CharField(
        label="Recipient Emails (Comma or newline separated)",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'recruiter1@company.com, recruiter2@company.com\nrecruiter3@company.com'
        })
    )
    csv_file = forms.FileField(
        label="Or Upload CSV File (Optional columns: Email, Name, Company, Role)",
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.all(),
        empty_label="-- Select Email Template --",
        widget=forms.Select(attrs={'class': 'form-select', 'required': True})
    )
    resume = forms.ModelChoiceField(
        queryset=ResumeDocument.objects.all(),
        empty_label="-- Select Resume --",
        widget=forms.Select(attrs={'class': 'form-select', 'required': True})
    )

    def clean(self):
        cleaned_data = super().clean()
        recipient_emails_text = cleaned_data.get('recipient_emails', '')
        csv_file = cleaned_data.get('csv_file')

        # We store recipients as dict: {email: {'email': ..., 'name': ..., 'company': ..., 'role': ...}}
        recipients_map = {}

        # 1. Parse text area (plain emails)
        if recipient_emails_text:
            # Split by commas, newlines, or spaces
            raw_emails = re.split(r'[,\n\s]+', recipient_emails_text)
            for raw_email in raw_emails:
                email = raw_email.strip()
                if email and email not in recipients_map:
                    recipients_map[email] = {
                        'email': email,
                        'name': '',
                        'company': '',
                        'role': ''
                    }

        # 2. Parse CSV file with header detection
        if csv_file:
            try:
                decoded_file = csv_file.read().decode('utf-8-sig')  # utf-8-sig handles UTF-8 with BOM
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                rows = [row for row in reader if any(field.strip() for field in row)]

                if rows:
                    first_row = [cell.strip().lower() for cell in rows[0]]
                    
                    # Detect if first row is a header row
                    email_keywords = {'email', 'e-mail', 'mail', 'recipient'}
                    name_keywords = {'name', 'recruiter', 'recruiter name', 'hiring manager', 'contact'}
                    company_keywords = {'company', 'company name', 'organization', 'firm'}
                    role_keywords = {'role', 'position', 'job title', 'title', 'job'}

                    email_col = None
                    name_col = None
                    company_col = None
                    role_col = None

                    for idx, cell in enumerate(first_row):
                        if cell in email_keywords and email_col is None:
                            email_col = idx
                        elif cell in name_keywords and name_col is None:
                            name_col = idx
                        elif cell in company_keywords and company_col is None:
                            company_col = idx
                        elif cell in role_keywords and role_col is None:
                            role_col = idx

                    # If header detected, start data rows from index 1, else from index 0 (default col 0 as email)
                    if email_col is not None:
                        data_rows = rows[1:]
                    else:
                        email_col = 0
                        data_rows = rows

                    for row in data_rows:
                        if len(row) > email_col:
                            email = row[email_col].strip()
                            if email:
                                name = row[name_col].strip() if (name_col is not None and len(row) > name_col) else ''
                                company = row[company_col].strip() if (company_col is not None and len(row) > company_col) else ''
                                role = row[role_col].strip() if (role_col is not None and len(row) > role_col) else ''

                                recipients_map[email] = {
                                    'email': email,
                                    'name': name,
                                    'company': company,
                                    'role': role
                                }
            except Exception as e:
                raise ValidationError(f"Error reading CSV file: {str(e)}")

        if not recipients_map:
            raise ValidationError("You must provide at least one recipient email (via text or CSV).")

        # 3. Validate all collected emails
        valid_recipients = []
        invalid_emails = []
        for email, recipient_data in recipients_map.items():
            try:
                validate_email(email)
                valid_recipients.append(recipient_data)
            except ValidationError:
                invalid_emails.append(email)

        if invalid_emails:
            raise ValidationError(f"Invalid email addresses found: {', '.join(invalid_emails)}")

        cleaned_data['parsed_recipients'] = valid_recipients
        cleaned_data['parsed_emails'] = [r['email'] for r in valid_recipients]
        return cleaned_data
