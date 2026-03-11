from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Callable

from .discord_sync import DiscordClient, DiscordThreadRef, load_thread_binding, resolve_discord_config
from .graph import build_initial_state, build_orchestrator, load_resume_context
from .workers import build_worker_pool
from .workspace import prepare_challenge_workspace


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv = list(argv or sys.argv[1:])
    env_file = _extract_env_file_arg(argv)
    _load_env_file(env_file)

    parser = argparse.ArgumentParser(description="LangGraph CTF orchestrator PoC.")
    parser.add_argument("--challenge-file", type=Path, help="JSON file describing the challenge.")
    parser.add_argument("--challenge-name", help="Override challenge name.")
    parser.add_argument("--challenge-text", help="Override challenge text.")
    parser.add_argument("--category-hint", help="Optional explicit challenge category.")
    parser.add_argument("--artifact", action="append", default=[], help="Artifact path. Repeatable.")
    parser.add_argument(
        "--backend-sequence",
        default="mock",
        help="Comma-separated worker order, for example 'codex,claude'.",
    )
    parser.add_argument("--max-attempts", type=int, default=4, help="Maximum specialist attempts.")
    parser.add_argument("--skills-root", type=Path, default=Path("skills"), help="Skills directory.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root under which a dedicated challenge directory will be created.",
    )
    parser.add_argument("--thread-id", default="ctf-poc", help="LangGraph thread ID.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=env_file,
        help="Optional .env file loaded before parsing other options. Defaults to .env when present.",
    )
    parser.add_argument(
        "--discord-bot-token",
        default=os.getenv("DISCORD_BOT_TOKEN"),
        help="Discord bot token. Defaults to DISCORD_BOT_TOKEN.",
    )
    parser.add_argument(
        "--discord-parent-channel-id",
        default=os.getenv("DISCORD_PARENT_CHANNEL_ID"),
        help="Discord channel ID used to create challenge threads.",
    )
    parser.add_argument(
        "--discord-auto-archive-duration",
        type=int,
        default=int(os.getenv("DISCORD_AUTO_ARCHIVE_DURATION", "10080")),
        help="Discord thread auto archive duration in minutes: 60, 1440, 4320 or 10080.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    challenge = _normalize_challenge_payload(_load_challenge_file(args.challenge_file)) if args.challenge_file else {}
    source_root = args.challenge_file.resolve().parent if args.challenge_file else Path.cwd()
    challenge_name = args.challenge_name or challenge.get("challenge_name")
    challenge_text = args.challenge_text or challenge.get("challenge_text")
    category_hint = args.category_hint or challenge.get("category_hint")
    artifact_paths = list(challenge.get("artifact_paths", [])) + args.artifact
    target_host = challenge.get("target_host")
    challenge_metadata = dict(challenge.get("challenge_metadata", {}))

    if not challenge_name or not challenge_text:
        raise SystemExit("challenge name and challenge text are required.")

    challenge_workspace, staged_artifacts = prepare_challenge_workspace(
        workspace_root=args.workspace,
        challenge_name=challenge_name,
        artifact_paths=artifact_paths,
        challenge_payload={
            "challenge_name": challenge_name,
            "challenge_text": challenge_text,
            "category_hint": category_hint,
            "target_host": target_host,
            "challenge_metadata": challenge_metadata,
            "artifact_paths": artifact_paths,
        },
        source_root=source_root,
    )
    try:
        discord_config = resolve_discord_config(
            bot_token=args.discord_bot_token,
            parent_channel_id=args.discord_parent_channel_id,
            auto_archive_duration=args.discord_auto_archive_duration,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    discord_client = DiscordClient(discord_config) if discord_config else None
    discord_thread = None
    if discord_client is not None:
        try:
            existing_thread = load_thread_binding(challenge_workspace)
            if existing_thread is not None:
                discord_thread = existing_thread
                _info(
                    "discord thread reused: "
                    f"{discord_thread.thread_name} ({discord_thread.thread_id}) "
                    f"in parent {discord_thread.parent_channel_id}"
                )
            else:
                discord_thread = discord_client.ensure_challenge_thread(
                    workspace=challenge_workspace,
                    challenge_name=challenge_name,
                    challenge_text=challenge_text,
                    category_hint=category_hint,
                    target_host=target_host,
                    challenge_metadata=challenge_metadata,
                    artifact_paths=staged_artifacts,
                )
                _info(
                    "discord thread created: "
                    f"{discord_thread.thread_name} ({discord_thread.thread_id}) "
                    f"in parent {discord_thread.parent_channel_id}"
                )
        except Exception as exc:
            _warn(f"discord thread setup failed: {exc}")
            discord_client = None

    backend_sequence = [item.strip() for item in args.backend_sequence.split(",") if item.strip()]
    workers = build_worker_pool(backend_sequence)
    graph = build_orchestrator(
        args.skills_root,
        workers,
        event_handler=_build_discord_event_handler(discord_client, discord_thread),
    )
    resumed_history, resumed_memory = load_resume_context(challenge_workspace)
    if resumed_history:
        _info(
            "resume context loaded: "
            f"{len(resumed_history)} prior attempt(s) from {challenge_workspace / '.runs'}"
        )
    initial_state = build_initial_state(
        challenge_name=challenge_name,
        challenge_text=challenge_text,
        workspace=challenge_workspace,
        backend_sequence=backend_sequence,
        category_hint=category_hint,
        target_host=target_host,
        challenge_metadata=challenge_metadata,
        artifact_paths=staged_artifacts,
        history=resumed_history,
        working_memory=resumed_memory,
        max_attempts=args.max_attempts,
    )
    final_state = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": args.thread_id}},
    )
    if discord_client is not None and discord_thread is not None:
        try:
            discord_client.publish_final(discord_thread, final_state)
            _info(
                "discord final update posted: "
                f"{discord_thread.thread_name} ({discord_thread.thread_id})"
            )
        except Exception as exc:
            _warn(f"discord final update failed: {exc}")
    print(json.dumps(final_state, indent=2))
    return 0


def _load_challenge_file(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_challenge_payload(raw: dict[str, object]) -> dict[str, object]:
    challenge_name = _coalesce_str(raw, "challenge_name", "title", "name")
    challenge_text = _coalesce_str(
        raw,
        "challenge_text",
        "description",
        "scenario",
        "challenge_scenario",
        "prompt",
    )
    category_hint = _coalesce_str(raw, "category_hint", "category")
    target_host = _coalesce_target_host(raw)
    artifact_paths = _coalesce_artifacts(raw)
    challenge_metadata = {
        key: value
        for key, value in raw.items()
        if key
        not in {
            "challenge_name",
            "title",
            "name",
            "challenge_text",
            "description",
            "scenario",
            "challenge_scenario",
            "prompt",
            "category_hint",
            "category",
            "artifact_paths",
            "artifacts",
            "files",
            "target_host",
            "target",
            "ip",
            "port",
        }
    }
    return {
        "challenge_name": challenge_name,
        "challenge_text": challenge_text,
        "category_hint": category_hint,
        "target_host": target_host,
        "artifact_paths": artifact_paths,
        "challenge_metadata": challenge_metadata,
    }


def _coalesce_str(raw: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coalesce_target_host(raw: dict[str, object]) -> str | None:
    direct = _coalesce_str(raw, "target_host", "target")
    if direct:
        return direct

    ip = _coalesce_str(raw, "ip")
    port = raw.get("port")
    if not ip:
        return None
    if isinstance(port, int):
        return f"{ip}:{port}"
    if isinstance(port, str) and port.strip():
        return f"{ip}:{port.strip()}"
    return ip


def _coalesce_artifacts(raw: dict[str, object]) -> list[str]:
    for key in ("artifact_paths", "artifacts", "files"):
        value = raw.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    return []


def _extract_env_file_arg(argv: list[str]) -> Path | None:
    default_env_file = Path(".env")
    if "--env-file" in argv:
        index = argv.index("--env-file")
        if index + 1 >= len(argv):
            raise SystemExit("--env-file requires a path value.")
        return Path(argv[index + 1]).expanduser().resolve()

    for item in argv:
        if item.startswith("--env-file="):
            _, value = item.split("=", 1)
            if not value:
                raise SystemExit("--env-file requires a path value.")
            return Path(value).expanduser().resolve()

    if default_env_file.exists():
        return default_env_file.resolve()
    return None


def _load_env_file(path: Path | None) -> None:
    if path is None:
        return
    if not path.exists():
        raise SystemExit(f"env file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, _parse_env_value(value.strip()))


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _build_discord_event_handler(
    discord_client: DiscordClient | None,
    discord_thread: DiscordThreadRef | None,
) -> Callable[[str, dict[str, object]], None] | None:
    if discord_client is None or discord_thread is None:
        return None

    def handler(event_type: str, payload: dict[str, object]) -> None:
        try:
            if event_type == "route_resolved":
                discord_client.publish_route(
                    discord_thread,
                    category=str(payload.get("category", "unknown")),
                    reason=str(payload.get("category_reason", "")),
                    skill_slug=str(payload.get("specialist_skill_slug", "")),
                )
            elif event_type == "attempt_completed":
                discord_client.publish_attempt(discord_thread, payload)
        except Exception as exc:
            _warn(f"discord event '{event_type}' failed: {exc}")

    return handler


def _warn(message: str) -> None:
    print(f"[warning] {message}", file=sys.stderr)


def _info(message: str) -> None:
    print(f"[info] {message}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
