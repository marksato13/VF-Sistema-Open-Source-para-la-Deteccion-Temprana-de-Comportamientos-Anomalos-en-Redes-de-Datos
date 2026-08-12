#!/usr/bin/env python3
"""API local mínima para campañas L7 reproducibles del laboratorio PPI."""
import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8090
LOG = "/var/log/ppi-api/auth.jsonl"

def record(handler, result, username=""):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    xff = handler.headers.get("X-Forwarded-For")
    remote_addr = xff.split(",")[0].strip() if xff else handler.client_address[0]
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "remote_addr": remote_addr, "method": handler.command,
        "path": handler.path.split("?", 1)[0], "username": username,
        "result": result,
    }
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")

class Handler(BaseHTTPRequestHandler):
    server_version = "PPI-API/1.0"
    def send_json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path == "/api/health": self.send_json(200, {"status":"ok","service":"ppi-api"}); return
        if self.path == "/api/profile": self.send_json(200, {"service":"ppi-api","version":"1.0"}); return
        record(self, "not_found"); self.send_json(404, {"error":"not_found"})
    def do_POST(self):
        if self.path != "/api/login": record(self, "not_found"); self.send_json(404, {"error":"not_found"}); return
        try:
            size = int(self.headers.get("Content-Length", "0")); body = json.loads(self.rfile.read(size) or b"{}")
        except (ValueError, json.JSONDecodeError): record(self, "bad_request"); self.send_json(400, {"error":"bad_json"}); return
        user, credential = str(body.get("username", "")), str(body.get("password", ""))
        expected = os.environ.get("PPI_API_DEMO_CREDENTIAL", "demo-pass-2026")
        if user == "demo" and credential == expected: record(self, "success", user); self.send_json(200, {"authenticated":True}); return
        record(self, "failure", user); self.send_json(401, {"authenticated":False,"error":"invalid_credentials"})
    def do_PUT(self): self.send_json(204, {})
    def do_DELETE(self): self.send_json(403, {"error":"forbidden"})
    def log_message(self, *_): pass

if __name__ == "__main__": ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
