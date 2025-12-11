from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule


class Command(BaseCommand):
    help = "Create or update the check_pending_conversations periodic task (runs every 5 minutes)"

    def handle(self, *args, **options):
        # Create interval schedule for 5 minutes
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created interval schedule: every {schedule.every} {schedule.period}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Using existing interval schedule: every {schedule.every} {schedule.period}')
            )

        # Create or update the periodic task
        task, created = PeriodicTask.objects.get_or_create(
            name='check_pending_conversations',
            defaults={
                'task': 'api.messaging.tasks.check_pending_conversations',
                'interval': schedule,
                'enabled': True,
            }
        )

        if not created:
            # Update the task if it already exists
            task.task = 'api.messaging.tasks.check_pending_conversations'
            task.interval = schedule
            task.crontab = None  # Clear crontab if it was set
            task.enabled = True
            task.save()
            self.stdout.write(
                self.style.SUCCESS('Updated existing periodic task "check_pending_conversations"')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Created periodic task "check_pending_conversations"')
            )

        self.stdout.write(
            self.style.SUCCESS(
                'Successfully set up check_pending_conversations task to run every 5 minutes. '
                'This task will check for pending conversations in organizations with the '
                '"conversation-analysis" feature flag enabled. '
                'You can view and manage it in Django admin under Periodic Tasks.'
            )
        )

