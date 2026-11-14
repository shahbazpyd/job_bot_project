import uuid
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
    message_id = models.CharField(max_length=255, blank=True, default='', help_text="RFC 2822 Message-ID for email threading")
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, help_text="Unique UUIDv4 token for open and click telemetry")
    opened_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when email was first opened")
    open_count = models.PositiveIntegerField(default=0, help_text="Total number of times email was opened")
    clicked_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when a project link was first clicked")
    click_count = models.PositiveIntegerField(default=0, help_text="Total number of times links were clicked")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            # Accelerates deduplication queries: ApplicationLog.objects.filter(recipient_email=email, status='SUCCESS').exists()
            models.Index(fields=['recipient_email', 'status'], name='idx_applog_email_status'),
            # Accelerates daily quota calculations: ApplicationLog.objects.filter(sent_at__date=today).count()
            models.Index(fields=['sent_at'], name='idx_applog_sent_at'),
            # Accelerates open and click telemetry lookups
            models.Index(fields=['tracking_token'], name='idx_applog_tracking'),
            # Accelerates engagement-based filtering and analytics
            models.Index(fields=['opened_at', 'clicked_at'], name='idx_applog_engagement'),
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

    SOURCE_PLATFORM_CHOICES = [
        ('Hacker News', 'Hacker News'),
        ('Remotive', 'Remotive'),
        ('We Work Remotely', 'We Work Remotely'),
        ('Manual / Dork', 'Manual / Dork'),
        ('Other', 'Other'),
    ]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150, blank=True)
    company = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=50, choices=LOCATION_CHOICES, default='Remote')
    experience_tag = models.CharField(max_length=50, choices=EXPERIENCE_CHOICES, default='0-3 Years')
    source_platform = models.CharField(max_length=50, choices=SOURCE_PLATFORM_CHOICES, default='Hacker News')
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
            # Accelerates platform origin filtering
            models.Index(fields=['source_platform', 'is_contacted'], name='idx_lead_source'),
        ]

    def __str__(self):
        return f"{self.email} ({self.company or 'Unknown Co'} - {self.location} [{self.experience_tag}])"

class FollowUpSequence(models.Model):
    STATUS_CHOICES = [
        ('WAITING', 'Waiting Cadence'),
        ('READY', 'Ready for Dispatch'),
        ('SENT', 'Follow-Up Dispatched'),
        ('REPLIED', 'Recruiter Replied / Halted'),
        ('CANCELLED', 'Manually Cancelled'),
    ]

    initial_log = models.ForeignKey(
        ApplicationLog, 
        on_delete=models.CASCADE, 
        related_name='followup_sequences',
        help_text="Reference to the initial application dispatch log"
    )
    recipient_email = models.EmailField()
    candidate_name = models.CharField(max_length=150, blank=True)
    company_name = models.CharField(max_length=150, blank=True)
    role_title = models.CharField(max_length=150, blank=True)
    step = models.IntegerField(default=2, help_text="Cadence step number (2 = Day 4 Follow-Up)")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='WAITING')
    scheduled_at = models.DateTimeField(help_text="Exact timestamp when this follow-up becomes eligible for dispatch")
    dispatched_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when follow-up was actually sent")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_at']
        indexes = [
            # Accelerates querying due follow-ups: scheduled_at <= now() AND status in ('WAITING', 'READY')
            models.Index(fields=['status', 'scheduled_at'], name='idx_followup_status_sched'),
            # Accelerates looking up sequences for a specific recruiter
            models.Index(fields=['recipient_email'], name='idx_followup_recipient'),
        ]

    def __str__(self):
        return f"Follow-up to {self.recipient_email} [{self.status}] (Scheduled: {self.scheduled_at.strftime('%Y-%m-%d %H:%M')})"

    @property
    def is_due(self):
        from django.utils import timezone
        return self.status in ('WAITING', 'READY') and timezone.now() >= self.scheduled_at

    @property
    def days_until_due(self):
        from django.utils import timezone
        if timezone.now() >= self.scheduled_at:
            return 0
        delta = self.scheduled_at - timezone.now()
        return max(1, delta.days + (1 if delta.seconds > 0 else 0))

class JobApplication(models.Model):
    STAGE_CHOICES = [
        ('DISPATCHED', 'Dispatched'),
        ('OPENED', 'Email Opened'),
        ('FOLLOWUP_SENT', 'Follow-Up Sent'),
        ('INTERVIEWING', 'Interviewing'),
        ('OFFER', 'Offer Received'),
        ('ARCHIVED', 'Archived / Rejected'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    ]

    initial_log = models.OneToOneField(
        ApplicationLog,
        on_delete=models.CASCADE,
        related_name='job_application',
        null=True,
        blank=True,
        help_text="Reference to the initial application dispatch log"
    )
    company_name = models.CharField(max_length=150, blank=True)
    role_title = models.CharField(max_length=150, blank=True)
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=150, blank=True)
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default='DISPATCHED')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    interview_date = models.DateTimeField(null=True, blank=True, help_text="Scheduled interview date and time")
    salary_notes = models.CharField(max_length=255, blank=True, help_text="Target or offered compensation notes")
    notes = models.TextField(blank=True, help_text="Recruiter feedback, interview notes, or next steps")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            # Accelerates Kanban column filtering ordered by latest stage activity
            models.Index(fields=['stage', '-updated_at'], name='idx_app_stage_updated'),
            # Accelerates looking up applications by recruiter email
            models.Index(fields=['recipient_email'], name='idx_app_email'),
            # Accelerates filtering by application priority
            models.Index(fields=['priority'], name='idx_app_priority'),
        ]

    def __str__(self):
        return f"{self.company_name or 'Company'} - {self.role_title or 'Role'} ({self.stage})"

    @property
    def days_since_dispatch(self):
        from django.utils import timezone
        return max(0, (timezone.now() - self.created_at).days)

class InboundReply(models.Model):
    CLASSIFICATION_CHOICES = [
        ('INTERVIEW_REQUEST', 'Interview Request'),
        ('REJECTION', 'Rejection'),
        ('CLARIFICATION', 'Clarification / Questions'),
        ('AUTO_REPLY', 'Auto-Reply / Out of Office'),
        ('UNKNOWN', 'Unknown'),
    ]

    application = models.ForeignKey(
        JobApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inbound_replies',
        help_text="Matching JobApplication card"
    )
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=150, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    message_id = models.CharField(max_length=255, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=255, blank=True)
    classification = models.CharField(max_length=50, choices=CLASSIFICATION_CHOICES, default='UNKNOWN')
    summary = models.TextField(blank=True, help_text="Gemini synthesized summary of recruiter message")
    body_snippet = models.TextField(blank=True, help_text="Clean extracted email body excerpt")
    interview_time = models.DateTimeField(null=True, blank=True, help_text="Detected interview time if suggested by recruiter")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['sender_email'], name='idx_inbound_sender'),
            models.Index(fields=['classification'], name='idx_inbound_class'),
            models.Index(fields=['-received_at'], name='idx_inbound_received'),
        ]

    def __str__(self):
        return f"{self.sender_email} [{self.classification}] - {self.subject[:40]}"


