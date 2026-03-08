from pathlib import Path
import unittest

from ctf_destroyer.graph import build_initial_state, build_orchestrator
from ctf_destroyer.workers import build_worker_pool


ROOT = Path(__file__).resolve().parents[1]


class GraphTest(unittest.TestCase):
    def test_graph_stops_after_max_attempts_with_mock_worker(self) -> None:
        graph = build_orchestrator(ROOT / "skills", build_worker_pool(["mock"]))
        initial_state = build_initial_state(
            challenge_name="Login Panel",
            challenge_text="Challenge web avec formulaire de login et aucune autre donnée.",
            workspace=ROOT,
            backend_sequence=["mock"],
            category_hint="web",
            max_attempts=2,
        )
        final_state = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": "test-max-attempts"}},
        )
        self.assertEqual(final_state["category"], "web")
        self.assertEqual(final_state["attempts"], 2)
        self.assertEqual(final_state["stop_reason"], "max_attempts_reached")
        self.assertFalse(final_state["solved"])

    def test_graph_returns_flag_when_worker_finds_one(self) -> None:
        graph = build_orchestrator(ROOT / "skills", build_worker_pool(["mock"]))
        initial_state = build_initial_state(
            challenge_name="Inline Flag",
            challenge_text="L'énoncé contient déjà flag{inline-win}.",
            workspace=ROOT,
            backend_sequence=["mock"],
            max_attempts=1,
        )
        final_state = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": "test-inline-flag"}},
        )
        self.assertTrue(final_state["solved"])
        self.assertEqual(final_state["final_flag"], "flag{inline-win}")
        self.assertEqual(final_state["stop_reason"], "flag_found")


if __name__ == "__main__":
    unittest.main()
