from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

from .challenges import normalize_challenge_payload
from .discord_sync import DiscordClient, DiscordThreadRef, load_thread_binding, resolve_discord_config
from .graph import build_initial_state, build_orchestrator, load_resume_context
from .writeups import generate_writeup_markdown
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
    challenge = normalize_challenge_payload(_load_challenge_file(args.challenge_file)) if args.challenge_file else {}
    source_root = args.challenge_file.resolve().parent if args.challenge_file else Path.cwd()
    challenge_name = args.challenge_name or challenge.get("challenge_name")
    challenge_text = args.challenge_text or challenge.get("challenge_text")
    category_hint = args.category_hint or challenge.get("category_hint")
    artifact_paths = list(challenge.get("artifact_paths", [])) + args.artifact
    target_host = challenge.get("target_host")
    challenge_metadata = dict(challenge.get("challenge_metadata", {}))

    if not challenge_name or not challenge_text:
        raise SystemExit("challenge name and challenge text are required.")
    _validate_challenge_actionability(challenge_name, target_host, challenge_metadata)

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
    _maybe_write_writeup(
        workspace=challenge_workspace,
        challenge_name=str(challenge_name),
        challenge_text=str(challenge_text),
        category_hint=category_hint,
        target_host=target_host,
        final_state=final_state,
        skills_root=args.skills_root,
        workers=workers,
        backend_sequence=backend_sequence,
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
    return normalize_challenge_payload(raw)


def _validate_challenge_actionability(
    challenge_name: str,
    target_host: str | None,
    challenge_metadata: dict[str, Any],
) -> None:
    import_metadata = challenge_metadata.get("import_metadata")
    if not isinstance(import_metadata, dict):
        return
    if target_host:
        return
    if not import_metadata.get("start_instance_requested"):
        return

    start_result = str(import_metadata.get("start_instance_result") or "unknown")
    warnings = import_metadata.get("warnings")
    detail_suffix = ""
    if isinstance(warnings, list) and warnings:
        detail_suffix = f" Details: {'; '.join(str(item) for item in warnings)}"
    raise SystemExit(
        f"Challenge '{challenge_name}' is not actionable: instance access is missing "
        f"after requested startup (start_instance_result={start_result}).{detail_suffix}"
    )


def _maybe_write_writeup(
    workspace: Path,
    challenge_name: str,
    challenge_text: str,
    category_hint: str | None,
    target_host: str | None,
    final_state: dict[str, Any],
    skills_root: Path | None = None,
    workers: dict[str, object] | None = None,
    backend_sequence: list[str] | None = None,
) -> None:
    if not final_state.get("solved"):
        return
    markdown = None
    if skills_root is not None and workers and backend_sequence:
        try:
            markdown = generate_writeup_markdown(
                workspace=workspace,
                skills_root=skills_root,
                workers=workers,
                backend_sequence=backend_sequence,
                challenge_name=challenge_name,
                challenge_text=challenge_text,
                category_hint=category_hint,
                target_host=target_host,
                final_state=final_state,
            )
        except Exception as exc:
            _warn(f"writeup worker failed: {exc}")

    writeup_path = workspace / "writeup.md"
    writeup_path.write_text(
        markdown
        or _render_writeup_markdown(
            challenge_name=challenge_name,
            challenge_text=challenge_text,
            category_hint=category_hint,
            target_host=target_host,
            final_state=final_state,
        ),
        encoding="utf-8",
    )


def _render_writeup_markdown(
    challenge_name: str,
    challenge_text: str,
    category_hint: str | None,
    target_host: str | None,
    final_state: dict[str, Any],
) -> str:
    history = [item for item in final_state.get("history", []) if isinstance(item, dict)]
    latest_output = final_state.get("latest_worker_output", {})
    latest_commands = list(latest_output.get("commands", [])) if isinstance(latest_output, dict) else []
    flag = str(final_state.get("final_flag") or "").strip()
    summary = _compact_text(str(final_state.get("final_summary", "")))
    approach_points = _build_writeup_approach_points(summary, history)
    commands = _collect_writeup_commands(history, latest_commands)
    script_snippets = _collect_writeup_scripts(history)

    lines = [
        "# Writeup",
        "",
        f"**Challenge:** {challenge_name}",
    ]
    if category_hint:
        lines.append(f"**Category:** `{category_hint}`")
    if target_host:
        lines.append(f"**Target:** `{target_host}`")
    if flag:
        lines.append(f"**Flag:** `{flag}`")

    lines.extend(
        [
            "",
            "## Challenge",
            "",
            _compact_text(challenge_text, limit=600),
            "",
            "## Resolution",
            "",
        ]
    )
    lines.extend(f"- {point}" for point in approach_points)

    lines.extend(
        [
            "",
            "## Solve",
            "",
        ]
    )
    if commands:
        lines.extend(
            [
                "```bash",
                *commands,
                "```",
            ]
        )
    else:
        lines.append("No shell commands were required to recover the flag.")

    if script_snippets:
        lines.extend(
            [
                "",
                "## Scripts",
                "",
            ]
        )
        for index, snippet in enumerate(script_snippets, 1):
            language = _guess_script_language(snippet)
            lines.extend(
                [
                    f"### Script {index}",
                    "",
                    f"```{language}",
                    snippet,
                    "```",
                    "",
                ]
            )
        if lines[-1] == "":
            lines.pop()

    return "\n".join(lines).strip() + "\n"


def _build_writeup_approach_points(summary: str, history: list[dict[str, Any]]) -> list[str]:
    points: list[str] = []
    if summary:
        points.append(summary)

    for attempt in history[-3:]:
        attempt_summary = _compact_text(str(attempt.get("summary", "")), limit=220)
        if attempt_summary and attempt_summary not in points:
            points.append(attempt_summary)
        for evidence in attempt.get("evidence", []):
            compact = _compact_text(str(evidence), limit=180)
            if compact and compact not in points:
                points.append(compact)
            if len(points) >= 5:
                return points
    return points[:5] or ["The challenge was solved and the final flag was validated by the worker."]


def _collect_writeup_commands(history: list[dict[str, Any]], latest_commands: list[str]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for command in latest_commands:
        compact = _compact_text(str(command), limit=500)
        if compact and compact not in seen:
            seen.add(compact)
            commands.append(compact)
    for attempt in reversed(history):
        for command in attempt.get("key_commands", []):
            compact = _compact_text(str(command), limit=500)
            if compact and compact not in seen:
                seen.add(compact)
                commands.append(compact)
            if len(commands) >= 8:
                return commands
    return commands


def _collect_writeup_scripts(history: list[dict[str, Any]]) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for attempt in reversed(history):
        for item in attempt.get("inline_scripts", []):
            if not isinstance(item, dict):
                continue
            snippet = _compact_text(str(item.get("snippet", "")), limit=1200, preserve_newlines=True)
            if not snippet or snippet in seen:
                continue
            seen.add(snippet)
            snippets.append(snippet)
            if len(snippets) >= 3:
                return snippets
    return snippets


def _compact_text(value: str, limit: int = 320, preserve_newlines: bool = False) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if preserve_newlines:
        lines = [" ".join(line.split()) for line in normalized.splitlines()]
        compact = "\n".join(line for line in lines if line)
    else:
        compact = " ".join(normalized.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def _guess_script_language(snippet: str) -> str:
    lowered = snippet.lstrip().lower()
    if lowered.startswith("import ") or lowered.startswith("from "):
        return "python"
    if lowered.startswith("#!/usr/bin/env python") or lowered.startswith("#!/usr/bin/python"):
        return "python"
    return "text"


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
