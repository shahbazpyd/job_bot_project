from django import forms
from django.contrib import admin
from .models import EmailTemplate, ResumeDocument, ApplicationLog

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
