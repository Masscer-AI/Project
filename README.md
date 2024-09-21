1. ## Open a new virtual environment
```
py -m venv venv
```
2. ## Get inside the environment
```
venv\Scripts\activate
```
Or pressing F1, this will open the command palette, > Python: Select Interpreter
And select the venv

3. ## Run the develop command
```
bash develop.sh
```
This will install the dependencies, run the migrations and start the project at port 8000
```bash
# LINUX
celery -A api worker --loglevel=info -E
```

```bash
# windows
celery -A api.celery worker --pool=gevent --loglevel=INFO
```

```
celery -A api.celery flower --port=5555
```