from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..challenges import build_canonical_challenge_payload


@dataclass(frozen=True)
class ImportRequest:
    source: str | None
    input_file: Path | None
    output: Path | None
    use_stdout: bool
    review: bool
    selected_challenge: str | None
    list_only: bool
    session_cookie: str | None
    cookie_file: Path | None
    start_instance: bool = False


@dataclass(frozen=True)
class SourceDocument:
    source_type: str
    source_label: str
    raw_text: str
    urls: list[str] = field(default_factory=list)
    fetched_url: str | None = None
    raw_html: str | None = None


@dataclass(frozen=True)
class DiscoveredChallenge:
    title: str
    text_block: str
    challenge_id: int | None = None
    category: str | None = None
    points: int | None = None
    solves: int | None = None
    source_label: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImportedChallenge:
    title: str
    description: str
    category: str
    target_host: str | None = None
    files: list[str] = field(default_factory=list)
    operator_hint: str | None = None
    points: int | None = None
    solves: int | None = None
    play_url: str | None = None
    references: list[str] = field(default_factory=list)
    source_snippet: str | None = None
    import_metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        payload = build_canonical_challenge_payload(
            title=self.title,
            description=self.description,
            category=self.category,
            target_host=self.target_host,
            files=self.files,
            operator_hint=self.operator_hint,
            points=self.points,
            solves=self.solves,
            play_url=self.play_url,
            references=self.references,
            source_snippet=self.source_snippet,
            import_metadata=self.import_metadata,
        )
        if self.warnings:
            metadata = dict(payload.get("import_metadata", {}))
            metadata["warnings"] = list(self.warnings)
            payload["import_metadata"] = metadata
        return payload
