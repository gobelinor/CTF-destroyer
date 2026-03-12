from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import yaml
from yaml import YAMLError


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "crypto": ("rsa", "xor", "cipher", "encrypt", "decrypt", "hash", "signature", "lattice", "lwe", "gcm"),
    "reverse": ("binary", "elf", "ghidra", "decompile", "bytecode", "crackme", "apk"),
    "web": ("http", "login", "cookie", "session", "jwt", "api", "sql", "xss", "ssrf"),
    "pwn": ("overflow", "format string", "heap", "rop", "shellcode", "uaf", "glibc"),
    "forensics": ("pcap", "memory dump", "disk image", "logs", "registry", "timeline"),
    "osint": ("social", "geolocation", "username", "metadata", "public profile"),
    "stego": ("image", "audio", "hidden data", "steganography", "lsb", "spectrogram"),
}

CATEGORY_TO_SKILL = {
    "crypto": "ctf-crypto-solver",
    "forensics": "ctf-forensics-solver",
    "misc": "ctf-misc-solver",
    "osint": "ctf-osint-solver",
    "pwn": "ctf-pwn-solver",
    "reverse": "ctf-reverse-solver",
    "stego": "ctf-stego-solver",
    "web": "ctf-web-solver",
}


@dataclass(frozen=True)
class Skill:
    slug: str
    name: str
    description: str
    instructions: str
    path: Path


def _parse_skill_file(path: Path) -> Skill:
    raw_text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(raw_text)
    metadata: dict[str, str] = {}
    instructions = raw_text.strip()
    if match:
        metadata = _parse_front_matter(match.group(1))
        instructions = match.group(2).strip()
    slug = path.parent.name
    return Skill(
        slug=slug,
        name=metadata.get("name", slug),
        description=metadata.get("description", ""),
        instructions=instructions,
        path=path,
    )


def load_skills(root: Path) -> dict[str, Skill]:
    return {
        skill.slug: skill
        for skill in (_parse_skill_file(path) for path in root.glob("*/SKILL.md"))
    }


def route_category(challenge_text: str, category_hint: str | None = None) -> tuple[str, str]:
    if category_hint:
        normalized = category_hint.strip().lower()
        if normalized in CATEGORY_TO_SKILL:
            return normalized, f"Used explicit category hint '{normalized}'."

    text = challenge_text.lower()
    scores = {
        category: sum(keyword in text for keyword in keywords)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best_category = max(scores, key=scores.get, default="misc")
    if scores.get(best_category, 0) == 0:
        return "misc", "No keyword match, falling back to misc."
    return best_category, f"Matched keywords for '{best_category}' with score {scores[best_category]}."


def resolve_specialist_skill(category: str, skills: dict[str, Skill]) -> Skill:
    skill_slug = CATEGORY_TO_SKILL.get(category, "ctf-misc-solver")
    if skill_slug in skills:
        return skills[skill_slug]
    if "ctf" in skills:
        return skills["ctf"]
    available = ", ".join(sorted(skills))
    raise KeyError(f"Unable to resolve a skill for category '{category}'. Available: {available}")


def summarize_skill_inventory(skills: Iterable[Skill]) -> str:
    return ", ".join(sorted(skill.slug for skill in skills))


def _parse_front_matter(text: str) -> dict[str, str]:
    try:
        parsed = yaml.safe_load(text) or {}
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items()}
    except YAMLError:
        pass

    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata
