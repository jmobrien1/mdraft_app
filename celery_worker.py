from celery import Celery
import os

def make_celery():
    broker = os.getenv("CELERY_BROKER_URL", "")
    backend = os.getenv("CELERY_RESULT_BACKEND") or broker or None
    c = Celery("mdraft", broker=broker or None, backend=backend)
    c.conf.broker_connection_retry = True
    c.conf.broker_connection_retry_on_startup = True
    c.conf.broker_connection_max_retries = 10
    return c

celery = make_celery()
