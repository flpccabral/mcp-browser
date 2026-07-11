"""Network interception and HAR export for Playwright pages."""

import json
import os
from datetime import datetime
from typing import Any

from playwright.async_api import Page


class NetworkInterceptor:
    """Captures network requests and responses for a Playwright page."""

    def __init__(self, max_body_length: int = 50000, max_log_size: int = 10000):
        self.max_body_length = max_body_length
        self.max_log_size = max_log_size
        self._entries: list[dict[str, Any]] = []
        self._page: Page | None = None
        self._recording: bool = False
        self._recording_start: datetime | None = None
        self._recording_end: datetime | None = None

    # ------------------------------------------------------------------
    # Attach / detach
    # ------------------------------------------------------------------
    def attach(self, page: Page) -> None:
        """Register request/response listeners on the page."""
        import asyncio
        self._page = page
        page.on("request", lambda request: self._on_request(request))
        page.on("response", lambda response: asyncio.create_task(self._on_response(response)))

    # ------------------------------------------------------------------
    # Recording control
    # ------------------------------------------------------------------
    def start_recording(self) -> None:
        """Start capturing network requests into the log."""
        self._recording = True
        self._recording_start = datetime.now()
        self._recording_end = None
        self._entries.clear()

    def stop_recording(self) -> None:
        """Stop capturing network requests into the log."""
        self._recording = False
        self._recording_end = datetime.now()

    def is_recording(self) -> bool:
        """Return whether network recording is active."""
        return self._recording

    def get_recording_info(self) -> dict[str, Any]:
        """Return recording timestamps and stats."""
        return {
            "recording": self._recording,
            "started_at": self._recording_start.isoformat() if self._recording_start else None,
            "stopped_at": self._recording_end.isoformat() if self._recording_end else None,
            "total_captured": len(self._entries),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _truncate_if_needed(self) -> None:
        """Remove oldest entries when log exceeds max_log_size."""
        excess = len(self._entries) - self.max_log_size
        if excess > 0:
            self._entries = self._entries[excess:]

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_request(self, request):
        """Callback chamado em cada requisição HTTP."""
        if not self._recording:
            return

        try:
            post_data = request.post_data
        except Exception:
            post_data = None

        entry = {
            "id": id(request),
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": post_data,
            "resource_type": request.resource_type,
            "timestamp": datetime.now().isoformat(),
            "response_status": None,
            "response_headers": {},
            "response_body": None,
        }
        self._entries.append(entry)
        self._truncate_if_needed()

    async def _on_response(self, response) -> None:
        """Capture incoming response metadata and body (truncated if too large)."""
        if not self._recording:
            return

        req_id = id(response.request)

        # Find the matching entry
        entry = None
        for e in self._entries:
            if e["id"] == req_id:
                entry = e
                break

        if entry is None:
            # Response without a matching request (e.g., cached) — create stub
            entry = {
                "id": req_id,
                "url": response.url,
                "method": "GET",
                "headers": {},
                "post_data": None,
                "resource_type": response.request.resource_type if response.request else "other",
                "timestamp": datetime.now().isoformat(),
            }
            self._entries.append(entry)
            self._truncate_if_needed()

        entry["response_status"] = response.status
        entry["response_headers"] = dict(response.headers)

        # Attempt body capture
        try:
            body = await response.body()
            text = body.decode("utf-8", errors="replace")
            if len(text) > self.max_body_length:
                text = text[: self.max_body_length] + "\n... [truncated]"
            entry["response_body"] = text
        except Exception:
            entry["response_body"] = None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def get_log(
        self,
        filter_url: str | None = None,
        filter_method: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return captured network entries, optionally filtered."""
        results = self._entries[:]
        if filter_url:
            results = [e for e in results if filter_url in e.get("url", "")]
        if filter_method:
            results = [e for e in results if e.get("method", "") == filter_method.upper()]
        return results

    def list_requests(
        self,
        filter_url: str | None = None,
        filter_method: str | None = None,
    ) -> dict[str, Any]:
        """Return captured network entries with recording metadata."""
        results = self._entries[:]
        if filter_url:
            results = [e for e in results if filter_url in e.get("url", "")]
        if filter_method:
            results = [e for e in results if e.get("method", "") == filter_method.upper()]
        return {
            "recording": self._recording,
            "recording_start": self._recording_start.isoformat() if self._recording_start else None,
            "recording_end": self._recording_end.isoformat() if self._recording_end else None,
            "total_captured": len(self._entries),
            "filtered_count": len(results),
            "requests": results,
        }

    # ------------------------------------------------------------------
    # HAR export
    # ------------------------------------------------------------------
    def export_har(self, path: str) -> None:
        """Export captured network activity as a HAR 1.2 file."""
        har = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "mcp-browser-automation",
                    "version": "1.0.0",
                },
                "entries": [],
            }
        }

        for e in self._entries:
            entry = {
                "startedDateTime": e.get("timestamp", datetime.now().isoformat()),
                "time": 0,
                "request": {
                    "method": e.get("method", "GET"),
                    "url": e.get("url", ""),
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in e.get("headers", {}).items()
                    ],
                    "queryString": [],
                    "cookies": [],
                    "headersSize": -1,
                    "bodySize": -1,
                },
                "response": {
                    "status": e.get("response_status", 0),
                    "statusText": "",
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in e.get("response_headers", {}).items()
                    ],
                    "cookies": [],
                    "content": {
                        "size": len(e["response_body"]) if e.get("response_body") else 0,
                        "mimeType": e.get("response_headers", {}).get("content-type", "application/octet-stream"),
                        "text": e.get("response_body", ""),
                    },
                    "redirectURL": "",
                    "headersSize": -1,
                    "bodySize": -1,
                },
                "cache": {},
                "timings": {
                    "blocked": -1,
                    "dns": -1,
                    "connect": -1,
                    "send": -1,
                    "wait": -1,
                    "receive": -1,
                    "ssl": -1,
                },
            }
            har["log"]["entries"].append(entry)

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(har, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Clear all captured network entries and recording timestamps."""
        self._entries.clear()
        self._recording_start = None
        self._recording_end = None
