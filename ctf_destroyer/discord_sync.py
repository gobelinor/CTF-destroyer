from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Protocol
from urllib import error, request

from .workspace import merge_challenge_manifest


DISCORD_API_BASE_URL = "https://discord.com/api/v10"
MAX_THREAD_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 1900
THREAD_TYPE_BY_NAME = {
    "public": 11,
    "private": 12,
}


@dataclass(frozen=True)
class DiscordConfig:
    bot_token: str
    parent_channel_id: str
    auto_archive_duration: int = 10080


@dataclass(frozen=True)
class DiscordThreadRef:
    thread_id: str
    thread_name: str
    parent_channel_id: str


class DiscordTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


class DiscordApiError(RuntimeError):
    pass


class DiscordHttpTransport:
    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "User-Agent": "ctf-destroyer/0.1",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        req = request.Request(
            f"{DISCORD_API_BASE_URL}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req) as response:
                text = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_text = exc.read().decode("utf-8", errors="replace")
            raise DiscordApiError(f"Discord API returned HTTP {exc.code}: {error_text}") from exc
        except error.URLError as exc:
            raise DiscordApiError(f"Unable to reach Discord API: {exc.reason}") from exc

        if not text:
            return {}
        payload_data = json.loads(text)
        if not isinstance(payload_data, dict):
            raise DiscordApiError("Discord API returned an unexpected payload.")
        return payload_data


class DiscordClient:
    def __init__(
        self,
        config: DiscordConfig,
        transport: DiscordTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or DiscordHttpTransport(config.bot_token)

    def ensure_challenge_thread(
        self,
        workspace: Path,
        challenge_name: str,
        challenge_text: str,
        category_hint: str | None,
        target_host: str | None,
        challenge_metadata: dict[str, Any] | None = None,
        artifact_paths: list[str] | None = None,
    ) -> DiscordThreadRef:
        existing = load_thread_binding(workspace)
        if existing is not None:
            return existing

        thread_name = _normalize_thread_name(challenge_name)
        challenge_excerpt = _truncate(challenge_text.strip(), 900)
        artifacts = list(artifact_paths or [])
        metadata = dict(challenge_metadata or {})
        initial_message = _render_initial_message(
            challenge_name=challenge_name,
            challenge_excerpt=challenge_excerpt,
            workspace=workspace,
            category_hint=category_hint,
            target_host=target_host,
            artifact_paths=artifacts,
            challenge_metadata=metadata,
        )

        created = self.transport.request(
            "POST",
            f"/channels/{self.config.parent_channel_id}/threads",
            payload={
                "name": thread_name,
                "auto_archive_duration": self.config.auto_archive_duration,
                "type": THREAD_TYPE_BY_NAME["public"],
            },
        )
        thread_id = str(created["id"])
        self.post_message(thread_id, initial_message)

        binding = DiscordThreadRef(
            thread_id=thread_id,
            thread_name=str(created.get("name", thread_name)),
            parent_channel_id=self.config.parent_channel_id,
        )
        save_thread_binding(workspace, binding)
        return binding

    def publish_route(
        self,
        thread: DiscordThreadRef,
        category: str,
        reason: str,
        skill_slug: str,
    ) -> None:
        content = "\n".join(
            [
                "Routing completed.",
                f"Category: `{category}`",
                f"Skill: `{skill_slug}`",
                f"Reason: {_truncate(reason, 600)}",
            ]
        )
        self.post_message(thread.thread_id, content)

    def publish_attempt(self, thread: DiscordThreadRef, attempt: dict[str, Any]) -> None:
        lines = [
            f"Attempt {attempt['attempt']} via `{attempt['backend']}`",
            f"Status: `{attempt['status']}`",
            f"Summary: {_truncate(str(attempt.get('summary', '')), 700)}",
            f"Next step: {_truncate(str(attempt.get('next_step', '')), 500)}",
        ]
        flag = attempt.get("flag")
        if flag:
            lines.append(f"Flag candidate: `{flag}`")
        commands = list(attempt.get("commands", []))[:5]
        if commands:
            lines.append("Commands:")
            lines.extend(f"- `{_truncate(command, 180)}`" for command in commands)
        self.post_message(thread.thread_id, "\n".join(lines))

    def publish_final(self, thread: DiscordThreadRef, final_state: dict[str, Any]) -> None:
        lines = [
            "Run completed.",
            f"Solved: `{'yes' if final_state.get('solved') else 'no'}`",
            f"Stop reason: `{final_state.get('stop_reason', 'unknown')}`",
            f"Attempts: `{final_state.get('attempts', 0)}`",
            f"Summary: {_truncate(str(final_state.get('final_summary', '')), 700)}",
        ]
        final_flag = final_state.get("final_flag")
        if final_flag:
            lines.append(f"Final flag: `{final_flag}`")
        self.post_message(thread.thread_id, "\n".join(lines))

    def post_message(self, thread_id: str, content: str) -> None:
        for chunk in _chunk_message(content):
            self.transport.request(
                "POST",
                f"/channels/{thread_id}/messages",
                payload={"content": chunk},
            )


def load_thread_binding(workspace: Path) -> DiscordThreadRef | None:
    state_path = workspace / ".discord-thread.json"
    if not state_path.exists():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return DiscordThreadRef(
        thread_id=str(payload["thread_id"]),
        thread_name=str(payload["thread_name"]),
        parent_channel_id=str(payload["parent_channel_id"]),
    )


def resolve_discord_config(
    *,
    bot_token: str | None,
    parent_channel_id: str | None,
    auto_archive_duration: int = 10080,
) -> DiscordConfig | None:
    token = (bot_token or "").strip()
    channel_id = (parent_channel_id or "").strip()
    if not token and not channel_id:
        return None
    if not token or not channel_id:
        raise ValueError("Discord integration requires both a bot token and a parent channel ID.")
    if auto_archive_duration not in {60, 1440, 4320, 10080}:
        raise ValueError("discord auto archive duration must be one of 60, 1440, 4320 or 10080.")

    return DiscordConfig(
        bot_token=token,
        parent_channel_id=channel_id,
        auto_archive_duration=auto_archive_duration,
    )


def save_thread_binding(workspace: Path, binding: DiscordThreadRef) -> None:
    state_path = workspace / ".discord-thread.json"
    state_path.write_text(
        json.dumps(asdict(binding), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    merge_challenge_manifest(
        workspace,
        {
            "discord_thread": {
                "thread_id": binding.thread_id,
                "thread_name": binding.thread_name,
                "parent_channel_id": binding.parent_channel_id,
            }
        },
    )


def _chunk_message(content: str) -> list[str]:
    stripped = content.strip()
    if not stripped:
        return []

    chunks: list[str] = []
    current = ""
    for line in stripped.splitlines():
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) <= MAX_MESSAGE_LENGTH:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(line) > MAX_MESSAGE_LENGTH:
            chunks.append(line[:MAX_MESSAGE_LENGTH])
            line = line[MAX_MESSAGE_LENGTH:]
        current = line
    if current:
        chunks.append(current)
    return chunks


def _normalize_thread_name(value: str) -> str:
    name = " ".join(value.split()).strip()
    if not name:
        name = "challenge"
    return name[:MAX_THREAD_NAME_LENGTH]


def _render_initial_message(
    *,
    challenge_name: str,
    challenge_excerpt: str,
    workspace: Path,
    category_hint: str | None,
    target_host: str | None,
    artifact_paths: list[str],
    challenge_metadata: dict[str, Any],
) -> str:
    lines = [
        f"Challenge: **{challenge_name}**",
        f"Workspace: `{workspace}`",
        f"Category hint: `{category_hint or 'none'}`",
        f"Target host: `{target_host or 'none'}`",
    ]
    if artifact_paths:
        lines.append("Artifacts:")
        lines.extend(f"- `{path}`" for path in artifact_paths[:10])
    if challenge_metadata:
        metadata_summary = ", ".join(
            f"{key}={value}" for key, value in list(challenge_metadata.items())[:5]
        )
        lines.append(f"Metadata: `{_truncate(metadata_summary, 300)}`")
    lines.append("Challenge text:")
    lines.append(f"```text\n{challenge_excerpt}\n```")
    return "\n".join(lines)


def _truncate(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."
