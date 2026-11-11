from django.db import models

class EmailTemplate(models.Model):
    title = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()

    def __str__(self):
        return self.title

class ResumeDocument(models.Model):
    title = models.CharField(max_length=100, unique=True)
    pdf_content = models.BinaryField()
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class ApplicationLog(models.Model):
    recipient_email = models.EmailField()
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True)
    resume = models.ForeignKey(ResumeDocument, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            # Accelerates deduplication queries: ApplicationLog.objects.filter(recipient_email=email, status='SUCCESS').exists()
            models.Index(fields=['recipient_email', 'status'], name='idx_applog_email_status'),
            # Accelerates daily quota calculations: ApplicationLog.objects.filter(sent_at__date=today).count()
            models.Index(fields=['sent_at'], name='idx_applog_sent_at'),
        ]

    def __str__(self):
        return f"{self.recipient_email} - {self.status} at {self.sent_at.strftime('%Y-%m-%d %H:%M')}"

class RecruiterLead(models.Model):
    LOCATION_CHOICES = [
        ('Gurugram', 'Gurugram / NCR'),
        ('Hyderabad', 'Hyderabad / Telangana'),
        ('Bengaluru', 'Bengaluru / Bangalore'),
        ('Pune', 'Pune'),
        ('Mumbai', 'Mumbai / MMR'),
        ('Remote', 'Remote (Pan-India)'),
        ('Pan-India', 'Pan-India (Other)'),
        ('Other', 'Other'),
    ]

    EXPERIENCE_CHOICES = [
        ('0-3 Years', '0-3 Years (Entry/Mid)'),
        ('3-5 Years', '3-5 Years (Mid-Senior)'),
        ('5+ Years', '5+ Years (Senior/Lead)'),
        ('Unspecified', 'Unspecified'),
    ]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150, blank=True)
    company = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=50, choices=LOCATION_CHOICES, default='Remote')
    experience_tag = models.CharField(max_length=50, choices=EXPERIENCE_CHOICES, default='0-3 Years')
    source_url = models.URLField(max_length=500, blank=True)
    is_verified = models.BooleanField(default=False, help_text="True if domain has active MX records")
    is_contacted = models.BooleanField(default=False, help_text="True if email dispatched successfully")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Accelerates lead filtering on dashboard by outreach status and targeted location
            models.Index(fields=['is_contacted', 'location'], name='idx_lead_contacted_loc'),
            # Accelerates candidate filtering by experience level (e.g. 0-3 YOE) and uncontacted status
            models.Index(fields=['experience_tag', 'is_contacted'], name='idx_lead_exp_contacted'),
            # Accelerates harvester chronology sorting
            models.Index(fields=['-created_at'], name='idx_lead_created_at'),
        ]

    def __str__(self):
        return f"{self.email} ({self.company or 'Unknown Co'} - {self.location} [{self.experience_tag}])"
