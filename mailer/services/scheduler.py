"""
mailer/services/scheduler.py

Service layer for managing Django-Q recurring database schedules.
Orchestrates:
  - Daily Morning Harvester Schedule (08:30 AM IST)
  - On-Demand Immediate Trigger Override (async_task)
  - Pause / Resume Schedule Toggles
  - Real-time Schedule Telemetry & Last Execution Auditing
"""
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional

from django.utils import timezone
from django_q.models import Schedule, Task
from django_q.tasks import async_task

logger = logging.getLogger(__name__)

SCHEDULE_NAME = "daily_morning_harvester"
SCHEDULE_FUNC = "mailer.services.tasks.automated_daily_harvester_task"

DEFAULT_SCHEDULE_KWARGS = {
    'platform': 'all',
    'query': 'Python',
    'location_filter': 'All',
    'max_leads': 25
}


def calculate_next_daily_run(hour: int = 8, minute: int = 30) -> datetime:
    """
    Computes the upcoming datetime for 08:30 AM in the current application timezone.
    If 08:30 AM has already passed today, targets 08:30 AM tomorrow.
    """
    now = timezone.now()
    current_tz = timezone.get_current_timezone()
    local_now = now.astimezone(current_tz)

    target_today = datetime.combine(local_now.date(), time(hour, minute))
    target_today = timezone.make_aware(target_today, current_tz)

    if local_now < target_today:
        return target_today
    else:
        return target_today + timedelta(days=1)


def get_or_create_daily_harvester_schedule() -> Schedule:
    """
    Retrieves or initializes the daily recurring schedule in django_q_schedule table.
    Guarantees persistence in Neon PostgreSQL across restarts.
    """
    sched = Schedule.objects.filter(name=SCHEDULE_NAME).first()
    if not sched:
        next_run_dt = calculate_next_daily_run(8, 30)
        sched = Schedule.objects.create(
            name=SCHEDULE_NAME,
            func=SCHEDULE_FUNC,
            kwargs=DEFAULT_SCHEDULE_KWARGS,
            schedule_type=Schedule.DAILY,
            repeats=-1,  # Repeat indefinitely
            next_run=next_run_dt
        )
        logger.info(f"Initialized Django-Q schedule '{SCHEDULE_NAME}' with next run at {next_run_dt}")
    return sched


def toggle_harvester_schedule(active: bool) -> bool:
    """
    Pauses or resumes the daily harvester schedule.
    When paused, repeats is set to 0. When resumed, repeats is reset to -1.
    """
    sched = get_or_create_daily_harvester_schedule()
    if active:
        sched.repeats = -1
        sched.next_run = calculate_next_daily_run(8, 30)
        sched.save(update_fields=['repeats', 'next_run'])
        logger.info(f"Resumed schedule '{SCHEDULE_NAME}' with next run at {sched.next_run}")
        return True
    else:
        sched.repeats = 0
        sched.save(update_fields=['repeats'])
        logger.info(f"Paused schedule '{SCHEDULE_NAME}'")
        return False


def trigger_immediate_harvester_run(
    platform: str = "all",
    query: str = "Python",
    location_filter: str = "All",
    max_leads: int = 25
) -> Optional[str]:
    """
    Dispatches an on-demand background run of the automated harvester task
    via async_task(), bypassing the wait until 08:30 AM.
    """
    try:
        task_id = async_task(
            SCHEDULE_FUNC,
            platform=platform,
            query=query,
            location_filter=location_filter,
            max_leads=max_leads
        )
        logger.info(f"Triggered immediate on-demand harvester run: Task #{task_id}")
        return str(task_id)
    except Exception as e:
        logger.error(f"Failed triggering immediate harvester run: {e}")
        return None


def get_harvester_schedule_status() -> Dict[str, Any]:
    """
    Returns live schedule telemetry for the Harvester Dashboard:
      - is_active: whether the daily schedule is running or paused
      - next_run: upcoming scheduled run timestamp
      - last_run_time: timestamp of latest completed execution
      - last_run_success: boolean status of latest execution
      - last_run_result: result dictionary from latest execution
    """
    sched = Schedule.objects.filter(name=SCHEDULE_NAME).first()
    is_active = sched is not None and sched.repeats != 0
    next_run = sched.next_run if sched and is_active else None

    # Fetch latest completed audit task from django_q_task
    latest_task = Task.objects.filter(func=SCHEDULE_FUNC).order_by('-stopped').first()

    last_run_time = latest_task.stopped if latest_task else None
    last_run_success = latest_task.success if latest_task else None
    last_run_result = latest_task.result if latest_task else None

    return {
        'exists': sched is not None,
        'is_active': is_active,
        'next_run': next_run,
        'schedule_name': SCHEDULE_NAME,
        'target_time': "08:30 AM IST",
        'last_run_time': last_run_time,
        'last_run_success': last_run_success,
        'last_run_result': last_run_result,
    }
