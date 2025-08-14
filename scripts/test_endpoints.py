#!/usr/bin/env python3
import argparse, json, os, sys, requests

def post_json(url, payload):
    r = requests.post(url, json=payload, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:400]}
    return r.status_code, body

def get_json(url):
    r = requests.get(url, timeout=30)
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:400]}
    return r.status_code, body

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.getenv("BASE_URL","https://mdraft-web.onrender.com"))
    ap.add_argument("--tool", choices=["criteria","outline"])
    ap.add_argument("--doc-id")
    ap.add_argument("--mode", choices=["smoke","full","prompts","health"], default="smoke")
    args = ap.parse_args()

    if args.mode == "health":
        sc, body = get_json(f"{args.base_url}/healthz")
        print("HTTP:", sc); print(json.dumps(body, indent=2)); return

    if args.mode == "prompts":
        sc, body = get_json(f"{args.base_url}/api/dev/check-prompts")
        print("HTTP:", sc); print(json.dumps(body, indent=2)); return

    if args.mode == "smoke":
        if not args.tool:
            ap.error("--tool required for smoke mode")
        sc, body = post_json(f"{args.base_url}/api/dev/gen-smoke", {"tool": args.tool})
        print("HTTP:", sc); print(json.dumps(body, indent=2)); return

    if args.mode == "full":
        if not args.doc_id:
            ap.error("--doc-id required for full mode")
        sc, body = post_json(f"{args.base_url}/api/generate/evaluation-criteria", {"document_id": args.doc_id})
        print("HTTP:", sc); print(json.dumps(body, indent=2)); return

if __name__ == "__main__":
    main()
