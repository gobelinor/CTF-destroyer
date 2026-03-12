from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import io
import json
import os
import unittest
from unittest.mock import patch

from ctf_destroyer.import_cli import main, parse_args
from ctf_destroyer.importers.models import DiscoveredChallenge, ImportedChallenge, SourceDocument


class ImportCliTest(unittest.TestCase):
    def test_parse_args_uses_default_dotenv_when_present(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            env_path = root / ".env"
            env_path.write_text("DISCORD_PARENT_CHANNEL_ID=1480705892918755544\n", encoding="utf-8")
            previous_cwd = Path.cwd()
            original_channel = os.environ.get("DISCORD_PARENT_CHANNEL_ID")
            try:
                os.chdir(root)
                os.environ.pop("DISCORD_PARENT_CHANNEL_ID", None)
                args = parse_args(["-"])
                self.assertEqual(args.env_file.resolve(), env_path.resolve())
            finally:
                os.chdir(previous_cwd)
                if original_channel is None:
                    os.environ.pop("DISCORD_PARENT_CHANNEL_ID", None)
                else:
                    os.environ["DISCORD_PARENT_CHANNEL_ID"] = original_channel

    def test_main_writes_json_from_input_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / "challenge.txt"
            output = root / "noise-cheap.json"
            source.write_text(
                "\n".join(
                    [
                        "Noise Cheap 90 pts · 337 Solves",
                        "A core part of making LWE secure is having the noise terms be larger than what lattice reduction algorithms can handle.",
                        "Connect at socket.cryptohack.org 13413",
                        "Challenge files:",
                        "  - 13413.py https://cryptohack.org/static/challenges/13413_0c0d299900953fdef5b48dafe6245d32.py",
                    ]
                ),
                encoding="utf-8",
            )

            stderr_buffer = io.StringIO()
            with redirect_stderr(stderr_buffer):
                status = main(["--input-file", str(source), "--output", str(output)])

            self.assertEqual(status, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "Noise Cheap")
            self.assertEqual(payload["target_host"], "socket.cryptohack.org:13413")
            self.assertIn("wrote", stderr_buffer.getvalue())

    def test_main_lists_multiple_candidates(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / "challenge-board.txt"
            source.write_text(
                "\n".join(
                    [
                        "Forbidden Fruit 150 pts · 754 Solves",
                        "Play at https://aes.cryptohack.org/forbidden_fruit",
                        "",
                        "Noise Cheap 90 pts · 337 Solves",
                        "Connect at socket.cryptohack.org 13413",
                    ]
                ),
                encoding="utf-8",
            )

            stdout_buffer = io.StringIO()
            with redirect_stdout(stdout_buffer):
                status = main(["--input-file", str(source), "--list"])

            self.assertEqual(status, 0)
            listing = stdout_buffer.getvalue()
            self.assertIn("Forbidden Fruit", listing)
            self.assertIn("Noise Cheap", listing)
            self.assertIn("[warn: no target, no files]", listing)
            self.assertIn("[warn: no files]", listing)

    def test_main_can_select_challenge_and_print_stdout(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / "challenge-board.txt"
            source.write_text(
                "\n".join(
                    [
                        "Forbidden Fruit 150 pts · 754 Solves",
                        "Play at https://aes.cryptohack.org/forbidden_fruit",
                        "",
                        "Noise Cheap 90 pts · 337 Solves",
                        "Connect at socket.cryptohack.org 13413",
                        "Challenge files:",
                        "  - 13413.py https://cryptohack.org/static/challenges/13413_0c0d299900953fdef5b48dafe6245d32.py",
                    ]
                ),
                encoding="utf-8",
            )

            stdout_buffer = io.StringIO()
            with redirect_stdout(stdout_buffer):
                status = main(
                    [
                        "--input-file",
                        str(source),
                        "--challenge",
                        "Noise Cheap",
                        "--stdout",
                    ]
                )

            self.assertEqual(status, 0)
            payload = json.loads(stdout_buffer.getvalue())
            self.assertEqual(payload["title"], "Noise Cheap")
            self.assertEqual(payload["points"], 90)

    def test_main_fails_explicitly_when_start_instance_does_not_yield_target_host(self) -> None:
        stderr_buffer = io.StringIO()
        stdout_buffer = io.StringIO()
        with patch(
            "ctf_destroyer.import_cli.load_source_document",
            return_value=SourceDocument(source_type="url_html", source_label="https://ctf.example.com/challenges", raw_text=""),
        ), patch(
            "ctf_destroyer.import_cli.try_discover_ctfd_challenges",
            return_value=[
                DiscoveredChallenge(
                    title="Operating Room",
                    text_block="Operating Room",
                    challenge_id=26,
                    source_label="https://ctf.example.com/challenges",
                )
            ],
        ), patch(
            "ctf_destroyer.import_cli.import_ctfd_challenge",
            return_value=ImportedChallenge(
                title="Operating Room",
                description="Control system challenge.",
                category="ot",
                target_host=None,
                import_metadata={"start_instance_result": "failed"},
                warnings=[
                    "Target host was not detected from the source.",
                    "Container start request timed out before access became available: timed out",
                ],
            ),
        ), redirect_stderr(stderr_buffer), redirect_stdout(stdout_buffer):
            status = main(
                [
                    "https://ctf.example.com/challenges",
                    "--challenge",
                    "Operating Room",
                    "--start-instance",
                    "--stdout",
                ]
            )

        self.assertEqual(status, 2)
        self.assertEqual(stdout_buffer.getvalue(), "")
        self.assertIn("failed to acquire instance access", stderr_buffer.getvalue())
        self.assertIn("start_instance_result=failed", stderr_buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
