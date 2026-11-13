"""Vercel Python function adapter for the Gemini cinema chat backend."""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

QUERIES = Path(__file__).resolve().parents[1]
if str(QUERIES) not in sys.path:
    sys.path.insert(0, str(QUERIES))

from gemini_chat import chat


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 1_048_576:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            status, body = chat(payload)
        except (ValueError, UnicodeDecodeError) as exc:
            status, body = 400, {"error": str(exc)}
        except Exception:
            status, body = 500, {"error": "Chat service failed. Please try again."}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send_error(405, "Use POST")
