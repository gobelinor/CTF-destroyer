from __future__ import annotations

import json
from pathlib import Path
import subprocess
import textwrap
from typing import Any

from .skills import Skill, load_skills
from .workers import ClaudeWorker, CodexWorker, WorkerBackend, _extract_json


WRITEUP_SKILL_SLUG = "ctf-writeup-writer"
WRITEUP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "markdown": {"type": "string"},
    },
    "required": ["markdown"],
    "additionalProperties": False,
}


def generate_writeup_markdown(
    *,
    workspace: Path,
    skills_root: Path,
    workers: dict[str, WorkerBackend],
    backend_sequence: list[str],
    challenge_name: str,
    challenge_text: str,
    category_hint: str | None,
    target_host: str | None,
    final_state: dict[str, Any],
) -> str | None:
    if not final_state.get("solved"):
        return None

    backend_name = select_writeup_backend(
        workers=workers,
        backend_sequence=backend_sequence,
        final_state=final_state,
    )
    if backend_name is None:
        return None

    skill = _load_writeup_skill(skills_root)
    if skill is None:
        return None

    prompt = _build_writeup_prompt(
        challenge_name=challenge_name,
        challenge_text=challenge_text,
        category_hint=category_hint,
        target_host=target_host,
        final_state=final_state,
        skill=skill,
    )
    run_dir = workspace / ".runs" / "writeup"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / f"{backend_name}-prompt.txt"
    schema_path = run_dir / f"{backend_name}-schema.json"
    output_path = run_dir / f"{backend_name}-output.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_text(json.dumps(WRITEUP_SCHEMA, indent=2), encoding="utf-8")

    worker = workers[backend_name]
    if isinstance(worker, CodexWorker):
        return _generate_with_codex(worker, workspace, prompt, schema_path, output_path)
    if isinstance(worker, ClaudeWorker):
        return _generate_with_claude(worker, workspace, prompt, schema_path, output_path)
    return None


def select_writeup_backend(
    *,
    workers: dict[str, WorkerBackend],
    backend_sequence: list[str],
    final_state: dict[str, Any],
) -> str | None:
    candidates: list[str] = []

    active_backend = final_state.get("active_backend")
    if isinstance(active_backend, str):
        candidates.append(active_backend)

    history = final_state.get("history", [])
    if isinstance(history, list):
        for attempt in reversed(history):
            if not isinstance(attempt, dict):
                continue
            backend = attempt.get("backend")
            if isinstance(backend, str):
                candidates.append(backend)

    candidates.extend(backend_sequence)

    seen: set[str] = set()
    for backend_name in candidates:
        if not backend_name or backend_name in seen:
            continue
        seen.add(backend_name)
        worker = workers.get(backend_name)
        if isinstance(worker, (CodexWorker, ClaudeWorker)):
            return backend_name
    return None


def _load_writeup_skill(skills_root: Path) -> Skill | None:
    return load_skills(skills_root).get(WRITEUP_SKILL_SLUG)


def _build_writeup_prompt(
    *,
    challenge_name: str,
    challenge_text: str,
    category_hint: str | None,
    target_host: str | None,
    final_state: dict[str, Any],
    skill: Skill,
) -> str:
    history = final_state.get("history", [])
    latest_output = final_state.get("latest_worker_output", {})
    final_flag = str(final_state.get("final_flag") or "").strip()
    final_summary = _compact_text(str(final_state.get("final_summary", "")), limit=500)

    compact_history = (
        json.dumps(_compact_history(history), indent=2, ensure_ascii=False)
        if isinstance(history, list)
        else "[]"
    )
    latest_payload = (
        json.dumps(_compact_latest_output(latest_output), indent=2, ensure_ascii=False)
        if isinstance(latest_output, dict)
        else "{}"
    )
    commands = json.dumps(_collect_commands(history, latest_output), indent=2, ensure_ascii=False)
    scripts = json.dumps(_collect_inline_scripts(history), indent=2, ensure_ascii=False)

    return textwrap.dedent(
        f"""
        Challenge name: {challenge_name}
        Category: {category_hint or "unknown"}
        Target host: {target_host or "none"}
        Final flag: {final_flag or "unknown"}
        Final summary: {final_summary or "none"}

        Challenge text:
        {challenge_text}

        Latest worker output:
        {latest_payload}

        Compact attempt history:
        {compact_history}

        Collected commands:
        {commands}

        Inline scripts:
        {scripts}

        Specialist skill: {skill.name}
        Skill description: {skill.description}

        Skill instructions:
        {skill.instructions}

        Objective:
        - Write a concise, clear, easy-to-follow CTF writeup in Markdown.
        - Explain the actual solve path, not every dead end.
        - Keep the tone dry and slightly amused; one or two mildly contemptuous lines about the broken design are acceptable.
        - The contempt must target the vulnerability, misuse or challenge design mistake, never the reader.
        - Include exact commands in `## Solve`.
        - Include a short `## Scripts` section only if a script materially helped solve the challenge.
        - Do not fabricate commands, scripts or reasoning not grounded in the provided history.
        - Return JSON that matches the schema exactly.
        """
    ).strip()


def _generate_with_codex(
    worker: CodexWorker,
    workspace: Path,
    prompt: str,
    schema_path: Path,
    output_path: Path,
) -> str | None:
    command = [
        "codex",
        "-a",
        worker.approval_policy,
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        worker.sandbox,
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
        "-C",
        str(workspace),
    ]
    if worker.model:
        command[1:1] = ["-m", worker.model]
    command = command + worker.extra_args + ["-"]
    completed = subprocess.run(
        command,
        cwd=workspace,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=min(worker.timeout_seconds, 300),
        check=False,
    )
    raw_output = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
    if not raw_output:
        raw_output = completed.stdout.strip() or completed.stderr.strip()
    return _extract_markdown(raw_output)


def _generate_with_claude(
    worker: ClaudeWorker,
    workspace: Path,
    prompt: str,
    schema_path: Path,
    output_path: Path,
) -> str | None:
    command = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--json-schema",
        schema_path.read_text(encoding="utf-8"),
        "--permission-mode",
        worker.permission_mode,
    ]
    if worker.model:
        command.extend(["--model", worker.model])
    command.extend(worker.extra_args)
    command.append(prompt)
    completed = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=min(worker.timeout_seconds, 300),
        check=False,
    )
    raw_output = completed.stdout.strip() or completed.stderr.strip()
    if raw_output:
        output_path.write_text(raw_output, encoding="utf-8")
    return _extract_markdown(raw_output)


def _extract_markdown(raw_output: str) -> str | None:
    if not raw_output.strip():
        return None
    payload = _extract_json(raw_output)
    if not isinstance(payload, dict):
        return None
    markdown = str(payload.get("markdown", "")).strip()
    if not markdown:
        return None
    return markdown if markdown.endswith("\n") else f"{markdown}\n"


def _compact_history(history: Any, limit: int = 4) -> list[dict[str, Any]]:
    if not isinstance(history, list):
        return []

    items: list[dict[str, Any]] = []
    for attempt in history[-limit:]:
        if not isinstance(attempt, dict):
            continue
        item: dict[str, Any] = {}
        for key in ("attempt", "backend", "status"):
            value = attempt.get(key)
            if value not in (None, ""):
                item[key] = value
        summary = _compact_text(str(attempt.get("summary", "")), limit=260)
        if summary:
            item["summary"] = summary
        evidence = [
            _compact_text(str(entry), limit=180)
            for entry in list(attempt.get("evidence", []))[:4]
            if _compact_text(str(entry), limit=180)
        ]
        if evidence:
            item["evidence"] = evidence
        commands = [
            _compact_text(str(entry), limit=220)
            for entry in list(attempt.get("key_commands", []))[:6]
            if _compact_text(str(entry), limit=220)
        ]
        if commands:
            item["key_commands"] = commands
        scripts = _collect_inline_scripts([attempt], limit=2)
        if scripts:
            item["inline_scripts"] = scripts
        if item:
            items.append(item)
    return items


def _compact_latest_output(latest_output: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("backend", "status", "summary", "next_step", "flag"):
        value = latest_output.get(key)
        if value in (None, ""):
            continue
        if key in {"summary", "next_step"}:
            compact[key] = _compact_text(str(value), limit=280)
        else:
            compact[key] = value

    evidence = [
        _compact_text(str(entry), limit=180)
        for entry in list(latest_output.get("evidence", []))[:4]
        if _compact_text(str(entry), limit=180)
    ]
    if evidence:
        compact["evidence"] = evidence
    commands = _collect_commands([], latest_output)
    if commands:
        compact["commands"] = commands
    return compact


def _collect_commands(history: Any, latest_output: Any, limit: int = 10) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()

    if isinstance(latest_output, dict):
        for command in list(latest_output.get("commands", [])):
            compact = _compact_text(str(command), limit=320)
            if compact and compact not in seen:
                seen.add(compact)
                commands.append(compact)
                if len(commands) >= limit:
                    return commands

    if isinstance(history, list):
        for attempt in reversed(history):
            if not isinstance(attempt, dict):
                continue
            for command in list(attempt.get("key_commands", [])):
                compact = _compact_text(str(command), limit=320)
                if compact and compact not in seen:
                    seen.add(compact)
                    commands.append(compact)
                    if len(commands) >= limit:
                        return commands
    return commands


def _collect_inline_scripts(history: Any, limit: int = 3) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    if not isinstance(history, list):
        return snippets
    for attempt in reversed(history):
        if not isinstance(attempt, dict):
            continue
        for item in list(attempt.get("inline_scripts", [])):
            if not isinstance(item, dict):
                continue
            snippet = _compact_text(str(item.get("snippet", "")), limit=1200, preserve_newlines=True)
            if not snippet or snippet in seen:
                continue
            seen.add(snippet)
            snippets.append(snippet)
            if len(snippets) >= limit:
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
