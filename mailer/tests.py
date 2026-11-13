"""
mailer/tests.py

Comprehensive Automated Test Suite for Job Application Dispatcher & Lead Harvester.
Covers:
  1. Form & Smart CSV Parser (Headers, BOM, Textarea, Validation)
  2. Template Variable Interpolation Engine
  3. DNS MX Deliverability Verifier
  4. Harvester Lead Extraction & Deduplication Pipeline
  5. Security, Retry Semantics & Media Streaming Access
"""
import io
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Template, Context
from django.utils import timezone
from django.core.management import call_command

from .models import EmailTemplate, ResumeDocument, ApplicationLog, RecruiterLead, FollowUpSequence, JobApplication
from .forms import ApplicationDispatchForm
from .services.verifier import verify_email_mx
from .services.harvester import (
    detect_location, 
    detect_experience, 
    extract_clean_domain,
    infer_recruiter_email,
    harvest_from_hacker_news,
    harvest_from_remotive,
    harvest_from_wwr,
    harvest_multi_platform,
    harvest_from_text_block, 
    process_and_save_leads
)
from .services.followup import (
    generate_rfc2822_message_id,
    schedule_followup_for_application,
    dispatch_single_followup,
    dispatch_due_followups,
    mark_as_replied,
    cancel_sequence,
    get_followup_queue_stats
)
from .services.ai_hook import (
    build_grounded_prompt,
    generate_personalized_hook,
    DEFAULT_CANDIDATE_HIGHLIGHTS
)
from .services.tracking import (
    TRANSPARENT_1PX_GIF,
    prepare_multipart_email_bodies,
    record_email_open,
    record_link_click,
    is_safe_redirect_url
)
from django_q.tasks import async_task
from django_q.models import Schedule
from .services.tasks import dispatch_applications_task, process_followups_scheduled_task, automated_daily_harvester_task
from .services.scheduler import (
    calculate_next_daily_run,
    get_or_create_daily_harvester_schedule,
    toggle_harvester_schedule,
    trigger_immediate_harvester_run,
    get_harvester_schedule_status,
    SCHEDULE_NAME
)
from .views import send_emails_in_background


class ApplicationDispatchFormTest(TestCase):
    """Unit tests for form parsing and CSV normalization."""

    def setUp(self):
        self.template = EmailTemplate.objects.create(
            title="Test Template",
            subject="Test Subject",
            body="Hello {{ name }}"
        )
        self.resume = ResumeDocument.objects.create(
            title="Test Resume",
            filename="test_resume.pdf",
            pdf_content=b"%PDF-1.4 mock pdf content"
        )

    def test_textarea_email_parsing(self):
        """Verify plain text input separated by commas and newlines is parsed correctly."""
        raw_input = "alice@example.com, bob@example.com\ncarol@example.com"
        form = ApplicationDispatchForm(data={
            'recipient_emails': raw_input,
            'template': self.template.id,
            'resume': self.resume.id
        })
        self.assertTrue(form.is_valid(), form.errors)
        parsed = form.cleaned_data['parsed_recipients']
        self.assertEqual(len(parsed), 3)
        emails = [r['email'] for r in parsed]
        self.assertIn("alice@example.com", emails)
        self.assertIn("bob@example.com", emails)
        self.assertIn("carol@example.com", emails)

    def test_csv_with_headers_parsing(self):
        """Verify CSV with standard headers extracts structured fields."""
        csv_content = (
            "Email,Name,Company,Role\n"
            "hr@acme.com,John Doe,Acme Corp,Python Developer\n"
            "talent@hooli.com,Jane Smith,Hooli,Full Stack Lead\n"
        ).encode('utf-8')
        uploaded_file = SimpleUploadedFile("recruiters.csv", csv_content, content_type="text/csv")

        form = ApplicationDispatchForm(
            data={'template': self.template.id, 'resume': self.resume.id},
            files={'csv_file': uploaded_file}
        )
        self.assertTrue(form.is_valid(), form.errors)
        parsed = form.cleaned_data['parsed_recipients']
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['name'], "John Doe")
        self.assertEqual(parsed[0]['company'], "Acme Corp")
        self.assertEqual(parsed[0]['role'], "Python Developer")

    def test_csv_headerless_parsing(self):
        """Verify headerless CSV defaults column 0 to email gracefully."""
        csv_content = (
            "dev1@test.com,Dev One\n"
            "dev2@test.com,Dev Two\n"
        ).encode('utf-8')
        uploaded_file = SimpleUploadedFile("raw.csv", csv_content, content_type="text/csv")

        form = ApplicationDispatchForm(
            data={'template': self.template.id, 'resume': self.resume.id},
            files={'csv_file': uploaded_file}
        )
        self.assertTrue(form.is_valid(), form.errors)
        parsed = form.cleaned_data['parsed_recipients']
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['email'], "dev1@test.com")

    def test_csv_utf8_bom_handling(self):
        """Verify UTF-8 files with Byte Order Mark (BOM) are parsed without encoding errors."""
        csv_content = "\ufeffEmail,Name\nbom@test.com,BOM User\n".encode('utf-8')
        uploaded_file = SimpleUploadedFile("bom.csv", csv_content, content_type="text/csv")

        form = ApplicationDispatchForm(
            data={'template': self.template.id, 'resume': self.resume.id},
            files={'csv_file': uploaded_file}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['parsed_recipients'][0]['email'], "bom@test.com")

    def test_invalid_email_rejection(self):
        """Verify malformed email strings fail form validation."""
        form = ApplicationDispatchForm(data={
            'recipient_emails': "invalid-email-address, valid@example.com",
            'template': self.template.id,
            'resume': self.resume.id
        })
        self.assertFalse(form.is_valid())
        self.assertIn("Invalid email addresses found", str(form.errors))


class TemplatePersonalizationTest(TestCase):
    """Unit tests for the template variable replacement engine."""

    def test_dynamic_variable_interpolation(self):
        """Verify {{ name }}, {{ company }}, and {{ role }} are interpolated per recipient."""
        template_text = "Hi {{ name }}, I am applying for the {{ role }} role at {{ company }}."
        context_data = {
            'name': 'Sarah Connor',
            'company': 'Cyberdyne',
            'role': 'Backend Engineer'
        }
        rendered = Template(template_text).render(Context(context_data))
        self.assertEqual(rendered, "Hi Sarah Connor, I am applying for the Backend Engineer role at Cyberdyne.")

    def test_fallback_defaults_when_empty(self):
        """Verify fallback defaults render cleanly when recipient attributes are missing."""
        template_text = "Hi {{ name|default:'Hiring Manager' }}, welcome to {{ company|default:'your team' }}."
        rendered = Template(template_text).render(Context({'name': '', 'company': ''}))
        self.assertEqual(rendered, "Hi Hiring Manager, welcome to your team.")


class DNSVerifierTest(TestCase):
    """Unit tests for RFC 5321 DNS MX pre-flight checks."""

    @patch('dns.resolver.Resolver.resolve')
    def test_active_mx_records_verified(self, mock_resolve):
        """Verify domain with active MX records returns True."""
        mock_resolve.return_value = [MagicMock(preference=10, exchange='mail.example.com')]
        is_valid, reason = verify_email_mx("recruiter@example.com")
        self.assertTrue(is_valid)
        self.assertIn("MX verified", reason)

    @patch('dns.resolver.Resolver.resolve')
    def test_nonexistent_domain_rejected(self, mock_resolve):
        """Verify non-existent domain returns False to prevent bounces."""
        import dns.resolver
        mock_resolve.side_effect = dns.resolver.NXDOMAIN()
        is_valid, reason = verify_email_mx("user@nonexistentdomainxyz123.com")
        self.assertFalse(is_valid)
        self.assertIn("no active mail exchange", reason)

    def test_invalid_syntax_short_circuits_before_dns(self):
        """Verify invalid syntax fails immediately without triggering network DNS."""
        is_valid, reason = verify_email_mx("not-an-email")
        self.assertFalse(is_valid)
        self.assertEqual(reason, "Invalid email syntax")


class HarvesterPipelineTest(TestCase):
    """Unit tests for lead scraping, location detection, and deduplication."""

    def test_location_detection(self):
        """Verify geographic locations are identified accurately."""
        self.assertEqual(detect_location("Looking for Python devs in Hyderabad / Telangana"), "Hyderabad")
        self.assertEqual(detect_location("Opening in Gurugram / Gurgaon office"), "Gurugram")
        self.assertEqual(detect_location("Opening in Bengaluru / Bangalore office"), "Bengaluru")
        self.assertEqual(detect_location("Software Engineer based in Pune"), "Pune")
        self.assertEqual(detect_location("Fintech company in Mumbai / MMR"), "Mumbai")
        self.assertEqual(detect_location("100% Remote Python role"), "Remote")
        self.assertEqual(detect_location("Multiple engineering positions across India"), "Pan-India")

    def test_experience_detection_heuristics(self):
        """Verify regex patterns classify 0-3 YOE early career and senior postings accurately."""
        self.assertEqual(detect_experience("Looking for a Python dev with 1-3 years experience"), "0-3 Years")
        self.assertEqual(detect_experience("Hiring freshers and junior developers for backend role"), "0-3 Years")
        self.assertEqual(detect_experience("Entry level Python developer / 0 to 2 YOE required"), "0-3 Years")
        self.assertEqual(detect_experience("Mid-level engineer with 3-5 years experience"), "3-5 Years")
        self.assertEqual(detect_experience("Senior Python engineer with 5+ years of experience"), "5+ Years")
        self.assertEqual(detect_experience("Lead software architect / 8 yrs yoe"), "5+ Years")

    def test_text_block_harvester_extraction(self):
        """Verify extraction of emails from raw recruiter posts."""
        raw_post = (
            "We are hiring Python developers! Send resume to hr@techcorp.com (Gurugram).\n"
            "Also hiring React devs at jobs@startup.io"
        )
        leads = harvest_from_text_block(raw_post, default_location="Gurugram")
        self.assertEqual(len(leads), 2)
        emails = [l['email'] for l in leads]
        self.assertIn("hr@techcorp.com", emails)
        self.assertIn("jobs@startup.io", emails)

    @patch('mailer.services.harvester.verify_email_mx')
    def test_lead_deduplication_pipeline(self, mock_verify):
        """Verify that already contacted or duplicate leads are skipped."""
        mock_verify.return_value = (True, "Mocked MX OK")

        # Mark an email as already contacted
        ApplicationLog.objects.create(recipient_email="already_contacted@test.com", status="SUCCESS")

        candidate_leads = [
            {'email': 'already_contacted@test.com', 'name': '', 'company': 'Corp A', 'role': 'Dev', 'location': 'Hyderabad'},
            {'email': 'new_lead@test.com', 'name': '', 'company': 'Corp B', 'role': 'Dev', 'location': 'Hyderabad'}
        ]

        stats = process_and_save_leads(candidate_leads)
        self.assertEqual(stats['saved'], 1)
        self.assertEqual(stats['skipped_duplicate'], 1)
        self.assertTrue(RecruiterLead.objects.filter(email='new_lead@test.com').exists())


class DispatchSecurityAndDeduplicationTest(TestCase):
    """Integration tests for view security, retry semantics, and media streaming."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="securepassword123")
        self.resume = ResumeDocument.objects.create(
            title="Shahbaz Alam Resume",
            filename="Shahbaz_Alam_Resume.pdf",
            pdf_content=b"%PDF-1.4 sample pdf content bytes"
        )
        self.template = EmailTemplate.objects.create(
            title="Outreach Template",
            subject="Job Inquiry",
            body="Hello from Job Bot"
        )

    def test_unauthenticated_access_redirects_to_login(self):
        """Verify protected views require active session authentication."""
        response_home = self.client.get(reverse('send_application'))
        self.assertEqual(response_home.status_code, 302)
        self.assertIn('/accounts/login/', response_home.url)

        response_media = self.client.get(reverse('serve_protected_document', args=[self.resume.id]))
        self.assertEqual(response_media.status_code, 302)

    def test_authenticated_media_streaming_by_primary_key(self):
        """Verify authenticated users receive 200 OK with PDF headers."""
        self.client.login(username="testuser", password="securepassword123")
        response = self.client.get(reverse('serve_protected_document', args=[self.resume.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])

    def test_nonexistent_resume_returns_404(self):
        """Verify querying non-existent resume ID returns 404 rather than unhandled exception."""
        self.client.login(username="testuser", password="securepassword123")
        response = self.client.get(reverse('serve_protected_document', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_retry_semantics_failed_emails_allowed(self):
        """Verify emails with FAILED status are NOT filtered out, allowing retries."""
        self.client.login(username="testuser", password="securepassword123")

        # Simulate prior failed send
        ApplicationLog.objects.create(recipient_email="retry_me@test.com", status="FAILED: SMTP timeout")

        # Check filter logic directly as in send_application_view
        parsed_emails = ["retry_me@test.com"]
        existing_successful = set(
            ApplicationLog.objects.filter(recipient_email__in=parsed_emails, status="SUCCESS").values_list('recipient_email', flat=True)
        )
        new_emails = [e for e in parsed_emails if e not in existing_successful]

        # Must allow retry_me@test.com to be sent
        self.assertEqual(new_emails, ["retry_me@test.com"])

    def test_successful_emails_skipped(self):
        """Verify emails with SUCCESS status are filtered out to prevent duplicate outreach."""
        ApplicationLog.objects.create(recipient_email="already_done@test.com", status="SUCCESS")

        parsed_emails = ["already_done@test.com"]
        existing_successful = set(
            ApplicationLog.objects.filter(recipient_email__in=parsed_emails, status="SUCCESS").values_list('recipient_email', flat=True)
        )
        new_emails = [e for e in parsed_emails if e not in existing_successful]

        self.assertEqual(new_emails, [])

    def test_transfer_selected_routes_pan_india_template(self):
        """Verify transferring Remote or Bengaluru leads pairs the Pan-India / Remote template."""
        self.client.login(username="testuser", password="securepassword123")
        pan_template = EmailTemplate.objects.create(
            title="Python Full Stack Outreach (Pan-India / Remote)",
            subject="Job Inquiry",
            body="Hello from Job Bot Pan-India"
        )
        lead = RecruiterLead.objects.create(
            email="recruiter.blr@innovate.in",
            company="Innovate Bangalore",
            role="Python Engineer",
            location="Bengaluru",
            experience_tag="0-3 Years",
            is_verified=True
        )

        response = self.client.post(reverse('lead_harvester'), {
            'action': 'transfer_selected',
            'selected_leads': [lead.id]
        })
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertEqual(session.get('prefill_template_id'), pan_template.id)
        self.assertIn("recruiter.blr@innovate.in", session.get('prefill_dispatch_emails', ''))


class FollowUpEngineTest(TestCase):
    """
    Unit & integration tests for Phase 8: Automated Follow-Up Engine.
    Covers:
      - RFC 2822 Message-ID generation and persistence.
      - Automated Day 4 FollowUpSequence creation on outreach.
      - RFC 2822 In-Reply-To and References conversation threading.
      - Recruiter reply safeguard / kill-switch mechanics.
      - Management command and web action handlers.
    """

    def setUp(self):
        self.template = EmailTemplate.objects.create(
            title="Python Full Stack Outreach (Gurugram)",
            subject="Application: {{ role }} - Shahbaz Alam",
            body="Hello {{ name }} at {{ company }}"
        )
        self.followup_template = EmailTemplate.objects.create(
            title="Python Full Stack Follow-Up (Day 4 Bump)",
            subject="Re: Application: {{ role }} - Shahbaz Alam",
            body="Hi {{ name }}, following up on my previous note regarding {{ company }}."
        )
        self.resume = ResumeDocument.objects.create(
            title="Shahbaz Alam - Python Full Stack Developer (Gurugram)",
            filename="Shahbaz_Alam_Resume_Gurugram.pdf",
            pdf_content=b"%PDF-1.4 Mock Resume Binary Content"
        )
        self.user = User.objects.create_user(username="testrunner", password="securepassword123")

    @patch('django.core.mail.message.EmailMessage.send')
    def test_followup_sequence_scheduled_on_initial_dispatch(self, mock_send):
        """Verify that initial dispatch generates RFC 2822 Message-ID and creates Day 4 FollowUpSequence."""
        mock_send.return_value = 1
        recipients = [{
            'email': 'hiring.lead@nextech.io',
            'name': 'Priya Sharma',
            'company': 'NexTech',
            'role': 'Backend Engineer'
        }]

        # Trigger background dispatch
        send_emails_in_background(recipients, self.template.id, self.resume.id)

        # Check ApplicationLog
        log_entry = ApplicationLog.objects.filter(recipient_email='hiring.lead@nextech.io').first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.status, "SUCCESS")
        self.assertTrue(log_entry.message_id.startswith("<"))
        self.assertTrue(log_entry.message_id.endswith("@jobbot.local>"))

        # Check FollowUpSequence
        sequence = FollowUpSequence.objects.filter(recipient_email='hiring.lead@nextech.io').first()
        self.assertIsNotNone(sequence)
        self.assertEqual(sequence.status, 'WAITING')
        self.assertEqual(sequence.candidate_name, 'Priya Sharma')
        self.assertEqual(sequence.company_name, 'NexTech')
        self.assertEqual(sequence.step, 2)
        # Scheduled time should be ~4 days after sent_at
        delta = sequence.scheduled_at - log_entry.sent_at
        self.assertAlmostEqual(delta.total_seconds(), 4 * 86400, delta=60)

    def test_rfc2822_threading_headers_on_followup_dispatch(self):
        """Verify that follow-up email injects In-Reply-To and References headers matching initial message_id."""
        parent_msg_id = "<parent_abc123@jobbot.local>"

        initial_log = ApplicationLog.objects.create(
            recipient_email="cto@startup.com",
            template=self.template,
            resume=self.resume,
            status="SUCCESS",
            message_id=parent_msg_id
        )

        # Create due sequence
        scheduled_past = timezone.now() - timedelta(days=5)
        sequence = FollowUpSequence.objects.create(
            initial_log=initial_log,
            recipient_email="cto@startup.com",
            candidate_name="Vikram Singh",
            company_name="StartupHub",
            role_title="Senior Python Dev",
            status="READY",
            scheduled_at=scheduled_past
        )

        mail.outbox.clear()
        result = dispatch_single_followup(sequence, force=True)

        self.assertTrue(result['success'], result.get('error'))
        self.assertEqual(len(mail.outbox), 1)
        dispatched_email = mail.outbox[0]

        # Verify RFC 2822 threading headers
        headers = dispatched_email.extra_headers
        self.assertEqual(headers.get('In-Reply-To'), parent_msg_id)
        self.assertEqual(headers.get('References'), parent_msg_id)
        self.assertTrue(headers.get('Message-ID').startswith("<"))
        self.assertNotEqual(headers.get('Message-ID'), parent_msg_id)
        self.assertTrue(dispatched_email.subject.startswith("Re:"))

        # Verify state machine transition
        sequence.refresh_from_db()
        self.assertEqual(sequence.status, 'SENT')
        self.assertIsNotNone(sequence.dispatched_at)

    def test_reply_safeguard_halts_sequence(self):
        """Verify that marking a sequence as REPLIED halts dispatch permanently."""
        initial_log = ApplicationLog.objects.create(
            recipient_email="lead@fintech.co",
            template=self.template,
            resume=self.resume,
            status="SUCCESS",
            message_id="<msg_fintech@jobbot.local>"
        )
        sequence = FollowUpSequence.objects.create(
            initial_log=initial_log,
            recipient_email="lead@fintech.co",
            candidate_name="Aman Verma",
            company_name="FinTech Co",
            status="WAITING",
            scheduled_at=timezone.now() - timedelta(days=1)
        )

        # Recruiter replies -> activate safeguard
        updated_seq = mark_as_replied(sequence.id)
        self.assertIsNotNone(updated_seq)
        self.assertEqual(updated_seq.status, 'REPLIED')

        # Attempt to dispatch
        res = dispatch_single_followup(updated_seq, force=False)
        self.assertFalse(res['success'])
        self.assertIn("not eligible", res['error'])

        # Verify queue stats reflect REPLIED
        stats = get_followup_queue_stats()
        self.assertEqual(stats['replied'], 1)

    @patch('django.core.mail.message.EmailMessage.send')
    def test_management_command_process_followups(self, mock_send):
        """Verify process_followups management command runs cleanly with --dry-run and batch execution."""
        mock_send.return_value = 1
        initial_log = ApplicationLog.objects.create(
            recipient_email="hr@cloudcorp.com",
            template=self.template,
            resume=self.resume,
            status="SUCCESS",
            message_id="<msg_cloud@jobbot.local>"
        )
        FollowUpSequence.objects.create(
            initial_log=initial_log,
            recipient_email="hr@cloudcorp.com",
            candidate_name="Simran Kaur",
            company_name="CloudCorp",
            status="READY",
            scheduled_at=timezone.now() - timedelta(hours=1)
        )

        # Test dry run
        out = io.StringIO()
        call_command('process_followups', dry_run=True, stdout=out)
        output_str = out.getvalue()
        self.assertIn("Found 1 sequence(s) eligible", output_str)
        self.assertIn("DRY-RUN MODE", output_str)

        # Test real run
        out_real = io.StringIO()
        call_command('process_followups', stdout=out_real)
        self.assertIn("Batch completed", out_real.getvalue())

    def test_followup_view_actions(self):
        """Verify web action view handles mark_replied, cancel, and unauthorized access."""
        # Unauthenticated request redirects
        res_unauth = self.client.post(reverse('followup_action'), {'action': 'send_due'})
        self.assertEqual(res_unauth.status_code, 302)
        self.assertIn('/accounts/login/', res_unauth.url)

        # Authenticated user
        self.client.login(username="testrunner", password="securepassword123")
        initial_log = ApplicationLog.objects.create(
            recipient_email="director@ai.org",
            template=self.template,
            resume=self.resume,
            status="SUCCESS",
            message_id="<msg_ai@jobbot.local>"
        )
        seq = FollowUpSequence.objects.create(
            initial_log=initial_log,
            recipient_email="director@ai.org",
            status="WAITING",
            scheduled_at=timezone.now() + timedelta(days=2)
        )

        # Post mark_replied action
        res = self.client.post(reverse('followup_action'), {
            'action': 'mark_replied',
            'sequence_id': seq.id
        })
        self.assertEqual(res.status_code, 302)
        seq.refresh_from_db()
        self.assertEqual(seq.status, 'REPLIED')


class GeminiAIHookGeneratorTest(TestCase):
    """
    Unit & integration tests for Phase 9: AI-Powered Dynamic Hook Generator (Gemini Integration).
    Covers:
      - Grounded prompt formulation with verified portfolio achievements.
      - Graceful zero-downtime fallback when GEMINI_API_KEY is unset or fails.
      - Mocked Gemini SDK response processing.
      - Decoupled RESTful AJAX endpoint authentication and JSON responses.
      - Template engine merge and dispatch with {{ custom_hook }}.
    """

    def setUp(self):
        self.template = EmailTemplate.objects.create(
            title="Test AI Hook Template",
            subject="Application: {{ role }} - Shahbaz Alam",
            body="Hello {{ name }},\n\n{{ custom_hook }}\n\nBest, Shahbaz"
        )
        self.resume = ResumeDocument.objects.create(
            title="Test AI Resume",
            filename="Test_AI_Resume.pdf",
            pdf_content=b"%PDF-1.4 Mock Binary"
        )
        self.user = User.objects.create_user(username="aitestuser", password="securepassword123")

    def test_build_grounded_prompt_includes_verified_projects(self):
        """Verify prompt grounds Gemini in Shahbaz's real projects (ssenterprisesncr.in, GISFY)."""
        prompt = build_grounded_prompt(
            company="NexGen AI",
            role="Backend Engineer",
            job_snippet="Must know FastAPI and SQL optimization."
        )
        self.assertIn("NexGen AI", prompt)
        self.assertIn("Backend Engineer", prompt)
        self.assertIn("ssenterprisesncr.in", prompt)
        self.assertIn("GISFY", prompt)
        self.assertIn("FastAPI", prompt)
        self.assertIn("PostgreSQL", prompt)

    def test_generate_personalized_hook_fallback_when_no_api_key(self):
        """Verify fallback to standard achievements paragraph when GEMINI_API_KEY is empty."""
        with patch('django.conf.settings.GEMINI_API_KEY', ''):
            res = generate_personalized_hook("Acme Corp", "Python Dev", "FastAPI skills needed")
            self.assertTrue(res['success'])
            self.assertTrue(res['is_fallback'])
            self.assertEqual(res['hook'], DEFAULT_CANDIDATE_HIGHLIGHTS)

    def test_generate_personalized_hook_success_mocked(self):
        """Verify successful Gemini 2.5 Flash response parsing when SDK returns text."""
        mock_response = MagicMock()
        mock_response.text = '"I noticed your backend team at Acme is scaling with FastAPI and PostgreSQL—at GISFY, I optimized spatial queries by 35% with robust RBAC."'

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch('django.conf.settings.GEMINI_API_KEY', 'fake-valid-key'), \
             patch('google.genai.Client', return_value=mock_client):
            res = generate_personalized_hook("Acme", "FastAPI Dev", "Scaling APIs")

            self.assertTrue(res['success'])
            self.assertFalse(res['is_fallback'])
            self.assertIn("GISFY, I optimized spatial queries", res['hook'])
            # Verify quotes were stripped
            self.assertFalse(res['hook'].startswith('"'))
            self.assertFalse(res['hook'].endswith('"'))

    def test_generate_ai_hook_ajax_endpoint_auth_and_response(self):
        """Verify /api/generate-hook/ requires login and returns valid JSON response."""
        # Unauthenticated request
        res_unauth = self.client.post(reverse('generate_ai_hook'), {
            'company': 'FinTech Labs',
            'role': 'Full Stack Developer',
            'job_snippet': 'React and Django needed'
        })
        self.assertEqual(res_unauth.status_code, 302)

        # Authenticated request
        self.client.login(username="aitestuser", password="securepassword123")
        res_auth = self.client.post(
            reverse('generate_ai_hook'),
            data=json.dumps({
                'company': 'FinTech Labs',
                'role': 'Full Stack Developer',
                'job_snippet': 'React and Django needed'
            }),
            content_type='application/json'
        )
        self.assertEqual(res_auth.status_code, 200)
        data = res_auth.json()
        self.assertTrue(data['success'])
        self.assertIn('hook', data)

    def test_template_interpolation_with_custom_hook(self):
        """Verify custom AI hook is rendered inside email body during dispatch."""
        mail.outbox.clear()
        custom_ai_hook = "I noticed your team is building with FastAPI—I deployed a live platform at ssenterprisesncr.in saving 15 hours/week."

        send_emails_in_background(
            parsed_recipients=[{'email': 'cto@innovate.com', 'name': 'Aditi'}],
            template_id=self.template.id,
            resume_id=self.resume.id,
            custom_hook=custom_ai_hook
        )

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn(custom_ai_hook, sent_email.body)


class EmailOpenAndClickTelemetryTest(TestCase):
    """Unit and integration tests for email open pixel and link click-through telemetry."""

    def setUp(self):
        self.client = Client()
        self.template = EmailTemplate.objects.create(
            title="Telemetry Template",
            subject="Exploring Full Stack role at {{ company }}",
            body="Hello {{ name }},\n\nCheck my platform at https://www.ssenterprisesncr.in for live demo."
        )
        self.resume = ResumeDocument.objects.create(
            title="Telemetry Resume",
            filename="telemetry_resume.pdf",
            pdf_content=b"%PDF-1.4 mock telemetry pdf content"
        )
        self.log = ApplicationLog.objects.create(
            recipient_email="recruiter@techcorp.in",
            template=self.template,
            resume=self.resume,
            status="SUCCESS"
        )

    def test_record_email_open_atomic_increment(self):
        """Verify record_email_open sets opened_at and increments open_count atomically."""
        self.assertEqual(self.log.open_count, 0)
        self.assertIsNone(self.log.opened_at)

        # First open event
        success, updated_log = record_email_open(self.log.tracking_token)
        self.assertTrue(success)
        self.assertEqual(updated_log.open_count, 1)
        self.assertIsNotNone(updated_log.opened_at)
        first_open_time = updated_log.opened_at

        # Second open event (e.g. recruiter re-opens next morning)
        success2, updated_log2 = record_email_open(self.log.tracking_token)
        self.assertTrue(success2)
        self.assertEqual(updated_log2.open_count, 2)
        # Verify first opened timestamp was preserved
        self.assertEqual(updated_log2.opened_at, first_open_time)

    def test_track_open_view_returns_transparent_gif_and_nocache(self):
        """Verify /track/open/<token>/ returns 43-byte GIF with aggressive no-cache headers."""
        url = reverse('track_open', args=[self.log.tracking_token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/gif')
        self.assertEqual(response.content, TRANSPARENT_1PX_GIF)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('no-cache', response['Pragma'])

        # Verify database record was updated by view
        self.log.refresh_from_db()
        self.assertEqual(self.log.open_count, 1)
        self.assertIsNotNone(self.log.opened_at)

    def test_record_link_click_and_redirect(self):
        """Verify /track/click/<token>/?url=... increments click_count and redirects 302."""
        target_url = "https://www.ssenterprisesncr.in"
        url = reverse('track_click', args=[self.log.tracking_token]) + f"?url={target_url}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], target_url)

        self.log.refresh_from_db()
        self.assertEqual(self.log.click_count, 1)
        self.assertIsNotNone(self.log.clicked_at)

    def test_track_click_open_redirect_protection(self):
        """Verify malicious or unsafe schemes (javascript:, data:) are rejected to safe fallback."""
        malicious_url = "javascript:alert('XSS')"
        url = reverse('track_click', args=[self.log.tracking_token]) + f"?url={malicious_url}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        # Fallback to safe destination '/'
        self.assertEqual(response['Location'], '/')

    def test_prepare_multipart_email_bodies_structure(self):
        """Verify plain text and HTML versions are generated with pixel and wrapped links."""
        body = "Hi team,\n\nCheck my platform at https://www.ssenterprisesncr.in today."
        base_url = "https://job-bot.onrender.com"
        plain, html = prepare_multipart_email_bodies(body, self.log.tracking_token, base_url)

        # Plain text retains raw URL without tags
        self.assertIn("https://www.ssenterprisesncr.in", plain)
        self.assertNotIn("<img", plain)

        # HTML has tracking pixel pointing to base_url
        self.assertIn(f'{base_url}/track/open/{self.log.tracking_token}/', html)
        self.assertIn(f'{base_url}/track/click/{self.log.tracking_token}/', html)
        self.assertIn('<img src=', html)
        self.assertIn('<a href=', html)

    def test_dispatch_creates_multipart_alternatives_with_telemetry(self):
        """Verify background dispatch creates EmailMultiAlternatives with tracking token."""
        mail.outbox.clear()

        send_emails_in_background(
            parsed_recipients=[{'email': 'founder@startup.co', 'name': 'Karan'}],
            template_id=self.template.id,
            resume_id=self.resume.id
        )

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        # Verify email is MIME multi-part with HTML alternative
        self.assertEqual(len(sent_email.alternatives), 1)
        html_content, mimetype = sent_email.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('/track/open/', html_content)

        # Verify ApplicationLog record was created with unique token
        log_entry = ApplicationLog.objects.get(recipient_email='founder@startup.co')
        self.assertIsNotNone(log_entry.tracking_token)
        self.assertEqual(log_entry.open_count, 0)
        self.assertEqual(log_entry.click_count, 0)


class DjangoQPersistentTaskQueueTest(TestCase):
    """Unit and integration tests for Django-Q2 persistent background task queue."""

    def setUp(self):
        self.template = EmailTemplate.objects.create(
            title="Task Queue Template",
            subject="Python Lead at {{ company }}",
            body="Hi {{ name }}, I love building with FastAPI."
        )
        self.resume = ResumeDocument.objects.create(
            title="Task Queue Resume",
            filename="task_queue_resume.pdf",
            pdf_content=b"%PDF-1.4 mock task queue resume"
        )
        self.recruiter = RecruiterLead.objects.create(
            email="lead@scaleup.io",
            name="Rohit",
            company="ScaleUp",
            role="Backend Engineer",
            is_verified=True,
            is_contacted=False
        )

    def test_dispatch_applications_task_direct_execution(self):
        """Verify dispatch_applications_task executes cleanly and returns summary stats."""
        mail.outbox.clear()
        result = dispatch_applications_task(
            parsed_recipients=[{'email': 'lead@scaleup.io', 'name': 'Rohit', 'company': 'ScaleUp', 'role': 'Backend'}],
            template_id=self.template.id,
            resume_id=self.resume.id
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['success_count'], 1)
        self.assertEqual(result['failure_count'], 0)
        self.assertEqual(len(mail.outbox), 1)

        # Verify ApplicationLog was persisted
        log_entry = ApplicationLog.objects.get(recipient_email='lead@scaleup.io')
        self.assertEqual(log_entry.status, "SUCCESS")
        self.assertIsNotNone(log_entry.tracking_token)

        # Verify FollowUpSequence was scheduled
        self.assertTrue(FollowUpSequence.objects.filter(recipient_email='lead@scaleup.io').exists())

        # Verify RecruiterLead marked as contacted
        self.recruiter.refresh_from_db()
        self.assertTrue(self.recruiter.is_contacted)

    def test_async_task_synchronous_mode(self):
        """Verify async_task executes with sync=True and creates database records."""
        mail.outbox.clear()
        with patch('django_q.tasks.Conf.SYNC', True):
            task_id = async_task(
                'mailer.services.tasks.dispatch_applications_task',
                [{'email': 'vp@enterprise.com', 'name': 'Vikram', 'company': 'Enterprise', 'role': 'Lead'}],
                self.template.id,
                self.resume.id
            )

        self.assertIsNotNone(task_id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(ApplicationLog.objects.filter(recipient_email='vp@enterprise.com', status='SUCCESS').exists())

    def test_process_followups_scheduled_task(self):
        """Verify process_followups_scheduled_task executes due follow-ups correctly."""
        mail.outbox.clear()
        initial_log = ApplicationLog.objects.create(
            recipient_email="due.recruiter@bigtech.in",
            template=self.template,
            resume=self.resume,
            status="SUCCESS",
            message_id="<orig.due@mail.com>"
        )
        followup_template = EmailTemplate.objects.create(
            title="Python Full Stack Follow-Up (Day 4 Bump)",
            subject="Following up on my application",
            body="Hi {{ name }}, bumping my note."
        )
        # Create a sequence scheduled in the past (due now)
        past_time = timezone.now() - timedelta(days=5)
        seq = FollowUpSequence.objects.create(
            initial_log=initial_log,
            recipient_email="due.recruiter@bigtech.in",
            candidate_name="Shahbaz",
            company_name="BigTech",
            role_title="Python Developer",
            status='WAITING',
            scheduled_at=past_time
        )

        summary = process_followups_scheduled_task()
        self.assertGreaterEqual(summary['dispatched_count'], 1)

        seq.refresh_from_db()
        self.assertEqual(seq.status, 'SENT')
        self.assertIsNotNone(seq.dispatched_at)
        self.assertEqual(len(mail.outbox), 1)


class MultiPlatformHarvesterTest(TestCase):
    """
    Automated Test Suite for Phase 13 Multi-Platform Recruiter Harvester.
    Covers:
      - Remotive public API response parsing & lead extraction.
      - We Work Remotely RSS XML parsing & lead extraction.
      - Domain heuristic fallback (Option 2) when direct email is absent.
      - Multi-platform aggregation & platform routing.
      - Platform attribution persistence in Neon PostgreSQL.
      - Harvester web view POST/GET platform filtering.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="leadseeker", password="pass123Secure")
        self.client = Client()
        self.client.login(username="leadseeker", password="pass123Secure")

    @patch('requests.get')
    def test_harvest_from_remotive_api(self, mock_get):
        """Verify Remotive API returns normalized leads with source_platform='Remotive'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'jobs': [
                {
                    'id': 101,
                    'url': 'https://remotive.com/remote-jobs/software-dev/python-dev-101',
                    'title': 'Senior Python Backend Developer',
                    'company_name': 'CloudScale Systems',
                    'candidate_required_location': 'Worldwide',
                    'description': '<p>We are hiring! Reach out directly to talent@cloudscale.io with your resume. 3-5 years required.</p>'
                }
            ]
        }
        mock_get.return_value = mock_response

        leads = harvest_from_remotive(query="Python", location_filter="All", max_leads=5)
        self.assertEqual(len(leads), 1)
        lead = leads[0]
        self.assertEqual(lead['email'], 'talent@cloudscale.io')
        self.assertEqual(lead['company'], 'CloudScale Systems')
        self.assertEqual(lead['role'], 'Senior Python Backend Developer')
        self.assertEqual(lead['location'], 'Remote')
        self.assertEqual(lead['experience_tag'], '3-5 Years')
        self.assertEqual(lead['source_platform'], 'Remotive')

    @patch('requests.get')
    def test_harvest_from_wwr_rss(self, mock_get):
        """Verify We Work Remotely RSS parses XML items with source_platform='We Work Remotely'."""
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>We Work Remotely: Programming</title>
                <item>
                    <title>NextGen AI: Full Stack Python / Django Engineer</title>
                    <description>&lt;p&gt;Looking for an entry level fresher or junior 0-2 years developer. Email hiring@nextgenai.tech to apply.&lt;/p&gt;</description>
                    <link>https://weworkremotely.com/jobs/nextgen-ai-python</link>
                    <pubDate>Mon, 12 Nov 2026 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_xml.encode('utf-8')
        mock_get.return_value = mock_response

        leads = harvest_from_wwr(query="Python", location_filter="All", max_leads=5)
        self.assertEqual(len(leads), 1)
        lead = leads[0]
        self.assertEqual(lead['email'], 'hiring@nextgenai.tech')
        self.assertEqual(lead['company'], 'NextGen AI')
        self.assertEqual(lead['role'], 'Full Stack Python / Django Engineer')
        self.assertEqual(lead['location'], 'Remote')
        self.assertEqual(lead['experience_tag'], '0-3 Years')
        self.assertEqual(lead['source_platform'], 'We Work Remotely')

    @patch('mailer.services.harvester.verify_email_mx')
    def test_domain_heuristic_fallback(self, mock_mx):
        """Verify Option 2 domain fallback derives careers@domain when direct email is missing."""
        mock_mx.return_value = (True, "MX verified")
        raw_text = "Join our engineering team! Visit our careers page at https://scaletech.io/jobs for info."
        email = infer_recruiter_email(company_name="ScaleTech", raw_text=raw_text, source_url="https://scaletech.io/jobs")
        self.assertEqual(email, 'careers@scaletech.io')

    @patch('mailer.services.harvester.harvest_from_hacker_news')
    @patch('mailer.services.harvester.harvest_from_remotive')
    @patch('mailer.services.harvester.harvest_from_wwr')
    def test_harvest_multi_platform_aggregation(self, mock_wwr, mock_remotive, mock_hn):
        """Verify harvest_multi_platform aggregates leads across all platforms."""
        mock_hn.return_value = [{'email': 'hn@lead.io', 'source_platform': 'Hacker News'}]
        mock_remotive.return_value = [{'email': 'remotive@lead.io', 'source_platform': 'Remotive'}]
        mock_wwr.return_value = [{'email': 'wwr@lead.io', 'source_platform': 'We Work Remotely'}]

        all_leads = harvest_multi_platform(platform='all', query='Python', location_filter='All', max_leads=10)
        self.assertEqual(len(all_leads), 3)
        platforms = {l['source_platform'] for l in all_leads}
        self.assertEqual(platforms, {'Hacker News', 'Remotive', 'We Work Remotely'})

    @patch('mailer.services.harvester.verify_email_mx')
    def test_process_and_save_leads_persists_source_platform(self, mock_mx):
        """Verify process_and_save_leads saves source_platform to RecruiterLead model."""
        mock_mx.return_value = (True, "MX verified")
        candidate_leads = [
            {
                'email': 'remotive.candidate@startup.io',
                'name': 'Priya',
                'company': 'StartupHQ',
                'role': 'Backend Dev',
                'location': 'Remote',
                'experience_tag': '0-3 Years',
                'source_platform': 'Remotive',
                'source_url': 'https://remotive.com/123'
            }
        ]
        stats = process_and_save_leads(candidate_leads)
        self.assertEqual(stats['saved'], 1)

        lead = RecruiterLead.objects.get(email='remotive.candidate@startup.io')
        self.assertEqual(lead.source_platform, 'Remotive')

    @patch('mailer.services.harvester.harvest_multi_platform')
    @patch('mailer.services.harvester.verify_email_mx')
    def test_lead_harvester_view_feed_post_and_platform_filter(self, mock_mx, mock_harvest):
        """Verify lead_harvester_view handles multi-platform POST and filters by platform in GET."""
        mock_mx.return_value = (True, "MX verified")
        mock_harvest.return_value = [
            {
                'email': 'harvested.view@remotive.io',
                'name': 'Alex',
                'company': 'RemotiveCorp',
                'role': 'FastAPI Dev',
                'location': 'Gurugram',
                'experience_tag': '0-3 Years',
                'source_platform': 'Remotive',
                'source_url': 'https://remotive.com/456'
            }
        ]

        response = self.client.post(reverse('lead_harvester'), {
            'action': 'harvest_feed',
            'platform': 'remotive',
            'query': 'FastAPI',
            'location': 'Gurugram'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(RecruiterLead.objects.filter(email='harvested.view@remotive.io', source_platform='Remotive').exists())

        # Test GET with ?platform=Remotive
        get_response = self.client.get(reverse('lead_harvester') + '?platform=Remotive')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.context['current_filter_platform'], 'Remotive')


class DailyHarvesterSchedulerTest(TestCase):
    """
    Automated Test Suite for Phase 14 Automated Daily Scheduled Harvester.
    Covers:
      - Next daily 08:30 AM timezone-aware calculation.
      - Schedule initialization and idempotency in django_q_schedule table.
      - Pause and resume toggle state transitions.
      - Automated background task execution and summary reporting.
      - On-demand async_task() trigger dispatching.
      - Harvester web view POST actions (trigger_schedule_now, toggle_schedule).
    """

    def setUp(self):
        self.user = User.objects.create_user(username="schedulertester", password="pass123Secure")
        self.client = Client()
        self.client.login(username="schedulertester", password="pass123Secure")
        # Ensure test isolation by clearing any leftover schedules
        Schedule.objects.filter(name=SCHEDULE_NAME).delete()

    def test_calculate_next_daily_run(self):
        """Verify next run calculation targets 08:30 AM in the future."""
        next_dt = calculate_next_daily_run(8, 30)
        self.assertTrue(timezone.is_aware(next_dt))
        self.assertGreater(next_dt, timezone.now())
        local_tz = timezone.get_current_timezone()
        local_dt = next_dt.astimezone(local_tz)
        self.assertEqual(local_dt.hour, 8)
        self.assertEqual(local_dt.minute, 30)

    def test_get_or_create_daily_harvester_schedule(self):
        """Verify schedule is created in django_q_schedule table and is idempotent."""
        sched = get_or_create_daily_harvester_schedule()
        self.assertEqual(sched.name, SCHEDULE_NAME)
        self.assertEqual(sched.schedule_type, Schedule.DAILY)
        self.assertEqual(sched.repeats, -1)
        self.assertIsNotNone(sched.next_run)

        # Calling again should retrieve the same schedule, not duplicate
        sched2 = get_or_create_daily_harvester_schedule()
        self.assertEqual(sched.id, sched2.id)
        self.assertEqual(Schedule.objects.filter(name=SCHEDULE_NAME).count(), 1)

    def test_toggle_harvester_schedule(self):
        """Verify pausing sets repeats=0 and resuming resets repeats=-1."""
        get_or_create_daily_harvester_schedule()

        # Pause
        active = toggle_harvester_schedule(False)
        self.assertFalse(active)
        status = get_harvester_schedule_status()
        self.assertFalse(status['is_active'])

        # Resume
        active = toggle_harvester_schedule(True)
        self.assertTrue(active)
        status = get_harvester_schedule_status()
        self.assertTrue(status['is_active'])
        self.assertIsNotNone(status['next_run'])

    @patch('mailer.services.harvester.harvest_multi_platform')
    @patch('mailer.services.harvester.process_and_save_leads')
    def test_automated_daily_harvester_task_execution(self, mock_process, mock_harvest):
        """Verify automated_daily_harvester_task executes and returns execution metrics."""
        mock_harvest.return_value = [{'email': 'cand@job.io', 'company': 'TestCorp'}]
        mock_process.return_value = {'saved': 1, 'skipped_duplicate': 0, 'failed_mx': 0}

        summary = automated_daily_harvester_task(
            platform='all',
            query='Python',
            location_filter='All',
            max_leads=25
        )
        self.assertEqual(summary['candidates_found'], 1)
        self.assertEqual(summary['saved'], 1)
        self.assertEqual(summary['skipped_duplicate'], 0)
        self.assertEqual(summary['failed_mx'], 0)
        self.assertIn('executed_at', summary)

    @patch('mailer.services.scheduler.async_task')
    def test_trigger_immediate_harvester_run(self, mock_async):
        """Verify trigger_immediate_harvester_run calls async_task and returns task ID."""
        mock_async.return_value = 'task-uuid-12345'
        task_id = trigger_immediate_harvester_run(platform='all', query='Python')
        self.assertEqual(task_id, 'task-uuid-12345')
        self.assertTrue(mock_async.called)

    @patch('mailer.services.scheduler.trigger_immediate_harvester_run')
    def test_harvester_view_schedule_post_actions(self, mock_trigger):
        """Verify web action trigger_schedule_now and toggle_schedule in lead_harvester_view."""
        mock_trigger.return_value = 'task-sched-999'

        # Trigger on-demand run
        response = self.client.post(reverse('lead_harvester'), {
            'action': 'trigger_schedule_now',
            'platform': 'all',
            'query': 'Python',
            'location': 'All'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_trigger.called)

        # Toggle schedule
        toggle_response = self.client.post(reverse('lead_harvester'), {
            'action': 'toggle_schedule'
        }, follow=True)
        self.assertEqual(toggle_response.status_code, 200)


class KanbanTrackerTest(TestCase):
    """Unit and integration tests for Phase 15 Visual Kanban ATS Tracker."""

    def setUp(self):
        self.user = User.objects.create_user(username='shahbaz_ats', password='secretpassword123')
        self.client = Client()
        self.client.login(username='shahbaz_ats', password='secretpassword123')

        self.template = EmailTemplate.objects.create(
            title="ATS Test Template",
            subject="Python Engineer at {{ company }}",
            body="Hi {{ name }}, I am excited to apply."
        )
        self.resume = ResumeDocument.objects.create(
            title="ATS Test Resume",
            filename="ats_test_resume.pdf",
            pdf_content=b"%PDF-1.4 mock ATS resume"
        )

    def test_job_application_creation_and_properties(self):
        """Verify JobApplication model fields, defaults, and days_since_dispatch calculation."""
        app = JobApplication.objects.create(
            company_name="Google",
            role_title="Backend Engineer",
            recipient_email="recruiter@google.com",
            recipient_name="Sundar",
            priority="HIGH",
        )
        self.assertEqual(app.stage, "DISPATCHED")
        self.assertEqual(app.priority, "HIGH")
        self.assertEqual(app.days_since_dispatch, 0)
        self.assertIn("Google", str(app))
        self.assertIn("Backend Engineer", str(app))

    def test_dispatch_task_auto_creates_job_application(self):
        """Verify dispatch_applications_task automatically creates a JobApplication card in DISPATCHED."""
        mail.outbox.clear()
        result = dispatch_applications_task(
            parsed_recipients=[{'email': 'hiring@stripe.com', 'name': 'Patrick', 'company': 'Stripe', 'role': 'Staff Python Engineer'}],
            template_id=self.template.id,
            resume_id=self.resume.id
        )
        self.assertTrue(result['success'])

        # Verify JobApplication was created with metadata
        app = JobApplication.objects.get(recipient_email='hiring@stripe.com')
        self.assertEqual(app.company_name, "Stripe")
        self.assertEqual(app.role_title, "Staff Python Engineer")
        self.assertEqual(app.recipient_name, "Patrick")
        self.assertEqual(app.stage, "DISPATCHED")
        self.assertIsNotNone(app.initial_log)

    def test_open_telemetry_advances_stage_to_opened(self):
        """Verify recording an email open automatically advances JobApplication from DISPATCHED to OPENED."""
        mail.outbox.clear()
        dispatch_applications_task(
            parsed_recipients=[{'email': 'talent@airbnb.com', 'name': 'Brian', 'company': 'Airbnb', 'role': 'Full Stack'}],
            template_id=self.template.id,
            resume_id=self.resume.id
        )
        app = JobApplication.objects.get(recipient_email='talent@airbnb.com')
        self.assertEqual(app.stage, 'DISPATCHED')

        # Trigger open beacon
        success, log = record_email_open(app.initial_log.tracking_token)
        self.assertTrue(success)
        app.refresh_from_db()
        self.assertEqual(app.stage, 'OPENED')

    def test_click_telemetry_advances_stage_to_opened(self):
        """Verify recording a link click automatically advances JobApplication from DISPATCHED to OPENED."""
        mail.outbox.clear()
        dispatch_applications_task(
            parsed_recipients=[{'email': 'lead@netflix.com', 'name': 'Reed', 'company': 'Netflix', 'role': 'Python Developer'}],
            template_id=self.template.id,
            resume_id=self.resume.id
        )
        app = JobApplication.objects.get(recipient_email='lead@netflix.com')
        self.assertEqual(app.stage, 'DISPATCHED')

        # Trigger link click
        success, dest = record_link_click(app.initial_log.tracking_token, 'https://ssenterprisesncr.in')
        self.assertTrue(success)
        app.refresh_from_db()
        self.assertEqual(app.stage, 'OPENED')

    def test_followup_dispatch_advances_stage_to_followup_sent(self):
        """Verify dispatching a Day 4 follow-up advances JobApplication to FOLLOWUP_SENT."""
        mail.outbox.clear()
        dispatch_applications_task(
            parsed_recipients=[{'email': 'hr@uber.com', 'name': 'Dara', 'company': 'Uber', 'role': 'Backend'}],
            template_id=self.template.id,
            resume_id=self.resume.id
        )
        app = JobApplication.objects.get(recipient_email='hr@uber.com')
        sequence = FollowUpSequence.objects.get(recipient_email='hr@uber.com')

        # Dispatch follow-up
        res = dispatch_single_followup(sequence, force=True)
        self.assertTrue(res['success'])

        app.refresh_from_db()
        self.assertEqual(app.stage, 'FOLLOWUP_SENT')

    def test_update_stage_ajax_endpoint(self):
        """Verify /api/applications/<id>/update-stage/ successfully moves stage and rejects invalid stages."""
        app = JobApplication.objects.create(
            company_name="Microsoft",
            role_title="Senior Developer",
            recipient_email="recruiter@microsoft.com",
            stage="DISPATCHED"
        )
        url = reverse('update_application_stage', args=[app.id])

        # Valid stage move
        response = self.client.post(url, json.dumps({'stage': 'INTERVIEWING'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['stage'], 'INTERVIEWING')

        app.refresh_from_db()
        self.assertEqual(app.stage, 'INTERVIEWING')

        # Invalid stage move
        bad_response = self.client.post(url, json.dumps({'stage': 'NON_EXISTENT_STAGE'}), content_type='application/json')
        self.assertEqual(bad_response.status_code, 400)

    def test_update_details_ajax_endpoint(self):
        """Verify /api/applications/<id>/update-details/ updates priority, notes, salary, and interview date."""
        app = JobApplication.objects.create(
            company_name="Amazon",
            role_title="SDE II",
            recipient_email="recruiter@amazon.com",
            priority="LOW"
        )
        url = reverse('update_application_details', args=[app.id])

        payload = {
            'priority': 'HIGH',
            'interview_date': '2026-11-25T14:30:00',
            'salary_notes': '₹30-35 LPA',
            'notes': 'Completed round 1 with Bar Raiser.',
            'company_name': 'Amazon AWS',
            'role_title': 'Senior SDE II'
        }
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        app.refresh_from_db()
        self.assertEqual(app.priority, 'HIGH')
        self.assertEqual(app.company_name, 'Amazon AWS')
        self.assertEqual(app.role_title, 'Senior SDE II')
        self.assertEqual(app.salary_notes, '₹30-35 LPA')
        self.assertIn('Bar Raiser', app.notes)
        self.assertIsNotNone(app.interview_date)

    def test_create_application_endpoint(self):
        """Verify /api/applications/create/ allows manual card insertion."""
        url = reverse('create_application')
        payload = {
            'company_name': 'Zomato',
            'role_title': 'Python Lead',
            'recipient_email': 'jobs@zomato.com',
            'recipient_name': 'Deepinder',
            'stage': 'DISPATCHED',
            'priority': 'HIGH',
            'notes': 'Direct referral'
        }
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        self.assertTrue(JobApplication.objects.filter(company_name='Zomato', recipient_email='jobs@zomato.com').exists())

    def test_kanban_view_rendering_and_filters(self):
        """Verify kanban_tracker_view renders all 6 columns and handles priority/search filters."""
        JobApplication.objects.create(company_name="AlphaCo", role_title="Dev", recipient_email="a@alpha.co", priority="HIGH", stage="DISPATCHED")
        JobApplication.objects.create(company_name="BetaCo", role_title="Dev", recipient_email="b@beta.co", priority="LOW", stage="INTERVIEWING")

        # Standard view
        response = self.client.get(reverse('kanban_tracker'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'mailer/kanban.html')
        self.assertEqual(response.context['total_apps'], 2)
        self.assertEqual(response.context['interviewing_count'], 1)

        # Priority filter HIGH
        filter_resp = self.client.get(reverse('kanban_tracker') + '?priority=HIGH')
        self.assertEqual(filter_resp.status_code, 200)
        self.assertEqual(filter_resp.context['total_apps'], 1)

        # Search filter
        search_resp = self.client.get(reverse('kanban_tracker') + '?q=AlphaCo')
        self.assertEqual(search_resp.status_code, 200)
        self.assertEqual(search_resp.context['total_apps'], 1)





