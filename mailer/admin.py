from django.contrib import admin
from .models import EmailTemplate, ResumeDocument, ApplicationLog

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject')

@admin.register(ResumeDocument)
class ResumeDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'file', 'uploaded_at')

@admin.register(ApplicationLog)
class ApplicationLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'status', 'sent_at', 'template', 'resume')
    readonly_fields = ('sent_at',)
