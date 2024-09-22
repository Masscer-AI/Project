FROM python:3.9-slim-buster

WORKDIR /api


RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /api/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /api/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]