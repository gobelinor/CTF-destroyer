from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from ctf_destroyer.discord_sync import DiscordClient, DiscordConfig, resolve_discord_config


class FakeDiscordTransport:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, object] | None]] = []

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.requests.append((method, path, payload))
        if not self.responses:
            return {}
        return self.responses.pop(0)


class DiscordSyncTest(unittest.TestCase):
    def test_resolve_discord_config_requires_token_and_channel(self) -> None:
        with self.assertRaises(ValueError):
            resolve_discord_config(bot_token="token", parent_channel_id=None)

        config = resolve_discord_config(
            bot_token="token",
            parent_channel_id="123456",
        )
        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.parent_channel_id, "123456")

    def test_ensure_challenge_thread_creates_text_thread_and_persists_binding(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "challenge.json").write_text('{"challenge_name":"Discord Test"}', encoding="utf-8")
            client = DiscordClient(
                DiscordConfig(
                    bot_token="token",
                    parent_channel_id="999",
                ),
                transport=FakeDiscordTransport([{"id": "thread-1", "name": "Discord Test"}, {"id": "message-1"}]),
            )

            binding = client.ensure_challenge_thread(
                workspace=workspace,
                challenge_name="Discord Test",
                challenge_text="Investigate the service and recover the flag.",
                category_hint="web",
                target_host="10.10.10.10:31337",
                artifact_paths=["artifacts/note.txt"],
                challenge_metadata={"points": 50},
            )

            self.assertEqual(binding.thread_id, "thread-1")
            request_method, request_path, payload = client.transport.requests[0]
            self.assertEqual((request_method, request_path), ("POST", "/channels/999/threads"))
            self.assertEqual(payload["type"], 11)
            self.assertEqual(client.transport.requests[1][1], "/channels/thread-1/messages")

            manifest = json.loads((workspace / "challenge.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["discord_thread"]["thread_id"], "thread-1")

            same_binding = client.ensure_challenge_thread(
                workspace=workspace,
                challenge_name="Discord Test",
                challenge_text="ignored",
                category_hint=None,
                target_host=None,
            )
            self.assertEqual(same_binding.thread_id, "thread-1")
            self.assertEqual(len(client.transport.requests), 2)

    def test_ensure_challenge_thread_creates_text_thread_then_posts_message(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "challenge.json").write_text('{"challenge_name":"Text Thread"}', encoding="utf-8")
            transport = FakeDiscordTransport(
                [
                    {"id": "thread-2", "name": "Text Thread"},
                    {"id": "message-1"},
                ]
            )
            client = DiscordClient(
                DiscordConfig(
                    bot_token="token",
                    parent_channel_id="321",
                ),
                transport=transport,
            )

            binding = client.ensure_challenge_thread(
                workspace=workspace,
                challenge_name="Text Thread",
                challenge_text="Short description.",
                category_hint=None,
                target_host=None,
            )

            self.assertEqual(binding.thread_id, "thread-2")
            self.assertEqual(transport.requests[0][1], "/channels/321/threads")
            self.assertEqual(transport.requests[0][2]["type"], 11)
            self.assertEqual(transport.requests[1][1], "/channels/thread-2/messages")


if __name__ == "__main__":
    unittest.main()
