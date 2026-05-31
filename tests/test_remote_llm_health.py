from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.remote_llm_health import (
    RemoteLlmHealthChecker,
)


class _OpenAiCompatibleHandler(BaseHTTPRequestHandler):
    request_payload: ClassVar[dict[str, object] | None] = None
    auth_header: ClassVar[str | None] = None

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(content_length)
        self.__class__.request_payload = json.loads(payload.decode("utf-8"))
        self.__class__.auth_header = self.headers.get("Authorization")
        response = {
            "id": "chatcmpl-test",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        return


def test_remote_llm_health_checker_posts_openai_compatible_payload() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OpenAiCompatibleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        result = RemoteLlmHealthChecker(
            Settings(
                docling_remote_llm_url=url,
                docling_remote_llm_model="served-qwen3",
                docling_remote_llm_api_key="secret",
                docling_remote_llm_health_check_timeout_seconds=2,
            )
        ).check()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert result.ok is True
    assert result.status_code == 200
    assert _OpenAiCompatibleHandler.auth_header == "Bearer secret"
    assert _OpenAiCompatibleHandler.request_payload == {
        "model": "served-qwen3",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
