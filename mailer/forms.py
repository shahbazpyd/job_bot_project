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
        label="Or Upload CSV File (Emails in first column)",
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

        all_emails = set()

        # 1. Parse text area
        if recipient_emails_text:
            # Split by commas, newlines, or spaces
            raw_emails = re.split(r'[,\n\s]+', recipient_emails_text)
            for raw_email in raw_emails:
                email = raw_email.strip()
                if email:
                    all_emails.add(email)

        # 2. Parse CSV file
        if csv_file:
            try:
                # Read file as text
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                for row in reader:
                    if row:
                        # Assuming emails are in the first column
                        email = row[0].strip()
                        if email:
                            all_emails.add(email)
            except Exception as e:
                raise ValidationError(f"Error reading CSV file: {str(e)}")

        if not all_emails:
            raise ValidationError("You must provide at least one recipient email (via text or CSV).")

        # 3. Validate all collected emails
        valid_emails = []
        invalid_emails = []
        for email in all_emails:
            try:
                validate_email(email)
                valid_emails.append(email)
            except ValidationError:
                invalid_emails.append(email)

        if invalid_emails:
            raise ValidationError(f"Invalid email addresses found: {', '.join(invalid_emails)}")

        cleaned_data['parsed_emails'] = valid_emails
        return cleaned_data
