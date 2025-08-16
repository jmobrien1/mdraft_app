import os
import logging
from celery import Celery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def make_celery():
    broker = os.getenv("CELERY_BROKER_URL", "")
    backend = os.getenv("CELERY_RESULT_BACKEND") or broker or None
    
    # Log connection details for debugging
    logger.info(f"Initializing Celery with broker: {broker}")
    logger.info(f"Result backend: {backend}")
    
    if not broker:
        logger.warning("CELERY_BROKER_URL not set - worker may not function properly")
    
    c = Celery("mdraft", broker=broker or None, backend=backend)
    
    # Set default queue
    c.conf.task_default_queue = 'mdraft_default'
    c.conf.task_default_exchange = 'mdraft_default'
    c.conf.task_default_routing_key = 'mdraft_default'
    
    # TLS for rediss://
    if broker and broker.startswith("rediss://"):
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
        },
        'app.celery_tasks.ping_task': {
            'queue': 'mdraft_default',
            'routing_key': 'mdraft_default',
        },
        'app.celery_tasks.daily_cleanup_task': {
            'queue': 'mdraft_default',
            'routing_key': 'mdraft_default',
        }
    }
    
    # Beat schedule for periodic tasks
    c.conf.beat_schedule = {
        'daily-cleanup': {
            'task': 'app.celery_tasks.daily_cleanup_task',
            'schedule': 86400.0,  # 24 hours in seconds
        },
    }
    
    # Register tasks explicitly
    c.autodiscover_tasks(['app.celery_tasks'])
    
    return c

celery = make_celery()

# Register tasks explicitly to ensure they're available
@celery.task
def ping_task(message: str = "pong"):
    """Ping task for smoke testing worker connectivity."""
    from app.celery_tasks import ping_task as ping_func
    return ping_func(message)

@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def convert_document(self, conversion_id: str, user_id: int, gcs_uri: str, callback_url: str = None):
    """Convert document task with idempotence and retry logic."""
    from app.celery_tasks import convert_document as convert_func
    return convert_func(conversion_id, user_id, gcs_uri, callback_url)

@celery.task
def daily_cleanup_task():
    """Daily cleanup task."""
    from app.celery_tasks import daily_cleanup_task as cleanup_func
    return cleanup_func()

# Test broker connection on startup
def test_broker_connection():
    """Test broker connection and log diagnostics."""
    try:
        broker = os.getenv("CELERY_BROKER_URL", "")
        if not broker:
            logger.error("CELERY_BROKER_URL not set")
            return False
        
        logger.info(f"Testing broker connection: {broker}")
        
        # Try to connect to broker
        from celery import current_app
        app = current_app._get_current_object()
        
        with app.connection() as conn:
            conn.ensure_connection(max_retries=3)
            logger.info("Broker connection successful")
            return True
            
    except Exception as e:
        logger.error(f"Broker connection failed: {e}")
        logger.error("Worker will not function properly without broker connection")
        return False

# Run connection test on import
if __name__ != "__main__":
    test_broker_connection()
