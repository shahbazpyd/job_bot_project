from django import forms
from django.contrib import admin
from .models import EmailTemplate, ResumeDocument, ApplicationLog, RecruiterLead, FollowUpSequence

class ResumeDocumentForm(forms.ModelForm):
    upload_file = forms.FileField(required=True, help_text="Upload your PDF resume here. It will be stored securely in the database.")

    class Meta:
        model = ResumeDocument
        fields = ('title',)

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded_file = self.cleaned_data.get('upload_file')
        if uploaded_file:
            instance.filename = uploaded_file.name
            instance.pdf_content = uploaded_file.read()
        if commit:
            instance.save()
        return instance

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject')

@admin.register(ResumeDocument)
class ResumeDocumentAdmin(admin.ModelAdmin):
    form = ResumeDocumentForm
    list_display = ('title', 'filename', 'uploaded_at')

@admin.register(ApplicationLog)
class ApplicationLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'status', 'sent_at', 'template', 'resume')
    readonly_fields = ('sent_at',)

@admin.register(RecruiterLead)
class RecruiterLeadAdmin(admin.ModelAdmin):
    list_display = ('email', 'company', 'role', 'location', 'experience_tag', 'is_verified', 'is_contacted', 'created_at')
    list_filter = ('location', 'experience_tag', 'is_verified', 'is_contacted')
    search_fields = ('email', 'company', 'role', 'name')

@admin.register(FollowUpSequence)
class FollowUpSequenceAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'company_name', 'role_title', 'step', 'status', 'scheduled_at', 'dispatched_at')
    list_filter = ('status', 'step')
    search_fields = ('recipient_email', 'company_name', 'role_title', 'candidate_name')
    readonly_fields = ('created_at',)
