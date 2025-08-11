# Deploying mdraft_app to Render (Tonight's Beta)

## What this deploy includes
- Flask app served by Gunicorn
- `/health` endpoint so Render sees the service as healthy
- No DB or worker required to boot; you can add them later

## One-time steps on Render
1. Go to https://render.com → **New +** → **Web Service**.
2. Connect GitHub and select repo **jmobrien1/mdraft_app** (branch: `main`).
3. Name: `mdraft-web`
4. Build Command:
   ```
   pip install -r requirements.txt
   ```
5. Start Command:
   ```
   gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app
   ```
6. Advanced → Health Check Path: `/health`
7. Environment Variables → Add:
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` = (click Generate or paste any long random string)

Click **Create Web Service** and wait for it to say **Live**.

## Smoke test
Visit your Render URL in a browser and append `/health`. You should see:
```json
{"status":"ok"}
```

## If you need Postgres later (optional)
- Create a Render PostgreSQL instance, copy its External Connection String.
- Add `DATABASE_URL` to the Web Service Environment.
- Web Service → Settings → Post-deploy Command:
  ```
  flask db upgrade || (flask db stamp head && flask db migrate -m "init" && flask db upgrade)
  ```
- Redeploy.

## If you need a Celery worker later (optional)
- New + → Background Worker → same repo/branch
- Build: `pip install -r requirements.txt`
- Start:
  ```
  celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4 --without-gossip --without-mingle
  ```
- Set `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` to your Redis `rediss://...` URL.
