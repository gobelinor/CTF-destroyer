from __future__ import annotations

from typing import Any


def normalize_challenge_payload(raw: dict[str, object]) -> dict[str, object]:
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


def build_canonical_challenge_payload(
    *,
    title: str,
    description: str,
    category: str | None = None,
    target_host: str | None = None,
    files: list[str] | None = None,
    operator_hint: str | None = None,
    points: int | None = None,
    solves: int | None = None,
    play_url: str | None = None,
    references: list[str] | None = None,
    source_snippet: str | None = None,
    import_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title.strip(),
        "description": description.strip(),
    }
    if category:
        payload["category"] = category.strip()
    if target_host:
        payload["target_host"] = target_host.strip()
    if files:
        payload["files"] = [str(item).strip() for item in files if str(item).strip()]
    if operator_hint:
        payload["operator_hint"] = operator_hint.strip()
    if points is not None:
        payload["points"] = int(points)
    if solves is not None:
        payload["solves"] = int(solves)
    if play_url:
        payload["play_url"] = play_url.strip()
    if references:
        cleaned = [str(item).strip() for item in references if str(item).strip()]
        if cleaned:
            payload["references"] = cleaned
    if source_snippet:
        payload["source_snippet"] = source_snippet.rstrip()
    if import_metadata:
        payload["import_metadata"] = import_metadata
    return payload


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
