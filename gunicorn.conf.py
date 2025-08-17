"""
Production Gunicorn configuration for mdraft application.

This configuration is optimized for Render deployment and includes
proper error handling, logging, and worker management.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Server socket
bind = "0.0.0.0:10000"  # Render's default port
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True
timeout = 120
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "mdraft"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (handled by Render)
keyfile = None
certfile = None

def when_ready(server):
    """Called just after the server is started."""
    logger.info("Gunicorn server is ready to serve requests")

def on_starting(server):
    """Called just before the master process is initialized."""
    logger.info("Starting Gunicorn master process")

def on_reload(server):
    """Called to reload the server."""
    logger.info("Reloading Gunicorn server")

def worker_int(worker):
    """Called just after a worker has been initialized."""
    logger.info(f"Worker {worker.pid} initialized")

def pre_fork(server, worker):
    """Called just before a worker has been forked."""
    logger.info(f"Pre-forking worker {worker.pid}")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    logger.info(f"Post-forking worker {worker.pid}")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    logger.info(f"Worker {worker.pid} application initialized")

def worker_abort(worker):
    """Called when a worker received SIGABRT signal."""
    logger.error(f"Worker {worker.pid} received SIGABRT")

def pre_exec(server):
    """Called just before a new master process is forked."""
    logger.info("Pre-executing new master process")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    logger.info("Gunicorn server exiting")

def worker_exit(server, worker):
    """Called when a worker exits."""
    logger.info(f"Worker {worker.pid} exited")

def nworkers_changed(server, new_value, old_value):
    """Called when the number of workers has changed."""
    logger.info(f"Number of workers changed from {old_value} to {new_value}")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    logger.info("Gunicorn server exiting")

def post_request(worker, req, environ, resp):
    """Called after a request has been processed."""
    logger.debug(f"Request processed: {req.method} {req.path}")

def pre_request(worker, req):
    """Called before a request has been processed."""
    logger.debug(f"Processing request: {req.method} {req.path}")

# Error handling
def worker_exit(server, worker):
    """Called when a worker exits."""
    logger.error(f"Worker {worker.pid} exited unexpectedly")

def worker_abort(worker):
    """Called when a worker received SIGABRT signal."""
    logger.error(f"Worker {worker.pid} received SIGABRT signal")

# Custom error handling for production
def handle_exception(worker, req, environ, exc_info):
    """Custom exception handler for production."""
    logger.error(f"Unhandled exception in worker {worker.pid}: {exc_info[1]}")
    logger.error(f"Request: {req.method} {req.path}")
    logger.error(f"Exception type: {exc_info[0].__name__}")
    logger.error(f"Exception details: {str(exc_info[1])}")

# Set custom exception handler
worker_exit = worker_exit
worker_abort = worker_abort
