from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path
import re
import shutil
from typing import Any


SLUG_RE = re.compile(r"[^a-z0-9]+")


def prepare_challenge_workspace(
    workspace_root: Path,
    challenge_name: str,
    artifact_paths: list[str],
    challenge_payload: dict[str, Any],
    source_root: Path | None = None,
) -> tuple[Path, list[str]]:
    challenge_dir = _workspace_dir_for_challenge(workspace_root, challenge_name)
    artifacts_dir = challenge_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    copied_artifacts: list[str] = []
    used_names: set[str] = set()
    for artifact_path in artifact_paths:
        source_path = _resolve_artifact_path(artifact_path, source_root)
        target_name = _dedupe_name(source_path.name, used_names)
        target_path = artifacts_dir / target_name
        _copy_path(source_path, target_path)
        copied_artifacts.append(str(target_path.relative_to(challenge_dir)))

    manifest = dict(challenge_payload)
    manifest["staged_artifacts"] = copied_artifacts
    manifest["workspace"] = str(challenge_dir.resolve())
    (challenge_dir / "challenge.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return challenge_dir, copied_artifacts


def _workspace_dir_for_challenge(workspace_root: Path, challenge_name: str) -> Path:
    slug = _slugify(challenge_name)
    digest = sha1(challenge_name.encode("utf-8")).hexdigest()[:8]
    return workspace_root / ".challenges" / f"{slug}-{digest}"


def _slugify(value: str) -> str:
    slug = SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "challenge"


def _resolve_artifact_path(raw_path: str, source_root: Path | None) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        if not candidate.exists():
            raise FileNotFoundError(f"Artifact path does not exist: {candidate}")
        return candidate.resolve()

    search_roots = [root for root in (source_root, Path.cwd()) if root is not None]
    for root in search_roots:
        candidate_path = (root / candidate).resolve()
        if candidate_path.exists():
            return candidate_path
    raise FileNotFoundError(f"Artifact path does not exist: {raw_path}")


def _copy_path(source_path: Path, target_path: Path) -> None:
    if source_path.is_dir():
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


def _dedupe_name(name: str, used_names: set[str]) -> str:
    if name not in used_names:
        used_names.add(name)
        return name

    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 2
    while True:
        candidate = f"{stem}-{index}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        index += 1
