from __future__ import annotations

from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

from ctf_destroyer.import_cli import main


class _FakeHeaders:
    def __init__(self, content_type: str) -> None:
        self._content_type = content_type

    def get(self, name: str, default: str = "") -> str:
        if name.lower() == "content-type":
            return self._content_type
        return default

    def get_content_charset(self) -> str:
        return "utf-8"


class _FakeResponse:
    def __init__(self, body: str, url: str, content_type: str) -> None:
        self._body = body.encode("utf-8")
        self._url = url
        self.headers = _FakeHeaders(content_type)

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class CTFdImportCliTest(unittest.TestCase):
    def test_main_lists_ctfd_challenges_via_api(self) -> None:
        seen_cookies: list[str | None] = []

        def _fake_urlopen(req, timeout=None):
            seen_cookies.append(req.headers.get("Cookie"))
            if req.full_url.endswith("/api/v1/challenges"):
                return _FakeResponse(
                    '{"success": true, "data": [{"id": 31, "name": "Patient Portal", "value": 482, "solves": 14, "category": "misc"}]}',
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/challenges/31"):
                return _FakeResponse(
                    '{"success": true, "data": {"id": 31, "name": "Patient Portal", "value": 482, "solves": 14, "description": "<p>Gain full control of the machine.</p>", "category": "misc", "connection_info": null, "files": []}}',
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers/current"):
                return _FakeResponse(
                    '{"success": true, "data": {"challenge": 999, "access": []}}',
                    req.full_url,
                    "application/json",
                )
            return _FakeResponse(
                "<html><body><title>Espilon CTF</title><div id='challenge-window'></div></body></html>",
                req.full_url,
                "text/html; charset=utf-8",
            )

        stdout_buffer = io.StringIO()
        with patch("ctf_destroyer.importers.sources.request.urlopen", side_effect=_fake_urlopen), patch(
            "ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen
        ), redirect_stdout(stdout_buffer):
            status = main(
                [
                    "--session-cookie",
                    "abc123",
                    "https://ctf.example.com/challenges",
                    "--list",
                ]
            )

        self.assertEqual(status, 0)
        self.assertIn("Patient Portal", stdout_buffer.getvalue())
        self.assertIn("id=31", stdout_buffer.getvalue())
        self.assertIn("[warn: no target, no files]", stdout_buffer.getvalue())
        self.assertTrue(any(cookie == "session=abc123" for cookie in seen_cookies))

    def test_main_can_start_ctfd_container_instance(self) -> None:
        seen = {"post_called": False, "csrf": None}

        def _fake_urlopen(req, timeout=None):
            if req.full_url == "https://ctf.example.com/challenges":
                return _FakeResponse(
                    """
                    <html>
                      <head><script>window.init = {}; window.init['csrfNonce'] = "nonce-123";</script></head>
                      <body><div id="challenge-window"></div></body>
                    </html>
                    """,
                    req.full_url,
                    "text/html; charset=utf-8",
                )
            if req.full_url.endswith("/api/v1/challenges"):
                return _FakeResponse(
                    '{"success": true, "data": [{"id": 33, "name": "Glitch The Wired", "value": 387, "solves": 33, "category": "hardware"}]}',
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/challenges/33"):
                return _FakeResponse(
                    '{"success": true, "data": {"id": 33, "name": "Glitch The Wired", "value": 387, "solves": 33, "description": "<p>Glitch Lab challenge.</p>", "category": "hardware", "connection_info": null, "files": []}}',
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers/current"):
                if seen["post_called"]:
                    return _FakeResponse(
                        '{"success": true, "data": {"challenge": 33, "access": [{"name": "Glitch Lab", "url": "espilon.net 35597"}]}}',
                        req.full_url,
                        "application/json",
                    )
                return _FakeResponse(
                    '{"success": true, "data": {"challenge": 1, "access": []}}',
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers"):
                seen["post_called"] = True
                seen["csrf"] = req.headers.get("CSRF-Token") or req.headers.get("Csrf-token")
                return _FakeResponse(
                    '{"success": true, "data": {"access": []}}',
                    req.full_url,
                    "application/json",
                )
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        stdout_buffer = io.StringIO()
        with patch("ctf_destroyer.importers.sources.request.urlopen", side_effect=_fake_urlopen), patch(
            "ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen
        ), patch("ctf_destroyer.importers.ctfd.time.sleep"), redirect_stdout(stdout_buffer):
            status = main(
                [
                    "--session-cookie",
                    "abc123",
                    "https://ctf.example.com/challenges",
                    "--challenge",
                    "Glitch",
                    "--start-instance",
                    "--stdout",
                ]
            )

        self.assertEqual(status, 0)
        self.assertIn('"target_host": "espilon.net:35597"', stdout_buffer.getvalue())
        self.assertEqual(seen["csrf"], "nonce-123")


if __name__ == "__main__":
    unittest.main()
