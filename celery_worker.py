import os
from celery import Celery

def make_celery():
    broker = os.getenv("CELERY_BROKER_URL", "")
    backend = os.getenv("CELERY_RESULT_BACKEND") or broker or None
    c = Celery("mdraft", broker=broker or None, backend=backend)
    # TLS for rediss://
    if broker.startswith("rediss://"):
        c.conf.broker_use_ssl = {"ssl_cert_reqs": "none"}
        c.conf.redis_backend_use_ssl = {"ssl_cert_reqs": "none"}
    c.conf.task_acks_late = True
    c.conf.worker_prefetch_multiplier = 1
    return c

celery = make_celery()
