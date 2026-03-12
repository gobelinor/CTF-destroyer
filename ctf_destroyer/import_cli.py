from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from .cli import _extract_env_file_arg, _load_env_file
from .importers import (
    ImportRequest,
    discover_text_challenges,
    import_ctfd_challenge,
    load_source_document,
    render_import_review,
    select_text_challenge,
    try_discover_ctfd_challenges,
)
from .importers.text import import_text_challenge, list_discovered_challenges
from .workspace import _slugify


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv = list(argv or sys.argv[1:])
    env_file = _extract_env_file_arg(argv)
    _load_env_file(env_file)

    parser = argparse.ArgumentParser(description="Import a CTF challenge source into the project JSON format.")
    parser.add_argument("source", nargs="?", help="URL, local file path, or '-' for stdin.")
    parser.add_argument("--input-file", type=Path, help="Read challenge text from a local file.")
    parser.add_argument("--output", type=Path, help="Write the imported challenge JSON to this path.")
    parser.add_argument("--stdout", action="store_true", help="Print the final JSON payload to stdout.")
    parser.add_argument("--review", action="store_true", help="Print a short import review to stderr.")
    parser.add_argument("--list", action="store_true", help="List discovered challenge candidates and exit.")
    parser.add_argument(
        "--challenge",
        help="Select one discovered challenge by exact or partial title when the source contains multiple challenges.",
    )
    parser.add_argument(
        "--session-cookie",
        help="Session cookie value or full Cookie header used when fetching a protected challenge URL.",
    )
    parser.add_argument(
        "--cookie-file",
        type=Path,
        help="File containing the raw Cookie header value used for authenticated challenge pages.",
    )
    parser.add_argument(
        "--start-instance",
        action="store_true",
        help="For CTFd container challenges, start the selected instance before building the JSON output.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=env_file,
        help="Optional .env file loaded before parsing other options. Defaults to .env when present.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    import_request = ImportRequest(
        source=args.source,
        input_file=args.input_file.resolve() if args.input_file else None,
        output=args.output.resolve() if args.output else None,
        use_stdout=bool(args.stdout),
        review=bool(args.review),
        selected_challenge=args.challenge,
        list_only=bool(args.list),
        session_cookie=args.session_cookie,
        cookie_file=args.cookie_file.resolve() if args.cookie_file else None,
        start_instance=bool(args.start_instance),
    )
    document = load_source_document(import_request)
    candidates = try_discover_ctfd_challenges(document, import_request) or discover_text_challenges(document)
    candidates = _annotate_candidates_for_listing(candidates, document, import_request)

    if args.list:
        print(list_discovered_challenges(candidates))
        return 0

    selected = select_text_challenge(candidates, args.challenge)
    imported = import_ctfd_challenge(selected, document, import_request) or import_text_challenge(selected, document)
    payload = imported.to_payload()

    if import_request.review:
        print(render_import_review(imported), file=sys.stderr)
    instance_error = _validate_instance_access(import_request, imported)
    if instance_error:
        print(f"[error] {instance_error}", file=sys.stderr)
        return 2

    output_path = import_request.output
    if output_path is None and not import_request.use_stdout:
        output_path = Path("examples") / f"{_slugify(imported.title)}.json"

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[info] wrote {output_path}", file=sys.stderr)

    if import_request.use_stdout or output_path is None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())


def _annotate_candidates_for_listing(
    candidates,
    document,
    import_request,
):
    inspect_request = replace(import_request, start_instance=False)
    annotated = []
    for candidate in candidates:
        warnings = list(getattr(candidate, "warnings", []))
        try:
            imported = import_ctfd_challenge(candidate, document, inspect_request)
            if imported is None:
                imported = import_text_challenge(candidate, document)
            warnings = list(imported.warnings)
        except Exception:
            pass
        annotated.append(
            type(candidate)(
                title=candidate.title,
                text_block=candidate.text_block,
                challenge_id=candidate.challenge_id,
                category=candidate.category,
                points=candidate.points,
                solves=candidate.solves,
                source_label=candidate.source_label,
                warnings=warnings,
            )
        )
    return annotated


def _validate_instance_access(import_request: ImportRequest, imported) -> str | None:
    if not import_request.start_instance:
        return None
    if imported.target_host:
        return None

    metadata = imported.import_metadata if isinstance(imported.import_metadata, dict) else {}
    start_result = str(metadata.get("start_instance_result") or "unknown")
    details = list(imported.warnings)
    detail_suffix = ""
    if details:
        detail_suffix = f" Details: {'; '.join(details)}"
    return (
        f"failed to acquire instance access for '{imported.title}' "
        f"(start_instance_result={start_result}).{detail_suffix}"
    )
