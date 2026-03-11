import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ctf_destroyer.cli import _load_env_file, _normalize_challenge_payload, parse_args


class CliNormalizationTest(unittest.TestCase):
    def test_normalizes_target_and_files(self) -> None:
        payload = _normalize_challenge_payload(
            {
                "title": "Evaluative",
                "description": "Decode the rogue bot.",
                "category": "misc",
                "ip": "154.57.164.64",
                "port": 31748,
                "files": ["bot.py", "trace.txt"],
                "difficulty": "Very Easy",
                "points": 10,
            }
        )
        self.assertEqual(payload["challenge_name"], "Evaluative")
        self.assertEqual(payload["challenge_text"], "Decode the rogue bot.")
        self.assertEqual(payload["category_hint"], "misc")
        self.assertEqual(payload["target_host"], "154.57.164.64:31748")
        self.assertEqual(payload["artifact_paths"], ["bot.py", "trace.txt"])
        self.assertEqual(payload["challenge_metadata"]["difficulty"], "Very Easy")
        self.assertEqual(payload["challenge_metadata"]["points"], 10)

    def test_load_env_file_sets_defaults_without_overriding_existing_env(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "DISCORD_PARENT_CHANNEL_ID=1480705892918755544",
                        'DISCORD_BOT_TOKEN="secret-token"',
                    ]
                ),
                encoding="utf-8",
            )
            original_token = os.environ.get("DISCORD_BOT_TOKEN")
            try:
                os.environ["DISCORD_BOT_TOKEN"] = "already-set"
                os.environ.pop("DISCORD_PARENT_CHANNEL_ID", None)

                _load_env_file(env_path)

                self.assertEqual(os.environ["DISCORD_BOT_TOKEN"], "already-set")
                self.assertEqual(os.environ["DISCORD_PARENT_CHANNEL_ID"], "1480705892918755544")
            finally:
                if original_token is None:
                    os.environ.pop("DISCORD_BOT_TOKEN", None)
                else:
                    os.environ["DISCORD_BOT_TOKEN"] = original_token
                os.environ.pop("DISCORD_PARENT_CHANNEL_ID", None)

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
                args = parse_args(["--challenge-name", "X", "--challenge-text", "Y"])
                self.assertEqual(args.discord_parent_channel_id, "1480705892918755544")
                self.assertEqual(args.env_file.resolve(), env_path.resolve())
            finally:
                os.chdir(previous_cwd)
                if original_channel is None:
                    os.environ.pop("DISCORD_PARENT_CHANNEL_ID", None)
                else:
                    os.environ["DISCORD_PARENT_CHANNEL_ID"] = original_channel


if __name__ == "__main__":
    unittest.main()
