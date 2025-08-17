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
    
    # FIXED: TLS configuration for rediss:// URLs
    if broker and broker.startswith("rediss://"):
        # For rediss:// URLs, explicitly set ssl_cert_reqs as required by redis-py
        c.conf.broker_use_ssl = {
            'ssl_cert_reqs': 'CERT_NONE',  # Don't verify SSL certificates
            'ssl_check_hostname': False,
            'ssl_ca_certs': None,
            'ssl_certfile': None,
            'ssl_keyfile': None,
        }
        
        # Only configure redis_backend_use_ssl if backend is also rediss://
        if backend and backend.startswith("rediss://"):
            c.conf.redis_backend_use_ssl = {
                'ssl_cert_reqs': 'CERT_NONE',  # Don't verify SSL certificates
                'ssl_check_hostname': False,
                'ssl_ca_certs': None,
                'ssl_certfile': None,
                'ssl_keyfile': None,
            }
    
    # Worker configuration
    c.conf.task_acks_late = True
    c.conf.worker_prefetch_multiplier = 1
    c.conf.worker_max_tasks_per_child = 1000
    c.conf.task_soft_time_limit = 600  # 10 minutes
    c.conf.task_time_limit = 900       # 15 minutes
    
    # Connection pool settings for Redis
    c.conf.broker_connection_retry = True
    c.conf.broker_connection_retry_on_startup = True
    c.conf.broker_connection_max_retries = 10
    
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
