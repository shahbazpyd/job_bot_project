"""
mailer/management/commands/process_followups.py

Management command to automatically process and dispatch eligible Day 4 follow-up emails.
Can be executed manually or scheduled via Windows Task Scheduler or cron.

Usage:
    python manage.py process_followups
    python manage.py process_followups --dry-run
    python manage.py process_followups --limit 5
    python manage.py process_followups --force-id 42
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from mailer.models import FollowUpSequence
from mailer.services.followup import (
    dispatch_due_followups,
    dispatch_single_followup,
    get_followup_queue_stats
)


class Command(BaseCommand):
    help = "Processes and dispatches due Day 4 follow-up email sequences with RFC 2822 threading."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate processing without actually sending any emails.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximum number of follow-up emails to dispatch in this batch.',
        )
        parser.add_argument(
            '--force-id',
            type=int,
            default=None,
            help='Force-dispatch a specific FollowUpSequence ID immediately.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        limit = options.get('limit')
        force_id = options.get('force_id')

        self.stdout.write(self.style.MIGRATE_HEADING("=== Automated Follow-Up Engine ==="))

        stats = get_followup_queue_stats()
        self.stdout.write(
            f"Queue Snapshot: Total={stats['total']} | "
            f"Waiting={stats['waiting']} | Due={stats['due']} | "
            f"Sent={stats['sent']} | Replied={stats['replied']} | Cancelled={stats['cancelled']}"
        )

        if force_id:
            try:
                seq = FollowUpSequence.objects.get(id=force_id)
                self.stdout.write(f"Force-dispatching sequence #{seq.id} to {seq.recipient_email}...")
                if dry_run:
                    self.stdout.write(self.style.WARNING(f"[DRY-RUN] Would dispatch follow-up to {seq.recipient_email}"))
                    return

                res = dispatch_single_followup(seq, force=True)
                if res['success']:
                    self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Dispatched to {seq.recipient_email} (MsgID: {res['message_id']})"))
                else:
                    self.stdout.write(self.style.ERROR(f"[FAILED] Error: {res.get('error')}"))
            except FollowUpSequence.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Sequence with ID #{force_id} not found."))
            return

        now = timezone.now()
        due_qs = FollowUpSequence.objects.filter(
            status__in=['WAITING', 'READY'],
            scheduled_at__lte=now
        ).order_by('scheduled_at')

        if limit:
            due_qs = due_qs[:limit]

        due_list = list(due_qs)
        if not due_list:
            self.stdout.write(self.style.SUCCESS("No follow-up sequences are currently due for dispatch."))
            return

        self.stdout.write(f"Found {len(due_list)} sequence(s) eligible for dispatch.")

        if dry_run:
            self.stdout.write(self.style.WARNING("--- DRY-RUN MODE: No emails will be sent ---"))
            for seq in due_list:
                self.stdout.write(f"  • [ID {seq.id}] {seq.recipient_email} ({seq.company_name} - {seq.role_title}) scheduled at {seq.scheduled_at}")
            return

        self.stdout.write("Initiating batch dispatch with anti-spam pacing jitter...")
        result = dispatch_due_followups(limit=limit)
        
        self.stdout.write(self.style.SUCCESS(
            f"Batch completed: Total={result['total']}, "
            f"Succeeded={result['success']}, Failed={result['failed']}"
        ))
