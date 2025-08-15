from celery_worker import celery


@celery.task(name="ping_task", bind=True)
def ping_task(self):
    """Simple ping task for worker health checks.
    
    Returns:
        dict: Simple success response with task info
    """
    return {
        "ok": True, 
        "timestamp": "ping",
        "task_id": self.request.id,
        "worker": self.request.hostname
    }
