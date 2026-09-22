FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py bigquery.py campaigns.py config.py demo.py model.py salesforce.py views.py ./
COPY assets/ assets/

ENV PORT=8080
EXPOSE 8080

# A single worker keeps exactly one shared 60s Salesforce cache per container instance --
# with 2+ workers, each has its own cache and can independently trigger a redundant
# concurrent reload, compounding into multi-second stalls. Threads still give real concurrency
# for this I/O-bound (network-call-heavy) workload.
CMD exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 65 app:server
