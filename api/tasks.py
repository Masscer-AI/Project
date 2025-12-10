from celery import shared_task


@shared_task
def hello_world():
    """Tarea de prueba que imprime 'hello world' en la consola."""
    print("hello world")
    return "hello world"

