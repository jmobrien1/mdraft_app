# Deploying mdraft_app to Render (Tonight's Beta)

## What this includes
- Flask app served by Gunicorn
- `/health` endpoint for Render health checks
- `/beta/convert` endpoint (upload a file, receive Markdown or a safe preview)
- No database or Celery required to boot

## Web Service (one-time)
1) Go to https://render.com → **New +** → **Web Service**
2) Connect GitHub → select **jmobrien1/mdraft_app** (branch: `main`)
3) Name: `mdraft-web`
4) Build Command:
   ```
   pip install -r requirements.txt
   ```
5. Start Command:
   ```
   gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120 wsgi:app
   ```
6. Advanced → Health Check Path: `/health`
7. Environment Variables:
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` = (Generate or any long random string)
8. Click **Create Web Service**. Wait for **Live**.

## Smoke tests
- Health: visit `https://<your-app>.onrender.com/health` → expect `{"status":"ok"}`
- Beta convert (from your terminal):
  ```bash
  echo "hello mdraft" > /tmp/hello.txt
  curl -s -X POST -F "file=@/tmp/hello.txt" https://<your-app>.onrender.com/beta/convert | python3 -m json.tool
  ```
  Expect a JSON with `markdown` field. If MarkItDown is not available or fails, you'll get a `warning` and a text preview.

## Notes
- You can add DB and a Celery worker later without changing this Start Command.
- If you see "No open ports detected", verify the Start Command and that Gunicorn starts cleanly.
