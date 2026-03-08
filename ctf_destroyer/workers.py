from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import textwrap
import threading
from typing import Any

from .skills import Skill


RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["solved", "needs_retry", "blocked"],
        },
        "summary": {"type": "string"},
        "next_step": {"type": "string"},
        "flag": {"type": ["string", "null"]},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "commands": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "summary", "next_step", "flag", "evidence", "commands"],
    "additionalProperties": False,
}

FLAG_RE = re.compile(r"(?:flag|ctf)\{[^}\n]+\}", re.IGNORECASE)


@dataclass(frozen=True)
class WorkerRequest:
    attempt_index: int
    challenge_name: str
    challenge_text: str
    challenge_category: str | None
    target_host: str | None
    metadata: dict[str, Any]
    artifact_paths: list[str]
    workspace: Path
    skill: Skill
    prior_attempts: list[dict[str, Any]]


@dataclass(frozen=True)
class WorkerResult:
    backend: str
    status: str
    summary: str
    next_step: str
    flag: str | None = None
    evidence: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    command_events: list[dict[str, Any]] = field(default_factory=list)
    event_log_path: str = ""
    raw_output: str = ""

    def as_state_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WorkerResult":
        return cls(
            backend=payload["backend"],
            status=payload["status"],
            summary=payload.get("summary", ""),
            next_step=payload.get("next_step", ""),
            flag=payload.get("flag"),
            evidence=list(payload.get("evidence", [])),
            commands=list(payload.get("commands", [])),
            command_events=list(payload.get("command_events", [])),
            event_log_path=payload.get("event_log_path", ""),
            raw_output=payload.get("raw_output", ""),
        )


class WorkerBackend(ABC):
    name: str

    @abstractmethod
    def invoke(self, request: WorkerRequest) -> WorkerResult:
        raise NotImplementedError


class MockWorker(WorkerBackend):
    name = "mock"

    def invoke(self, request: WorkerRequest) -> WorkerResult:
        flag_match = FLAG_RE.search(request.challenge_text)
        if flag_match:
            return WorkerResult(
                backend=self.name,
                status="solved",
                summary="Flag already present in challenge text.",
                next_step="Submit the flag to validate the challenge.",
                flag=flag_match.group(0),
                evidence=["Detected an inline flag pattern in the challenge statement."],
            )

        if request.attempt_index == 1:
            artifact_note = (
                f"Staged artifacts available in workspace: {', '.join(request.artifact_paths)}"
                if request.artifact_paths
                else "No artifacts were provided, so only the challenge text was analyzed."
            )
            return WorkerResult(
                backend=self.name,
                status="needs_retry",
                summary=f"First pass using {request.skill.slug}: likely auth bypass or input tampering path.",
                next_step="Retry with another worker or increase tool autonomy to validate the main hypothesis.",
                evidence=[
                    f"Skill selected: {request.skill.slug}",
                    artifact_note,
                ],
                commands=["curl -i http://target/login", "ffuf -w wordlist.txt -u http://target/FUZZ"],
            )

        return WorkerResult(
            backend=self.name,
            status="blocked",
            summary="Mock worker exhausted its deterministic branches without recovering a flag.",
            next_step="Escalate to a real backend such as codex or claude.",
            evidence=["This is the expected fallback branch of the mock backend."],
        )


class SubprocessWorker(WorkerBackend, ABC):
    def __init__(self, name: str, timeout_seconds: int = 600) -> None:
        self.name = name
        self.timeout_seconds = timeout_seconds

    def invoke(self, request: WorkerRequest) -> WorkerResult:
        run_dir = request.workspace / ".runs" / self.name
        run_dir.mkdir(parents=True, exist_ok=True)
        schema_path = run_dir / f"attempt-{request.attempt_index:02d}-schema.json"
        output_path = run_dir / f"attempt-{request.attempt_index:02d}-output.json"
        prompt_path = run_dir / f"attempt-{request.attempt_index:02d}-prompt.txt"
        events_path = run_dir / f"attempt-{request.attempt_index:02d}-events.jsonl"
        schema_path.write_text(json.dumps(RESULT_SCHEMA, indent=2), encoding="utf-8")
        prompt = self._build_prompt(request)
        prompt_path.write_text(prompt, encoding="utf-8")

        try:
            completed = subprocess.run(
                self._build_command(request, schema_path, output_path, prompt),
                cwd=request.workspace,
                input=self._stdin_payload(prompt),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_text = _to_text(exc.stdout)
            if stdout_text:
                events_path.write_text(stdout_text, encoding="utf-8")
            stderr_text = _to_text(exc.stderr)
            raw_output = self._read_output_file(output_path) or stdout_text or stderr_text
            parsed = self._parse_if_possible(raw_output)
            command_events = self._extract_command_events(stdout_text)
            if parsed is not None:
                commands = _dedupe_strings(
                    list(parsed.get("commands", [])) + self._extract_commands_from_events(stdout_text)
                )
                return WorkerResult(
                    backend=self.name,
                    status=parsed["status"],
                    summary=parsed["summary"],
                    next_step=parsed["next_step"],
                    flag=parsed.get("flag"),
                    evidence=list(parsed.get("evidence", [])),
                    commands=commands,
                    command_events=command_events,
                    event_log_path=str(events_path) if stdout_text else "",
                    raw_output=raw_output,
                )
            return WorkerResult(
                backend=self.name,
                status="blocked",
                summary=f"{self.name} timed out after {self.timeout_seconds} seconds.",
                next_step="Retry with a longer timeout or a narrower prompt.",
                evidence=[(stderr_text or stdout_text or "No subprocess output before timeout.").strip()],
                commands=_dedupe_strings(self._extract_commands_from_events(stdout_text)),
                command_events=command_events,
                event_log_path=str(events_path) if stdout_text else "",
                raw_output=raw_output,
            )
        if completed.stdout:
            events_path.write_text(completed.stdout, encoding="utf-8")
        raw_output = self._read_output_file(output_path) or completed.stdout or completed.stderr
        command_events = self._extract_command_events(completed.stdout or "")
        parsed = self._parse_if_possible(raw_output)
        if completed.returncode != 0 and parsed is None:
            return WorkerResult(
                backend=self.name,
                status="blocked",
                summary=f"{self.name} exited with status {completed.returncode}.",
                next_step="Inspect stderr/stdout and adjust authentication or CLI flags.",
                evidence=[completed.stderr.strip() or completed.stdout.strip() or "No subprocess output."],
                commands=_dedupe_strings(self._extract_commands_from_events(completed.stdout or "")),
                command_events=command_events,
                event_log_path=str(events_path) if completed.stdout else "",
                raw_output=raw_output,
            )

        if parsed is None:
            parsed = self._parse_structured_output(raw_output)
        commands = _dedupe_strings(
            list(parsed.get("commands", [])) + self._extract_commands_from_events(completed.stdout or "")
        )
        return WorkerResult(
            backend=self.name,
            status=parsed["status"],
            summary=parsed["summary"],
            next_step=parsed["next_step"],
            flag=parsed.get("flag"),
            evidence=list(parsed.get("evidence", [])),
            commands=commands,
            command_events=command_events,
            event_log_path=str(events_path) if completed.stdout else "",
            raw_output=raw_output,
        )

    def _build_prompt(self, request: WorkerRequest) -> str:
        prior_attempts = json.dumps(request.prior_attempts, indent=2) if request.prior_attempts else "[]"
        artifacts = "\n".join(f"- {path}" for path in request.artifact_paths) or "- none"
        metadata = json.dumps(request.metadata, indent=2, ensure_ascii=False) if request.metadata else "{}"
        return textwrap.dedent(
            f"""
            Challenge name: {request.challenge_name}
            Attempt: {request.attempt_index}
            Workspace: {request.workspace}
            Declared category: {request.challenge_category or "unknown"}
            Target host: {request.target_host or "none"}

            Challenge text:
            {request.challenge_text}

            Artifact paths:
            {artifacts}

            Challenge metadata:
            {metadata}

            Prior attempts:
            {prior_attempts}

            Specialist skill: {request.skill.name}
            Skill description: {request.skill.description}

            Skill instructions:
            {request.skill.instructions}

            Objective:
            - Solve the CTF challenge if possible.
            - You may execute shell commands inside the workspace when needed.
            - If a target host is provided, prefer direct interaction with it using shell tools before relying on external references.
            - If you cannot finish, return the most useful next step.
            - If you find a candidate flag, include it in the `flag` field only.
            - Keep evidence concise and operational.
            - Include the key commands you executed in the `commands` field.
            - Do not rely on public writeups alone when direct interaction is feasible from the workspace.
            """
        ).strip()

    def _parse_structured_output(self, raw_output: str) -> dict[str, Any]:
        payload = _extract_json(raw_output)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object from {self.name}, got: {type(payload).__name__}")
        if "status" in payload:
            return payload

        for nested_key in ("result", "content", "message", "output"):
            nested = payload.get(nested_key)
            if isinstance(nested, str):
                nested_payload = _extract_json(nested)
                if isinstance(nested_payload, dict) and "status" in nested_payload:
                    return nested_payload

        raise ValueError(f"Unable to locate a structured worker result in {self.name} output.")

    def _parse_if_possible(self, raw_output: str) -> dict[str, Any] | None:
        try:
            return self._parse_structured_output(raw_output)
        except Exception:
            return None

    def _extract_command_events(self, event_stream: str) -> list[dict[str, Any]]:
        return []

    def _extract_commands_from_events(self, event_stream: str) -> list[str]:
        return [event["command"] for event in self._extract_command_events(event_stream) if event.get("command")]

    def _read_output_file(self, output_path: Path) -> str:
        if output_path.exists():
            return output_path.read_text(encoding="utf-8").strip()
        return ""

    def _stdin_payload(self, prompt: str) -> str | None:
        return None

    @abstractmethod
    def _build_command(
        self,
        request: WorkerRequest,
        schema_path: Path,
        output_path: Path,
        prompt: str,
    ) -> list[str]:
        raise NotImplementedError


class CodexWorker(SubprocessWorker):
    def __init__(self) -> None:
        super().__init__(name="codex", timeout_seconds=int(os.getenv("CODEX_TIMEOUT_SECONDS", "600")))
        self.model = os.getenv("CODEX_MODEL", "")
        self.sandbox = _normalize_codex_sandbox(os.getenv("CODEX_SANDBOX", "workspace-write"))
        self.approval_policy = os.getenv("CODEX_APPROVAL_POLICY", "never")
        self.extra_args = shlex.split(os.getenv("CODEX_EXTRA_ARGS", ""))
        self.stream_events = _env_flag("CODEX_STREAM_EVENTS", True)

    def invoke(self, request: WorkerRequest) -> WorkerResult:
        if not self.stream_events:
            return super().invoke(request)

        run_dir = request.workspace / ".runs" / self.name
        run_dir.mkdir(parents=True, exist_ok=True)
        schema_path = run_dir / f"attempt-{request.attempt_index:02d}-schema.json"
        output_path = run_dir / f"attempt-{request.attempt_index:02d}-output.json"
        prompt_path = run_dir / f"attempt-{request.attempt_index:02d}-prompt.txt"
        events_path = run_dir / f"attempt-{request.attempt_index:02d}-events.jsonl"
        schema_path.write_text(json.dumps(RESULT_SCHEMA, indent=2), encoding="utf-8")
        prompt = self._build_prompt(request)
        prompt_path.write_text(prompt, encoding="utf-8")

        command = self._build_command(request, schema_path, output_path, prompt)
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        process = subprocess.Popen(
            command,
            cwd=request.workspace,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        stdin_payload = self._stdin_payload(prompt)
        if stdin_payload is not None and process.stdin is not None:
            process.stdin.write(stdin_payload)
            process.stdin.close()

        stdout_thread = threading.Thread(
            target=_read_stream_lines,
            args=(process.stdout, stdout_chunks, self._emit_live_event),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_read_stream_lines,
            args=(process.stderr, stderr_chunks, None),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        try:
            returncode = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            returncode = None

        stdout_thread.join()
        stderr_thread.join()
        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)
        if stdout_text:
            events_path.write_text(stdout_text, encoding="utf-8")

        raw_output = self._read_output_file(output_path) or stdout_text or stderr_text
        command_events = self._extract_command_events(stdout_text)
        parsed = self._parse_if_possible(raw_output)
        if timed_out:
            if parsed is not None:
                commands = _dedupe_strings(
                    list(parsed.get("commands", [])) + self._extract_commands_from_events(stdout_text)
                )
                return WorkerResult(
                    backend=self.name,
                    status=parsed["status"],
                    summary=parsed["summary"],
                    next_step=parsed["next_step"],
                    flag=parsed.get("flag"),
                    evidence=list(parsed.get("evidence", [])),
                    commands=commands,
                    command_events=command_events,
                    event_log_path=str(events_path) if stdout_text else "",
                    raw_output=raw_output,
                )
            return WorkerResult(
                backend=self.name,
                status="blocked",
                summary=f"{self.name} timed out after {self.timeout_seconds} seconds.",
                next_step="Retry with a longer timeout or a narrower prompt.",
                evidence=[(stderr_text or stdout_text or "No subprocess output before timeout.").strip()],
                commands=_dedupe_strings(self._extract_commands_from_events(stdout_text)),
                command_events=command_events,
                event_log_path=str(events_path) if stdout_text else "",
                raw_output=raw_output,
            )

        if returncode not in (0, None) and parsed is None:
            return WorkerResult(
                backend=self.name,
                status="blocked",
                summary=f"{self.name} exited with status {returncode}.",
                next_step="Inspect stderr/stdout and adjust authentication or CLI flags.",
                evidence=[(stderr_text or stdout_text or "No subprocess output.").strip()],
                commands=_dedupe_strings(self._extract_commands_from_events(stdout_text)),
                command_events=command_events,
                event_log_path=str(events_path) if stdout_text else "",
                raw_output=raw_output,
            )

        if parsed is None:
            parsed = self._parse_structured_output(raw_output)
        commands = _dedupe_strings(
            list(parsed.get("commands", [])) + self._extract_commands_from_events(stdout_text)
        )
        return WorkerResult(
            backend=self.name,
            status=parsed["status"],
            summary=parsed["summary"],
            next_step=parsed["next_step"],
            flag=parsed.get("flag"),
            evidence=list(parsed.get("evidence", [])),
            commands=commands,
            command_events=command_events,
            event_log_path=str(events_path) if stdout_text else "",
            raw_output=raw_output,
        )

    def _stdin_payload(self, prompt: str) -> str | None:
        return prompt

    def _build_command(
        self,
        request: WorkerRequest,
        schema_path: Path,
        output_path: Path,
        prompt: str,
    ) -> list[str]:
        command = [
            "codex",
            "-a",
            self.approval_policy,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            self.sandbox,
            "--json",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            "-C",
            str(request.workspace),
            "-",
        ]
        if self.model:
            command[3:3] = ["-m", self.model]
        return command[:-1] + self.extra_args + command[-1:]

    def _extract_command_events(self, event_stream: str) -> list[dict[str, Any]]:
        latest_by_id: dict[str, dict[str, Any]] = {}
        ordered_ids: list[str] = []
        for line in event_stream.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = payload.get("item")
            if not isinstance(item, dict) or item.get("type") != "command_execution":
                continue
            item_id = str(item.get("id", len(ordered_ids)))
            latest_by_id[item_id] = {
                "id": item_id,
                "event_type": payload.get("type", ""),
                "command": item.get("command", ""),
                "status": item.get("status", ""),
                "exit_code": item.get("exit_code"),
                "output": item.get("aggregated_output", ""),
            }
            if item_id not in ordered_ids:
                ordered_ids.append(item_id)
        return [latest_by_id[item_id] for item_id in ordered_ids]

    def _emit_live_event(self, line: str) -> None:
        formatted = _format_codex_event_line(line)
        if formatted:
            sys.stderr.write(formatted)
            sys.stderr.flush()


class ClaudeWorker(SubprocessWorker):
    def __init__(self) -> None:
        super().__init__(name="claude", timeout_seconds=int(os.getenv("CLAUDE_TIMEOUT_SECONDS", "600")))
        self.model = os.getenv("CLAUDE_MODEL", "")
        self.permission_mode = os.getenv("CLAUDE_PERMISSION_MODE", "auto")
        self.extra_args = shlex.split(os.getenv("CLAUDE_EXTRA_ARGS", ""))

    def _build_command(
        self,
        request: WorkerRequest,
        schema_path: Path,
        output_path: Path,
        prompt: str,
    ) -> list[str]:
        command = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(RESULT_SCHEMA),
            "--permission-mode",
            self.permission_mode,
            "--append-system-prompt",
            request.skill.instructions,
        ]
        if self.model:
            command.extend(["--model", self.model])
        command.extend(self.extra_args)
        command.append(prompt)
        return command


def _extract_json(raw_output: str) -> Any:
    text = raw_output.strip()
    if not text:
        raise ValueError("Worker returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    code_fence_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_fence_match:
        return json.loads(code_fence_match.group(1))

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        return json.loads(text[first_brace : last_brace + 1])

    raise ValueError("Unable to extract JSON object from worker output.")


def extract_flag(text: str) -> str | None:
    match = FLAG_RE.search(text)
    return match.group(0) if match else None


def build_worker_pool(backends: list[str]) -> dict[str, WorkerBackend]:
    available: dict[str, WorkerBackend] = {
        "mock": MockWorker(),
        "codex": CodexWorker(),
        "claude": ClaudeWorker(),
    }
    missing = [backend for backend in backends if backend not in available]
    if missing:
        raise KeyError(f"Unsupported backend(s): {', '.join(missing)}")
    return {backend: available[backend] for backend in backends}


def _normalize_codex_sandbox(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"read-only", "workspace-write", "danger-full-access"}:
        return normalized
    if normalized in {"seatbelt", "sandbox", "workspace"}:
        return "workspace-write"
    return "workspace-write"


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _read_stream_lines(
    stream: Any,
    collector: list[str],
    on_line: Any = None,
) -> None:
    if stream is None:
        return
    try:
        for line in stream:
            collector.append(line)
            if on_line is not None:
                on_line(line)
    finally:
        stream.close()


def _format_codex_event_line(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    item = payload.get("item")
    if not isinstance(item, dict) or item.get("type") != "command_execution":
        return None
    command = item.get("command", "").strip()
    if not command:
        return None
    event_type = payload.get("type")
    if event_type == "item.started":
        return f"[codex] start: {command}\n"
    if event_type == "item.completed":
        exit_code = item.get("exit_code")
        return f"[codex] done ({exit_code}): {command}\n"
    return None
