from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import io
import unittest
from unittest.mock import patch

from ctf_destroyer.importers.models import ImportRequest, SourceDocument
from ctf_destroyer.importers.ctfd import import_ctfd_challenge, try_discover_ctfd_challenges
from ctf_destroyer.importers.sources import load_source_document
from ctf_destroyer.importers.text import (
    discover_text_challenges,
    import_text_challenge,
    list_discovered_challenges,
    select_text_challenge,
)


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
    def __init__(self, body: str, url: str, content_type: str = "text/html; charset=utf-8") -> None:
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


class ImportersTest(unittest.TestCase):
    def test_discover_text_challenges_splits_multiple_candidates(self) -> None:
        document = SourceDocument(
            source_type="stdin",
            source_label="stdin",
            raw_text="\n".join(
                [
                    "Forbidden Fruit 150 pts · 754 Solves",
                    "Play at https://aes.cryptohack.org/forbidden_fruit",
                    "",
                    "Noise Cheap 90 pts · 337 Solves",
                    "Connect at socket.cryptohack.org 13413",
                ]
            ),
        )

        candidates = discover_text_challenges(document)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].title, "Forbidden Fruit")
        self.assertEqual(candidates[1].title, "Noise Cheap")

    def test_select_text_challenge_requires_selection_when_multiple(self) -> None:
        candidates = [
            discover_text_challenges(
                SourceDocument(
                    source_type="stdin",
                    source_label="stdin",
                    raw_text="Forbidden Fruit 150 pts\nPlay at https://aes.cryptohack.org/forbidden_fruit",
                )
            )[0],
            discover_text_challenges(
                SourceDocument(
                    source_type="stdin",
                    source_label="stdin",
                    raw_text="Noise Cheap 90 pts\nConnect at socket.cryptohack.org 13413",
                )
            )[0],
        ]
        with self.assertRaises(SystemExit):
            select_text_challenge(candidates, None)

    def test_import_text_challenge_extracts_fields_from_collapsed_text(self) -> None:
        raw_text = "\n".join(
            [
                "Noise Cheap 90 pts · 337 Solves",
                "A core part of making LWE secure is having the noise terms be larger than what lattice reduction algorithms can handle.",
                "",
                "Connect at socket.cryptohack.org 13413",
                "",
                "Challenge files:",
                "  - 13413.py https://cryptohack.org/static/challenges/13413_0c0d299900953fdef5b48dafe6245d32.py",
            ]
        )
        document = SourceDocument(source_type="stdin", source_label="stdin", raw_text=raw_text)
        candidate = discover_text_challenges(document)[0]

        imported = import_text_challenge(candidate, document)

        self.assertEqual(imported.title, "Noise Cheap")
        self.assertEqual(imported.category, "crypto")
        self.assertEqual(imported.target_host, "socket.cryptohack.org:13413")
        self.assertEqual(imported.points, 90)
        self.assertEqual(imported.solves, 337)
        self.assertEqual(
            imported.files,
            ["https://cryptohack.org/static/challenges/13413_0c0d299900953fdef5b48dafe6245d32.py"],
        )
        self.assertIn("avoid brute force", (imported.operator_hint or "").lower())

    def test_list_discovered_challenges_formats_entries(self) -> None:
        document = SourceDocument(
            source_type="stdin",
            source_label="stdin",
            raw_text="Forbidden Fruit 150 pts · 754 Solves\n\nNoise Cheap 90 pts · 337 Solves",
        )

        listing = list_discovered_challenges(discover_text_challenges(document))

        self.assertIn("[1] Forbidden Fruit (150 pts, 754 solves)", listing)
        self.assertIn("[2] Noise Cheap (90 pts, 337 solves)", listing)

    def test_load_source_document_fetches_url_with_session_cookie(self) -> None:
        seen_request = {}

        def _fake_urlopen(req, timeout=None):
            seen_request["cookie"] = req.headers.get("Cookie")
            return _FakeResponse(
                """
                <html><body>
                <h1>Noise Cheap 90 pts · 337 Solves</h1>
                <p>Connect at socket.cryptohack.org 13413</p>
                <a href="https://cryptohack.org/static/challenges/13413.py">file</a>
                </body></html>
                """,
                "https://example.test/challenge/noise-cheap",
            )

        with patch("ctf_destroyer.importers.sources.request.urlopen", side_effect=_fake_urlopen):
            document = load_source_document(
                ImportRequest(
                    source="https://example.test/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge=None,
                    list_only=False,
                    session_cookie="session=abc123",
                    cookie_file=None,
                    start_instance=False,
                )
            )

        self.assertEqual(seen_request["cookie"], "session=abc123")
        self.assertEqual(document.source_type, "url_html")
        self.assertIn("Noise Cheap 90 pts", document.raw_text)
        self.assertIn("https://cryptohack.org/static/challenges/13413.py", document.urls)

    def test_try_discover_ctfd_challenges_uses_api(self) -> None:
        document = SourceDocument(
            source_type="url_html",
            source_label="https://ctf.example.com/challenges",
            fetched_url="https://ctf.example.com/challenges",
            raw_text="Espilon CTF\nChallenges",
        )

        def _fake_urlopen(req, timeout=None):
            self.assertEqual(req.headers.get("Cookie"), "session=abc123")
            return _FakeResponse(
                '{"success": true, "data": [{"id": 31, "name": "Patient Portal", "value": 482, "solves": 14, "category": "misc"}]}',
                "https://ctf.example.com/api/v1/challenges",
                "application/json",
            )

        with patch("ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen):
            candidates = try_discover_ctfd_challenges(
                document,
                ImportRequest(
                    source="https://ctf.example.com/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge=None,
                    list_only=False,
                    session_cookie="abc123",
                    cookie_file=None,
                    start_instance=False,
                ),
            )

        assert candidates is not None
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "Patient Portal")
        self.assertEqual(candidates[0].challenge_id, 31)

    def test_import_ctfd_challenge_fetches_detail(self) -> None:
        document = SourceDocument(
            source_type="url_html",
            source_label="https://ctf.example.com/challenges",
            fetched_url="https://ctf.example.com/challenges",
            raw_text="Espilon CTF\nChallenges",
        )
        candidate = discover_text_challenges(
            SourceDocument(source_type="stdin", source_label="stdin", raw_text="Patient Portal 482 pts · 14 Solves")
        )[0]
        candidate = type(candidate)(
            title=candidate.title,
            text_block=candidate.text_block,
            challenge_id=31,
            category="misc",
            points=candidate.points,
            solves=candidate.solves,
            source_label=candidate.source_label,
        )

        def _fake_urlopen(req, timeout=None):
            self.assertEqual(req.headers.get("Cookie"), "session=abc123")
            return _FakeResponse(
                """{"success": true, "data": {"id": 31, "name": "Patient Portal", "value": 482, "solves": 14, "description": "<p>Gain full control of the machine.</p><p>Ports:<br>- 8080 : Web Portal (HTTP)</p>", "category": "misc", "connection_info": null, "files": ["/files/patient.zip"]}}""",
                "https://ctf.example.com/api/v1/challenges/31",
                "application/json",
            )

        with patch("ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen):
            imported = import_ctfd_challenge(
                candidate,
                document,
                ImportRequest(
                    source="https://ctf.example.com/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge="Patient Portal",
                    list_only=False,
                    session_cookie="abc123",
                    cookie_file=None,
                    start_instance=False,
                ),
            )

        assert imported is not None
        self.assertEqual(imported.title, "Patient Portal")
        self.assertEqual(imported.files, ["https://ctf.example.com/files/patient.zip"])
        self.assertEqual(imported.points, 482)

    def test_import_ctfd_challenge_uses_running_instance_access_as_target(self) -> None:
        document = SourceDocument(
            source_type="url_html",
            source_label="https://ctf.example.com/challenges",
            fetched_url="https://ctf.example.com/challenges",
            raw_text="Espilon CTF\nChallenges",
        )
        candidate = discover_text_challenges(
            SourceDocument(source_type="stdin", source_label="stdin", raw_text="Glitch The Wired 387 pts · 33 Solves")
        )[0]
        candidate = type(candidate)(
            title=candidate.title,
            text_block=candidate.text_block,
            challenge_id=33,
            category="hardware",
            points=candidate.points,
            solves=candidate.solves,
            source_label=candidate.source_label,
        )

        def _fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/api/v1/challenges/33"):
                return _FakeResponse(
                    """{"success": true, "data": {"id": 33, "name": "Glitch The Wired", "value": 387, "solves": 33, "description": "<p><strong>Glitch The Wired</strong></p><p>Glitch Lab: <code>tcp/&lt;host&gt;:3700</code></p>", "category": "hardware", "connection_info": null, "files": []}}""",
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers/current"):
                return _FakeResponse(
                    """{"success": true, "data": {"challenge": 33, "access": [{"name": "Glitch Lab", "url": "espilon.net 35597"}]}}""",
                    req.full_url,
                    "application/json",
                )
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        with patch("ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen):
            imported = import_ctfd_challenge(
                candidate,
                document,
                ImportRequest(
                    source="https://ctf.example.com/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge="Glitch The Wired",
                    list_only=False,
                    session_cookie="abc123",
                    cookie_file=None,
                    start_instance=False,
                ),
            )

        assert imported is not None
        self.assertEqual(imported.target_host, "espilon.net:35597")
        self.assertEqual(
            imported.import_metadata.get("instance_access"),
            [{"name": "Glitch Lab", "url": "espilon.net 35597"}],
        )

    def test_import_ctfd_challenge_can_start_instance(self) -> None:
        document = SourceDocument(
            source_type="url_html",
            source_label="https://ctf.example.com/challenges",
            fetched_url="https://ctf.example.com/challenges",
            raw_text="Espilon CTF\nChallenges",
            raw_html="""
                <html>
                  <head><script>window.init = {}; window.init['csrfNonce'] = "nonce-123";</script></head>
                  <body><div id="challenge-window"></div></body>
                </html>
            """,
        )
        candidate = discover_text_challenges(
            SourceDocument(source_type="stdin", source_label="stdin", raw_text="Glitch The Wired 387 pts · 33 Solves")
        )[0]
        candidate = type(candidate)(
            title=candidate.title,
            text_block=candidate.text_block,
            challenge_id=33,
            category="hardware",
            points=candidate.points,
            solves=candidate.solves,
            source_label=candidate.source_label,
        )

        seen_post_headers: dict[str, str | None] = {}
        poll_counter = {"current": 0}

        def _fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/api/v1/challenges/33"):
                return _FakeResponse(
                    """{"success": true, "data": {"id": 33, "name": "Glitch The Wired", "value": 387, "solves": 33, "description": "<p>Glitch Lab challenge.</p>", "category": "hardware", "connection_info": null, "files": []}}""",
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers/current"):
                poll_counter["current"] += 1
                if poll_counter["current"] == 1:
                    return _FakeResponse(
                        """{"success": true, "data": {"challenge": 12, "access": [{"name": "Old", "url": "espilon.net 12345"}]}}""",
                        req.full_url,
                        "application/json",
                    )
                return _FakeResponse(
                    """{"success": true, "data": {"challenge": 33, "access": [{"name": "Glitch Lab", "url": "espilon.net 35597"}]}}""",
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers"):
                seen_post_headers["cookie"] = req.headers.get("Cookie")
                seen_post_headers["csrf"] = req.headers.get("CSRF-Token") or req.headers.get("Csrf-token")
                seen_post_headers["body"] = req.data.decode("utf-8") if req.data else None
                return _FakeResponse(
                    """{"success": true, "data": {"access": []}}""",
                    req.full_url,
                    "application/json",
                )
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        with patch("ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen), patch(
            "ctf_destroyer.importers.ctfd.time.sleep"
        ):
            imported = import_ctfd_challenge(
                candidate,
                document,
                ImportRequest(
                    source="https://ctf.example.com/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge="Glitch The Wired",
                    list_only=False,
                    session_cookie="abc123",
                    cookie_file=None,
                    start_instance=True,
                ),
            )

        assert imported is not None
        self.assertEqual(imported.target_host, "espilon.net:35597")
        self.assertEqual(seen_post_headers["cookie"], "session=abc123")
        self.assertEqual(seen_post_headers["csrf"], "nonce-123")
        self.assertEqual(seen_post_headers["body"], '{"challenge": 33, "action": "start"}')
        self.assertEqual(imported.import_metadata.get("start_instance_result"), "started")

    def test_import_ctfd_challenge_warns_when_start_instance_has_no_csrf_token(self) -> None:
        document = SourceDocument(
            source_type="url_html",
            source_label="https://ctf.example.com/challenges",
            fetched_url="https://ctf.example.com/challenges",
            raw_text="Espilon CTF\nChallenges",
            raw_html="<html><body><div id='challenge-window'></div></body></html>",
        )
        candidate = discover_text_challenges(
            SourceDocument(source_type="stdin", source_label="stdin", raw_text="Glitch The Wired 387 pts · 33 Solves")
        )[0]
        candidate = type(candidate)(
            title=candidate.title,
            text_block=candidate.text_block,
            challenge_id=33,
            category="hardware",
            points=candidate.points,
            solves=candidate.solves,
            source_label=candidate.source_label,
        )

        def _fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/api/v1/challenges/33"):
                return _FakeResponse(
                    """{"success": true, "data": {"id": 33, "name": "Glitch The Wired", "value": 387, "solves": 33, "description": "<p>Glitch Lab challenge.</p>", "category": "hardware", "connection_info": null, "files": []}}""",
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers/current"):
                return _FakeResponse(
                    """{"success": true, "data": {"challenge": 12, "access": []}}""",
                    req.full_url,
                    "application/json",
                )
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        with patch("ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen):
            imported = import_ctfd_challenge(
                candidate,
                document,
                ImportRequest(
                    source="https://ctf.example.com/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge="Glitch The Wired",
                    list_only=False,
                    session_cookie="abc123",
                    cookie_file=None,
                    start_instance=True,
                ),
            )

        assert imported is not None
        self.assertIsNone(imported.target_host)
        self.assertIn("no CSRF token was found", " ".join(imported.warnings))
        self.assertEqual(imported.import_metadata.get("start_instance_result"), "failed")

    def test_import_ctfd_challenge_extracts_csrf_nonce_from_window_init_object(self) -> None:
        document = SourceDocument(
            source_type="url_html",
            source_label="https://ctf.example.com/challenges",
            fetched_url="https://ctf.example.com/challenges",
            raw_text="Espilon CTF\nChallenges",
            raw_html="""
                <html>
                  <head>
                    <script>
                      window.init = {
                        'urlRoot': "",
                        'csrfNonce': "nonce-quoted",
                        'userMode': "users",
                      }
                    </script>
                  </head>
                </html>
            """,
        )
        candidate = discover_text_challenges(
            SourceDocument(source_type="stdin", source_label="stdin", raw_text="Operating Room 500 pts · 0 Solves")
        )[0]
        candidate = type(candidate)(
            title=candidate.title,
            text_block=candidate.text_block,
            challenge_id=26,
            category="ot",
            points=candidate.points,
            solves=candidate.solves,
            source_label=candidate.source_label,
        )

        seen_csrf: dict[str, str | None] = {"value": None}
        seen_post: dict[str, bool] = {"done": False}

        def _fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/api/v1/challenges/26"):
                return _FakeResponse(
                    """{"success": true, "data": {"id": 26, "name": "Operating Room", "value": 500, "solves": 0, "description": "<p>Industrial control room.</p>", "category": "ot", "connection_info": null, "files": []}}""",
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers/current"):
                if not seen_post["done"]:
                    return _FakeResponse(
                        """{"success": true, "data": {"challenge": 1, "access": []}}""",
                        req.full_url,
                        "application/json",
                    )
                return _FakeResponse(
                    """{"success": true, "data": {"challenge": 26, "access": [{"name": "Modbus", "url": "espilon.net 35597"}]}}""",
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers"):
                seen_post["done"] = True
                seen_csrf["value"] = req.headers.get("CSRF-Token") or req.headers.get("Csrf-token")
                return _FakeResponse(
                    """{"success": true, "data": {"access": []}}""",
                    req.full_url,
                    "application/json",
                )
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        with patch("ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen), patch(
            "ctf_destroyer.importers.ctfd.time.sleep"
        ):
            imported = import_ctfd_challenge(
                candidate,
                document,
                ImportRequest(
                    source="https://ctf.example.com/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge="Operating Room",
                    list_only=False,
                    session_cookie="abc123",
                    cookie_file=None,
                    start_instance=True,
                ),
            )

        assert imported is not None
        self.assertEqual(seen_csrf["value"], "nonce-quoted")

    def test_import_ctfd_challenge_recovers_after_start_timeout(self) -> None:
        document = SourceDocument(
            source_type="url_html",
            source_label="https://ctf.example.com/challenges",
            fetched_url="https://ctf.example.com/challenges",
            raw_text="Espilon CTF\nChallenges",
            raw_html="""
                <html>
                  <head><script>window.init = { 'csrfNonce': "nonce-timeout" }</script></head>
                  <body></body>
                </html>
            """,
        )
        candidate = discover_text_challenges(
            SourceDocument(source_type="stdin", source_label="stdin", raw_text="Operating Room 500 pts · 0 Solves")
        )[0]
        candidate = type(candidate)(
            title=candidate.title,
            text_block=candidate.text_block,
            challenge_id=26,
            category="ot",
            points=candidate.points,
            solves=candidate.solves,
            source_label=candidate.source_label,
        )

        poll_counter = {"current": 0}

        def _fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/api/v1/challenges/26"):
                return _FakeResponse(
                    """{"success": true, "data": {"id": 26, "name": "Operating Room", "value": 500, "solves": 0, "description": "<p>Industrial control room.</p>", "category": "ot", "connection_info": null, "files": []}}""",
                    req.full_url,
                    "application/json",
                )
            if req.full_url.endswith("/api/v1/containers"):
                raise TimeoutError("timed out")
            if req.full_url.endswith("/api/v1/containers/current"):
                poll_counter["current"] += 1
                if poll_counter["current"] == 1:
                    return _FakeResponse(
                        """{"success": true, "data": {"challenge": 1, "access": []}}""",
                        req.full_url,
                        "application/json",
                    )
                return _FakeResponse(
                    """{"success": true, "data": {"challenge": 26, "access": [{"name": "Modbus", "url": "espilon.net 35597"}]}}""",
                    req.full_url,
                    "application/json",
                )
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        with patch("ctf_destroyer.importers.ctfd.request.urlopen", side_effect=_fake_urlopen), patch(
            "ctf_destroyer.importers.ctfd.time.sleep"
        ):
            imported = import_ctfd_challenge(
                candidate,
                document,
                ImportRequest(
                    source="https://ctf.example.com/challenges",
                    input_file=None,
                    output=None,
                    use_stdout=False,
                    review=False,
                    selected_challenge="Operating Room",
                    list_only=False,
                    session_cookie="abc123",
                    cookie_file=None,
                    start_instance=True,
                ),
            )

        assert imported is not None
        self.assertEqual(imported.target_host, "espilon.net:35597")
        self.assertEqual(imported.import_metadata.get("start_instance_result"), "started_after_timeout")


if __name__ == "__main__":
    unittest.main()
