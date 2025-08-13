import os
from celery import Celery

def make_celery():
    broker = os.getenv("CELERY_BROKER_URL", "")
    backend = os.getenv("CELERY_RESULT_BACKEND") or broker or None
    c = Celery("mdraft", broker=broker or None, backend=backend)
    
    # Set default queue
    c.conf.task_default_queue = 'mdraft_default'
    c.conf.task_default_exchange = 'mdraft_default'
    c.conf.task_default_routing_key = 'mdraft_default'
    
    # TLS for rediss://
    if broker.startswith("rediss://"):
        c.conf.broker_use_ssl = {"ssl_cert_reqs": "none"}
        c.conf.redis_backend_use_ssl = {"ssl_cert_reqs": "none"}
    
    # Worker configuration
    c.conf.task_acks_late = True
    c.conf.worker_prefetch_multiplier = 1
    
    # Task routing for priority queue
    c.conf.task_routes = {
        'app.celery_tasks.convert_document': {
            'queue': 'mdraft_priority',
            'routing_key': 'mdraft_priority',
        }
    }
    
    # Beat schedule for periodic tasks
    c.conf.beat_schedule = {
        'daily-cleanup': {
            'task': 'app.celery_tasks.daily_cleanup_task',
            'schedule': 86400.0,  # 24 hours in seconds
        },
    }
    
    return c

celery = make_celery()

# Tasks are registered dynamically when needed
