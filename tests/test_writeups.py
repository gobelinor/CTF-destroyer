import os
import unittest
from unittest.mock import patch

from ctf_destroyer.workers import ClaudeWorker, CodexWorker
from ctf_destroyer.writeups import select_writeup_backend


class WriteupWorkerSelectionTest(unittest.TestCase):
    def test_select_writeup_backend_prefers_active_real_backend(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            workers = {
                "codex": CodexWorker(),
                "claude": ClaudeWorker(),
                "mock": object(),
            }

        backend = select_writeup_backend(
            workers=workers,
            backend_sequence=["codex", "claude"],
            final_state={
                "active_backend": "claude",
                "history": [
                    {"backend": "codex"},
                ],
            },
        )

        self.assertEqual(backend, "claude")

    def test_select_writeup_backend_ignores_mock_only_runs(self) -> None:
        backend = select_writeup_backend(
            workers={"mock": object()},
            backend_sequence=["mock"],
            final_state={
                "active_backend": "mock",
                "history": [
                    {"backend": "mock"},
                ],
            },
        )

        self.assertIsNone(backend)


if __name__ == "__main__":
    unittest.main()
