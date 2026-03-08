import unittest

from ctf_destroyer.cli import _normalize_challenge_payload


class CliNormalizationTest(unittest.TestCase):
    def test_normalizes_target_and_files(self) -> None:
        payload = _normalize_challenge_payload(
            {
                "title": "Evaluative",
                "description": "Decode the rogue bot.",
                "category": "misc",
                "ip": "154.57.164.64",
                "port": 31748,
                "files": ["bot.py", "trace.txt"],
                "difficulty": "Very Easy",
                "points": 10,
            }
        )
        self.assertEqual(payload["challenge_name"], "Evaluative")
        self.assertEqual(payload["challenge_text"], "Decode the rogue bot.")
        self.assertEqual(payload["category_hint"], "misc")
        self.assertEqual(payload["target_host"], "154.57.164.64:31748")
        self.assertEqual(payload["artifact_paths"], ["bot.py", "trace.txt"])
        self.assertEqual(payload["challenge_metadata"]["difficulty"], "Very Easy")
        self.assertEqual(payload["challenge_metadata"]["points"], 10)


if __name__ == "__main__":
    unittest.main()
