from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .graph import build_initial_state, build_orchestrator
from .workers import build_worker_pool
from .workspace import prepare_challenge_workspace


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    backend_sequence = [item.strip() for item in args.backend_sequence.split(",") if item.strip()]
    workers = build_worker_pool(backend_sequence)
    graph = build_orchestrator(args.skills_root, workers)
    initial_state = build_initial_state(
        challenge_name=challenge_name,
        challenge_text=challenge_text,
        workspace=challenge_workspace,
        backend_sequence=backend_sequence,
        category_hint=category_hint,
        target_host=target_host,
        challenge_metadata=challenge_metadata,
        artifact_paths=staged_artifacts,
        max_attempts=args.max_attempts,
    )
    final_state = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": args.thread_id}},
    )
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


if __name__ == "__main__":
    sys.exit(main())
