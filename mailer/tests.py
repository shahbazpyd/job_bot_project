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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Template, Context
from django.utils import timezone
from django.core.management import call_command

from .models import EmailTemplate, ResumeDocument, ApplicationLog, RecruiterLead, FollowUpSequence
from .forms import ApplicationDispatchForm
from .services.verifier import verify_email_mx
from .services.harvester import detect_location, detect_experience, harvest_from_text_block, process_and_save_leads
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
