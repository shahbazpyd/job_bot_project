from django.db import models

class EmailTemplate(models.Model):
    title = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()

    def __str__(self):
        return self.title

class ResumeDocument(models.Model):
    title = models.CharField(max_length=100, unique=True)
    file = models.FileField(upload_to='resumes/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class ApplicationLog(models.Model):
    recipient_email = models.EmailField()
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True)
    resume = models.ForeignKey(ResumeDocument, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.recipient_email} - {self.status} at {self.sent_at.strftime('%Y-%m-%d %H:%M')}"
