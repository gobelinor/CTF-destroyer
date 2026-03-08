import unittest

from ctf_destroyer.workers import CodexWorker, _format_codex_event_line


class WorkerTraceTest(unittest.TestCase):
    def test_codex_event_stream_extracts_commands(self) -> None:
        event_stream = "\n".join(
            [
                '{"type":"item.started","item":{"id":"item_0","type":"command_execution","command":"/bin/zsh -lc pwd","aggregated_output":"","exit_code":null,"status":"in_progress"}}',
                '{"type":"item.completed","item":{"id":"item_0","type":"command_execution","command":"/bin/zsh -lc pwd","aggregated_output":"/tmp\\n","exit_code":0,"status":"completed"}}',
                '{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc ls","aggregated_output":"a\\n","exit_code":0,"status":"completed"}}',
            ]
        )
        worker = CodexWorker()
        events = worker._extract_command_events(event_stream)
        commands = worker._extract_commands_from_events(event_stream)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["status"], "completed")
        self.assertEqual(commands, ["/bin/zsh -lc pwd", "/bin/zsh -lc ls"])

    def test_format_codex_event_line_for_console(self) -> None:
        started = _format_codex_event_line(
            '{"type":"item.started","item":{"id":"item_0","type":"command_execution","command":"/bin/zsh -lc pwd","status":"in_progress"}}'
        )
        completed = _format_codex_event_line(
            '{"type":"item.completed","item":{"id":"item_0","type":"command_execution","command":"/bin/zsh -lc pwd","status":"completed","exit_code":0}}'
        )
        self.assertEqual(started, "[codex] start: /bin/zsh -lc pwd\n")
        self.assertEqual(completed, "[codex] done (0): /bin/zsh -lc pwd\n")


if __name__ == "__main__":
    unittest.main()
