"""A tiny in-process fake of the Telegram Bot API for tests. Records every call."""
from __future__ import annotations

import json
import threading
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


class FakeTelegram:
    def __init__(self):
        self.calls: list[tuple[str, dict, dict]] = []   # (method, fields, files{name: bytes})
        self.updates: list[dict] = []
        self.fail_next: list[dict] = []                 # queued error bodies to return
        self._msg_id = 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                method = self.path.rsplit("/", 1)[-1]
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                ctype = self.headers.get("Content-Type", "")
                fields, files = {}, {}
                if ctype.startswith("multipart/"):
                    msg = BytesParser(policy=email_policy).parsebytes(
                        f"Content-Type: {ctype}\r\n\r\n".encode() + body)
                    for part in msg.iter_parts():
                        name = part.get_param("name", header="content-disposition")
                        if part.get_filename():
                            files[name] = part.get_payload(decode=True)
                        else:
                            fields[name] = part.get_payload(decode=True).decode("utf-8")
                else:
                    fields = {k: v[0] for k, v in parse_qs(body.decode()).items()}
                fake.calls.append((method, fields, files))
                if fake.fail_next:
                    out = fake.fail_next.pop(0)
                else:
                    out = {"ok": True, "result": fake.result(method, fields)}
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def result(self, method: str, fields: dict):
        if method == "getMe":
            return {"id": 1, "is_bot": True, "username": "test_bot"}
        if method == "getUpdates":
            offset = int(fields.get("offset", 0) or 0)
            return [u for u in self.updates if u["update_id"] >= offset]
        self._msg_id += 1
        return {"message_id": self._msg_id}

    def methods(self) -> list[str]:
        return [c[0] for c in self.calls]

    def close(self):
        self.server.shutdown()
