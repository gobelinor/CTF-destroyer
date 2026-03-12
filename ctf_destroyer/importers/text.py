from __future__ import annotations

from dataclasses import replace
import re
from typing import Iterable

from ..skills import route_category
from .models import DiscoveredChallenge, ImportedChallenge, SourceDocument


TITLE_LINE_RE = re.compile(
    r"^(?P<title>.+?)\s+(?P<points>\d+)\s+pts(?:\s*[·•-]\s*(?P<solves>\d+)\s+Solves?)?\s*$",
    re.IGNORECASE,
)
CONNECT_RE = re.compile(
    r"connect\s+at\s+(?P<host>[a-z0-9._-]+)(?::|\s+)(?P<port>\d+)\b",
    re.IGNORECASE,
)
PLAY_RE = re.compile(r"play\s+at\s+(?P<url>https?://\S+)", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>()]+")
CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n(?P<code>.*?)```", re.DOTALL)


def discover_text_challenges(document: SourceDocument) -> list[DiscoveredChallenge]:
    lines = [line.rstrip() for line in document.raw_text.splitlines()]
    candidate_indexes = [index for index, line in enumerate(lines) if TITLE_LINE_RE.match(line.strip())]
    if not candidate_indexes:
        return [_parse_candidate(document.raw_text, document.source_label)]

    if len(candidate_indexes) == 1:
        return [_parse_candidate(document.raw_text, document.source_label)]

    candidates: list[DiscoveredChallenge] = []
    for index, start in enumerate(candidate_indexes):
        end = candidate_indexes[index + 1] if index + 1 < len(candidate_indexes) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        if block:
            candidates.append(_parse_candidate(block, document.source_label))
    return candidates


def select_text_challenge(
    candidates: list[DiscoveredChallenge],
    selected_challenge: str | None,
) -> DiscoveredChallenge:
    if not candidates:
        raise SystemExit("No challenge-like content was detected in the source.")
    if len(candidates) == 1 and not selected_challenge:
        return candidates[0]
    if not selected_challenge:
        raise SystemExit(
            "Multiple challenge candidates were detected. Use --list to inspect them or --challenge to select one."
        )

    normalized_query = selected_challenge.strip().lower()
    exact = [candidate for candidate in candidates if candidate.title.lower() == normalized_query]
    if len(exact) == 1:
        return exact[0]

    partial = [candidate for candidate in candidates if normalized_query in candidate.title.lower()]
    if len(partial) == 1:
        return partial[0]

    raise SystemExit(f"Unable to select a unique challenge for query: {selected_challenge}")


def import_text_challenge(candidate: DiscoveredChallenge, document: SourceDocument) -> ImportedChallenge:
    title, points, solves = _parse_title_line(candidate.text_block)
    target_host = _extract_target_host(candidate.text_block)
    play_url = _extract_play_url(candidate.text_block) or document.fetched_url
    urls = _collect_urls(candidate.text_block, document.urls)
    files, references = _split_urls(urls, play_url)
    description = _build_description(candidate.text_block)
    code_snippet = _extract_code_snippet(candidate.text_block)
    category = _infer_category(title, description, target_host)
    operator_hint = _suggest_operator_hint(category, has_target=bool(target_host), has_files=bool(files))
    warnings = _build_warnings(points, solves, target_host, files)
    confidence = "high" if title and description else "medium"

    return ImportedChallenge(
        title=title,
        description=description,
        category=category,
        target_host=target_host,
        files=files,
        operator_hint=operator_hint,
        points=points,
        solves=solves,
        play_url=play_url,
        references=references,
        source_snippet=code_snippet,
        import_metadata={
            "source_type": document.source_type,
            "source_url": document.fetched_url or document.source_label,
            "extractor": "text",
            "confidence": confidence,
        },
        warnings=warnings,
    )


def list_discovered_challenges(candidates: Iterable[DiscoveredChallenge]) -> str:
    lines: list[str] = []
    for index, candidate in enumerate(candidates, 1):
        details = []
        if candidate.challenge_id is not None:
            details.append(f"id={candidate.challenge_id}")
        if candidate.points is not None:
            details.append(f"{candidate.points} pts")
        if candidate.solves is not None:
            details.append(f"{candidate.solves} solves")
        suffix = f" ({', '.join(details)})" if details else ""
        warning_suffix = _render_warning_suffix(candidate.warnings)
        lines.append(f"[{index}] {candidate.title}{suffix}{warning_suffix}")
    return "\n".join(lines)


def _parse_candidate(text_block: str, source_label: str | None) -> DiscoveredChallenge:
    title, points, solves = _parse_title_line(text_block)
    warnings = _build_candidate_warnings(points, solves)
    return DiscoveredChallenge(
        title=title,
        text_block=text_block.strip(),
        points=points,
        solves=solves,
        source_label=source_label,
        warnings=warnings,
    )


def _parse_title_line(text_block: str) -> tuple[str, int | None, int | None]:
    first_non_empty = next((line.strip() for line in text_block.splitlines() if line.strip()), "")
    match = TITLE_LINE_RE.match(first_non_empty)
    if not match:
        fallback = first_non_empty or "Imported Challenge"
        return fallback, None, None
    points = int(match.group("points"))
    solves = match.group("solves")
    return match.group("title").strip(), points, int(solves) if solves else None


def _extract_target_host(text_block: str) -> str | None:
    match = CONNECT_RE.search(text_block)
    if not match:
        return None
    return f"{match.group('host')}:{match.group('port')}"


def _extract_play_url(text_block: str) -> str | None:
    match = PLAY_RE.search(text_block)
    if not match:
        return None
    return match.group("url").rstrip(".,)")


def _collect_urls(text_block: str, discovered_urls: list[str]) -> list[str]:
    urls = [match.rstrip(".,)") for match in URL_RE.findall(text_block)]
    for url in discovered_urls:
        cleaned = url.rstrip(".,)")
        if cleaned not in urls:
            urls.append(cleaned)
    return urls


def _split_urls(urls: list[str], play_url: str | None) -> tuple[list[str], list[str]]:
    files: list[str] = []
    references: list[str] = []
    for url in urls:
        if play_url and url == play_url:
            continue
        if _looks_like_file_url(url):
            files.append(url)
            continue
        references.append(url)
    return files, references


def _looks_like_file_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.endswith(
        (
            ".py",
            ".zip",
            ".tar",
            ".tar.gz",
            ".tgz",
            ".gz",
            ".bz2",
            ".xz",
            ".txt",
            ".pcap",
            ".png",
            ".jpg",
            ".jpeg",
            ".pdf",
            ".cpp",
            ".c",
            ".rs",
            ".go",
            ".js",
            ".java",
            ".sage",
            ".bin",
        )
    )


def _build_description(text_block: str) -> str:
    lines = [line.rstrip() for line in text_block.splitlines()]
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if stripped.lower().startswith("challenge files:"):
            continue
        if stripped.startswith("- http://") or stripped.startswith("- https://"):
            continue
        if stripped.startswith("http://") or stripped.startswith("https://"):
            continue
        kept.append(stripped)
    description = "\n".join(kept).strip()
    return description or text_block.strip()


def _extract_code_snippet(text_block: str) -> str | None:
    fenced = CODE_FENCE_RE.search(text_block)
    if fenced:
        snippet = fenced.group("code").strip()
        return snippet or None
    return None


def _infer_category(title: str, description: str, target_host: str | None) -> str:
    category, _ = route_category(
        "\n".join(part for part in (title, description, target_host or "") if part),
        None,
    )
    return category


def _suggest_operator_hint(category: str, has_target: bool, has_files: bool) -> str:
    base_by_category = {
        "crypto": "Read the provided material first, recover the primitive and parameters, and avoid brute force.",
        "web": "Map the request flow and trust boundaries first; do not fuzz blindly before understanding the app.",
        "pwn": "Read the binary and the interface first, then script the interaction instead of guessing by hand.",
        "reverse": "Inspect the artifact before touching the remote endpoint and reduce the logic to a small reproducible script.",
        "forensics": "Build a minimal extraction pipeline from the provided artifacts before exploring side paths.",
        "osint": "Collect the explicit clues first and keep the pivot chain tight instead of wandering across the internet.",
        "stego": "Inspect formats and metadata before trying broad extraction tools or guesswork.",
        "misc": "Read the provided material first and reduce the problem to a short reproducible script before experimenting widely.",
    }
    suffix: list[str] = []
    if has_files:
        suffix.append("Start with the provided files.")
    if has_target:
        suffix.append("Interact with the target only after you understand the protocol or input format.")
    return " ".join([base_by_category.get(category, base_by_category["misc"]), *suffix]).strip()


def _build_warnings(
    points: int | None,
    solves: int | None,
    target_host: str | None,
    files: list[str],
) -> list[str]:
    warnings: list[str] = []
    if points is None:
        warnings.append("Points were not detected from the source.")
    if solves is None:
        warnings.append("Solve count was not detected from the source.")
    if target_host is None:
        warnings.append("Target host was not detected from the source.")
    if not files:
        warnings.append("No artifact file URLs were detected from the source.")
    return warnings


def _build_candidate_warnings(points: int | None, solves: int | None) -> list[str]:
    warnings: list[str] = []
    if points is None:
        warnings.append("Points were not detected from the source.")
    if solves is None:
        warnings.append("Solve count was not detected from the source.")
    return warnings


def _render_warning_suffix(warnings: list[str]) -> str:
    if not warnings:
        return ""
    labels = [_warning_label(item) for item in warnings[:2]]
    return f"  [warn: {', '.join(labels)}]"


def _warning_label(warning: str) -> str:
    lowered = warning.lower()
    if "target host" in lowered:
        return "no target"
    if "artifact" in lowered or "file" in lowered:
        return "no files"
    if "solve count" in lowered:
        return "no solves"
    if "points" in lowered:
        return "no points"
    return "warning"
