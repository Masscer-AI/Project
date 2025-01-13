from celery import signals
from django.db import close_old_connections

@signals.task_prerun.connect
def close_connections_before_task(*args, **kwargs):
    """Cierra conexiones antes de ejecutar una tarea."""
    print("closing connections before task")
    close_old_connections()

@signals.task_postrun.connect
def close_connections_after_task(*args, **kwargs):
    """Cierra conexiones después de ejecutar una tarea."""
    print("closing connections after task")
    close_old_connections()
