from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_model_options import (
    remote_llm_headers,
)


@dataclass(frozen=True)
class RemoteLlmHealthResult:
    ok: bool
    url: str
    model: str
    status_code: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "url": self.url,
            "model": self.model,
            "status_code": self.status_code,
            "error": self.error,
        }


class RemoteLlmHealthChecker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def check(self) -> RemoteLlmHealthResult:
        model = self._settings.docling_remote_llm_model or self._settings.docling_vlm_model
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        }
        headers = {
            "Content-Type": "application/json",
            **remote_llm_headers(self._settings),
        }
        request = Request(
            self._settings.docling_remote_llm_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(
                request,
                timeout=self._settings.docling_remote_llm_health_check_timeout_seconds,
            ) as response:
                status_code = int(getattr(response, "status", 200))
                return RemoteLlmHealthResult(
                    ok=200 <= status_code < 300,
                    url=self._settings.docling_remote_llm_url,
                    model=model,
                    status_code=status_code,
                )
        except HTTPError as exc:
            return RemoteLlmHealthResult(
                ok=False,
                url=self._settings.docling_remote_llm_url,
                model=model,
                status_code=exc.code,
                error=str(exc),
            )
        except URLError as exc:
            return RemoteLlmHealthResult(
                ok=False,
                url=self._settings.docling_remote_llm_url,
                model=model,
                error=str(exc.reason),
            )
        except Exception as exc:
            return RemoteLlmHealthResult(
                ok=False,
                url=self._settings.docling_remote_llm_url,
                model=model,
                error=str(exc),
            )
