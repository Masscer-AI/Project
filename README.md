Masscer AI Project

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

3. ## Install
Python requirements
```
pip install -r requirements.txt
```
Node requirements
```bash
cd streaming/ && npm i && cd .. 
```


4. ## Init
This will install the dependencies, run the migrations and start the project at port 8000


Initialize the Django server
```bash
python manage.py runserver
```

Initialize the Celery Worker for background tasks
```bash
# LINUX
celery -A api worker --loglevel=info -E
# windows
celery -A api.celery worker --pool=gevent --loglevel=INFO
```

Initialize the FastAPI server
```bash
python streaming/main.py
```


OPTIONAL
Initialize flower to inspect background tasks
```
celery -A api.celery flower --port=5555
```


5. Visit URLs:
Django server will live at: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

FastAPI server will live at: [http://127.0.0.1:8001/](http://127.0.0.1:8001/)


Flower if you are using flower:

Inspect tasks at: [http://127.0.0.1:5555/](http://127.0.0.1:5555/)
