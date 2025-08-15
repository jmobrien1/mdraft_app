#!/usr/bin/env python3
"""
Quick inline Celery ping test.

Usage: python3 scripts/ping_celery_inline.py
"""
import os
import time
from celery import Celery

# Get configuration
broker = os.environ.get('CELERY_BROKER_URL')
backend = os.environ.get('CELERY_RESULT_BACKEND') or broker

if not broker:
    print("ERROR: CELERY_BROKER_URL not set")
    exit(1)

print(f"Broker: {broker}")
print(f"Backend: {backend}")

# Create app and send task
app = Celery(broker=broker, backend=backend)
res = app.send_task('ping_task')
print(f"Task ID: {res.id}")

# Monitor status
for i in range(20):
    s = res.status
    print(f"Status ({i+1}/20): {s}")
    if s in ("SUCCESS", "FAILURE"):
        print(f"Result: {res.result}")
        break
    time.sleep(1)
else:
    print("Still PENDING after 20 seconds")
