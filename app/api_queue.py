from flask import Blueprint, jsonify
from celery_worker import celery_app as celery

bp = Blueprint("api_queue", __name__, url_prefix="/api/queue")

@bp.post("/ping")
def queue_ping():
    task = celery.send_task("ping")
    return jsonify(task_id=task.id), 202
