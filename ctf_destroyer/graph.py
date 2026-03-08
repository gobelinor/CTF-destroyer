from __future__ import annotations

from pathlib import Path
from typing import Any
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .skills import Skill, load_skills, resolve_specialist_skill, route_category
from .workers import WorkerRequest, WorkerResult, WorkerBackend, extract_flag


class ChallengeState(TypedDict, total=False):
    challenge_name: str
    challenge_text: str
    challenge_metadata: dict[str, Any]
    artifact_paths: list[str]
    category_hint: str | None
    target_host: str | None
    category: str
    category_reason: str
    specialist_skill_slug: str
    specialist_skill_path: str
    backend_sequence: list[str]
    backend_index: int
    active_backend: str
    attempts: int
    max_attempts: int
    history: list[dict[str, Any]]
    latest_worker_output: dict[str, Any]
    solved: bool
    final_flag: str | None
    final_summary: str
    stop_reason: str
    workspace: str


def build_orchestrator(
    skills_root: Path,
    workers: dict[str, WorkerBackend],
):
    skills = load_skills(skills_root)

    def route_node(state: ChallengeState) -> dict[str, Any]:
        category, reason = route_category(
            "\n".join(
                part
                for part in (
                    state["challenge_name"],
                    state["challenge_text"],
                    state.get("target_host", ""),
                )
                if part
            ),
            state.get("category_hint"),
        )
        skill = resolve_specialist_skill(category, skills)
        return {
            "category": category,
            "category_reason": reason,
            "specialist_skill_slug": skill.slug,
            "specialist_skill_path": str(skill.path),
            "backend_index": state.get("backend_index", 0),
            "attempts": state.get("attempts", 0),
            "history": list(state.get("history", [])),
            "solved": False,
            "final_flag": None,
            "final_summary": "",
            "stop_reason": "",
        }

    def specialist_node(state: ChallengeState) -> dict[str, Any]:
        skill = _get_skill(skills, state["specialist_skill_slug"])
        sequence = state["backend_sequence"]
        backend_index = state.get("backend_index", 0) % len(sequence)
        backend_name = sequence[backend_index]
        request = WorkerRequest(
            attempt_index=state.get("attempts", 0) + 1,
            challenge_name=state["challenge_name"],
            challenge_text=state["challenge_text"],
            challenge_category=state.get("category_hint"),
            target_host=state.get("target_host"),
            metadata=dict(state.get("challenge_metadata", {})),
            artifact_paths=list(state.get("artifact_paths", [])),
            workspace=Path(state["workspace"]),
            skill=skill,
            prior_attempts=list(state.get("history", [])),
        )
        result = workers[backend_name].invoke(request)
        history = list(state.get("history", []))
        history.append(
            {
                "attempt": request.attempt_index,
                "backend": backend_name,
                "status": result.status,
                "summary": result.summary,
                "next_step": result.next_step,
                "flag": result.flag,
                "commands": result.commands,
                "event_log_path": result.event_log_path,
            }
        )
        return {
            "attempts": request.attempt_index,
            "active_backend": backend_name,
            "latest_worker_output": result.as_state_payload(),
            "history": history,
        }

    def evaluator_node(state: ChallengeState) -> dict[str, Any]:
        latest = WorkerResult.from_payload(state["latest_worker_output"])
        flag = latest.flag or extract_flag(latest.summary) or extract_flag(latest.raw_output)
        if flag:
            return {
                "solved": True,
                "final_flag": flag,
                "final_summary": latest.summary,
                "stop_reason": "flag_found",
            }

        attempts = state["attempts"]
        if attempts >= state["max_attempts"]:
            return {
                "solved": False,
                "final_summary": latest.summary,
                "stop_reason": "max_attempts_reached",
            }

        next_backend_index = (state.get("backend_index", 0) + 1) % len(state["backend_sequence"])
        return {
            "backend_index": next_backend_index,
            "final_summary": latest.summary,
            "stop_reason": "",
        }

    def after_evaluator(state: ChallengeState) -> str:
        if state.get("solved") or state.get("stop_reason") == "max_attempts_reached":
            return END
        return "run_specialist"

    builder = StateGraph(ChallengeState)
    builder.add_node("route", route_node)
    builder.add_node("run_specialist", specialist_node)
    builder.add_node("evaluate", evaluator_node)
    builder.add_edge(START, "route")
    builder.add_edge("route", "run_specialist")
    builder.add_edge("run_specialist", "evaluate")
    builder.add_conditional_edges("evaluate", after_evaluator)
    return builder.compile(checkpointer=InMemorySaver())


def build_initial_state(
    challenge_name: str,
    challenge_text: str,
    workspace: Path,
    backend_sequence: list[str],
    category_hint: str | None = None,
    target_host: str | None = None,
    challenge_metadata: dict[str, Any] | None = None,
    artifact_paths: list[str] | None = None,
    max_attempts: int = 4,
) -> ChallengeState:
    if not backend_sequence:
        raise ValueError("backend_sequence must not be empty.")
    return ChallengeState(
        challenge_name=challenge_name,
        challenge_text=challenge_text,
        challenge_metadata=dict(challenge_metadata or {}),
        artifact_paths=list(artifact_paths or []),
        category_hint=category_hint,
        target_host=target_host,
        backend_sequence=backend_sequence,
        backend_index=0,
        attempts=0,
        max_attempts=max_attempts,
        history=[],
        workspace=str(workspace.resolve()),
    )


def _get_skill(skills: dict[str, Skill], slug: str) -> Skill:
    if slug not in skills:
        raise KeyError(f"Skill '{slug}' is not available in the registry.")
    return skills[slug]
