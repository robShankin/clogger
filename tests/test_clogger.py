import tempfile
import unittest
from pathlib import Path
from unittest import mock

import clogger


def codex_transcript(workspace: Path, session_id: str, turn_id: str, user_text: str, assistant_text: str) -> str:
    return "\n".join(
        [
            (
                '{"timestamp":"2026-03-27T00:00:00Z","type":"session_meta","payload":'
                f'{{"id":"{session_id}","cwd":"{workspace}","originator":"Codex Desktop"}}'
                "}"
            ),
            (
                '{"timestamp":"2026-03-27T00:00:01Z","type":"response_item","payload":'
                '{"type":"message","role":"user","content":[{"type":"input_text","text":"'
                f"{user_text}"
                '"}]}}'
            ),
            (
                '{"timestamp":"2026-03-27T00:00:03Z","type":"event_msg","payload":'
                f'{{"type":"task_complete","turn_id":"{turn_id}","last_agent_message":"{assistant_text}"}}'
                "}"
            ),
            "",
        ]
    )


class CloggerTests(unittest.TestCase):
    def test_parse_latest_turn_uses_task_complete(self):
        entries = [
            {
                "timestamp": "2026-03-27T00:00:01Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "build a parser"}],
                },
            },
            {
                "timestamp": "2026-03-27T00:00:03Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": "turn-123",
                    "last_agent_message": "Implemented the parser.",
                },
            },
        ]

        turn = clogger.parse_latest_turn(entries)

        self.assertEqual(turn["turn_id"], "turn-123")
        self.assertEqual(turn["user_text"], "build a parser")
        self.assertEqual(turn["assistant_text"], "Implemented the parser.")

    def test_hook_stop_logs_exchange_once(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            workspace = root / "workspace"
            workspace.mkdir()

            transcript_root = root / ".codex" / "sessions" / "2026" / "03" / "27"
            transcript_root.mkdir(parents=True)
            transcript_path = transcript_root / "rollout-2026-03-27T00-00-00-session-abc.jsonl"
            transcript_path.write_text(
                codex_transcript(
                    workspace=workspace,
                    session_id="session-abc",
                    turn_id="turn-1",
                    user_text="write a python function",
                    assistant_text="Here is the function.",
                )
            )

            with mock.patch.object(clogger, "TRANSCRIPT_ROOTS", (root / ".codex" / "sessions",)):
                start_message = clogger.start_session(workspace)
                self.assertIn("clogger on ->", start_message)

                stop_payload = {"cwd": str(workspace), "session_id": "session-abc"}
                prompt_payload = {
                    "cwd": str(workspace),
                    "session_id": "session-abc",
                    "prompt": "write a python function",
                }

                clogger.hook_user_prompt_submit(prompt_payload)
                clogger.hook_stop(stop_payload)
                clogger.hook_stop(stop_payload)

                state = clogger.load_session_state(workspace, "session-abc")
                log_file = Path(state["log_file"])
                contents = log_file.read_text()

                self.assertIn("USER: /clogger", contents)
                self.assertIn("USER: write a python function", contents)
                self.assertIn("CODEX: Here is the function.", contents)
                self.assertEqual(contents.count("USER: write a python function"), 1)

    def test_hook_user_prompt_submit_ignores_internal_skill_text(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir()
            state = {
                "version": 2,
                "enabled": True,
                "session_id": "session-1",
                "cwd": str(workspace),
                "transcript_path": str(workspace / "missing.jsonl"),
                "log_file": str(workspace / "clogger-files" / "clogger_test.txt"),
                "agent_label": "CLAUDE",
                "pending_user": None,
                "pending_elicitation": None,
                "pending_elicitation_result": None,
                "last_logged_turn_id": None,
                "last_logged_exchange_hash": None,
            }
            clogger.save_session_state(workspace, "session-1", state)

            clogger.hook_user_prompt_submit(
                {
                    "cwd": str(workspace),
                    "session_id": "session-1",
                    "prompt": "Base directory for this skill: /Users/test/.claude/skills/clogger\n\nManage clogger...",
                    "timestamp": "2026-03-27T02:55:27Z",
                }
            )

            saved = clogger.load_session_state(workspace, "session-1")
            self.assertIsNone(saved["pending_user"])

    def test_hook_user_prompt_submit_ignores_clogger_command_markup(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir()
            state = {
                "version": 2,
                "enabled": True,
                "session_id": "session-1",
                "cwd": str(workspace),
                "transcript_path": str(workspace / "missing.jsonl"),
                "log_file": str(workspace / "clogger-files" / "clogger_test.txt"),
                "agent_label": "CLAUDE",
                "pending_user": None,
                "pending_elicitation": None,
                "pending_elicitation_result": None,
                "last_logged_turn_id": None,
                "last_logged_exchange_hash": None,
            }
            clogger.save_session_state(workspace, "session-1", state)

            clogger.hook_user_prompt_submit(
                {
                    "cwd": str(workspace),
                    "session_id": "session-1",
                    "prompt": "<command-message>clogger</command-message>\n<command-name>/clogger</command-name>\n<command-args>start</command-args>",
                    "timestamp": "2026-03-27T03:02:18Z",
                }
            )

            saved = clogger.load_session_state(workspace, "session-1")
            self.assertIsNone(saved["pending_user"])

    def test_parse_latest_turn_supports_claude_transcript_shape(self):
        entries = [
            {
                "timestamp": "2026-03-27T01:57:13Z",
                "type": "user",
                "message": {"role": "user", "content": "where did we leave off?"},
            },
            {
                "timestamp": "2026-03-27T01:57:25Z",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "We were building the sample app."}],
                    "stop_reason": "end_turn",
                },
            },
        ]

        turn = clogger.parse_latest_turn(entries)

        self.assertEqual(turn["user_text"], "where did we leave off?")
        self.assertEqual(turn["assistant_text"], "We were building the sample app.")

    def test_parse_latest_turn_ignores_clogger_command_markup(self):
        entries = [
            {
                "timestamp": "2026-03-27T03:02:18Z",
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "<command-message>clogger</command-message>\n<command-name>/clogger</command-name>\n<command-args>start</command-args>",
                },
            },
            {
                "timestamp": "2026-03-27T03:02:22Z",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "clogger on -> clogger_2026-03-27_test.txt"}],
                    "stop_reason": "end_turn",
                },
            },
        ]

        turn = clogger.parse_latest_turn(entries)

        self.assertIsNotNone(turn)
        self.assertNotIn("user_text", turn)
        self.assertEqual(turn["assistant_text"], "clogger on -> clogger_2026-03-27_test.txt")

    def test_hook_stop_prefers_last_assistant_message_from_payload(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            workspace = root / "workspace"
            workspace.mkdir()

            transcript_root = root / ".claude" / "projects" / "workspace"
            transcript_root.mkdir(parents=True)
            transcript_path = transcript_root / "session-claude.jsonl"
            transcript_path.write_text("")

            state = {
                "version": 2,
                "enabled": True,
                "session_id": "session-claude",
                "cwd": str(workspace),
                "transcript_path": str(transcript_path),
                "log_file": str(workspace / "clogger-files" / "clogger_test.txt"),
                "agent_label": "CLAUDE",
                "pending_user": {
                    "text": "what were we building?",
                    "timestamp": "2026-03-27T02:10:00Z",
                },
                "last_logged_turn_id": None,
                "last_logged_exchange_hash": None,
            }
            clogger.save_session_state(workspace, "session-claude", state)

            payload = {
                "cwd": str(workspace),
                "session_id": "session-claude",
                "last_assistant_message": "We were building the sample app.",
                "timestamp": "2026-03-27T02:10:05Z",
            }

            clogger.hook_stop(payload)

            saved = clogger.load_session_state(workspace, "session-claude")
            contents = Path(saved["log_file"]).read_text()

            self.assertIn("USER: what were we building?", contents)
            self.assertIn("CLAUDE: We were building the sample app.", contents)
            self.assertIsNone(saved["pending_user"])

    def test_hook_stop_uses_payload_for_reply_but_transcript_for_ask_user_question_details(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            workspace = root / "workspace"
            workspace.mkdir()

            transcript_root = root / ".claude" / "projects" / "workspace"
            transcript_root.mkdir(parents=True)
            transcript_path = transcript_root / "session-claude.jsonl"
            transcript_path.write_text(
                "\n".join(
                    [
                        '{"timestamp":"2026-03-27T02:50:01Z","type":"user","message":{"role":"user","content":"show me an elicitation list"}}',
                        '{"timestamp":"2026-03-27T02:50:05Z","type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"AskUserQuestion","input":{"questions":[{"question":"Which vegetables would you like to work with?","options":[{"label":"Carrots"},{"label":"Broccoli"}]}]}}],"stop_reason":"tool_use"}}',
                        '{"timestamp":"2026-03-27T02:50:10Z","type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"answer recorded"}]},"toolUseResult":{"questions":[{"question":"Which vegetables would you like to work with?"}],"answers":{"Which vegetables would you like to work with?":"Carrots"}}}',
                        "",
                    ]
                )
            )

            state = {
                "version": 2,
                "enabled": True,
                "session_id": "session-claude",
                "cwd": str(workspace),
                "transcript_path": str(transcript_path),
                "log_file": str(workspace / "clogger-files" / "clogger_test.txt"),
                "agent_label": "CLAUDE",
                "pending_user": {
                    "text": "show me an elicitation list",
                    "timestamp": "2026-03-27T02:50:01Z",
                },
                "pending_elicitation": None,
                "pending_elicitation_result": None,
                "last_logged_turn_id": None,
                "last_logged_exchange_hash": None,
            }
            clogger.save_session_state(workspace, "session-claude", state)

            clogger.hook_stop(
                {
                    "cwd": str(workspace),
                    "session_id": "session-claude",
                    "timestamp": "2026-03-27T02:50:16Z",
                    "last_assistant_message": "Perfect! You selected Carrots.",
                }
            )

            saved = clogger.load_session_state(workspace, "session-claude")
            contents = Path(saved["log_file"]).read_text()

            self.assertIn("USER: show me an elicitation list", contents)
            self.assertIn("CLAUDE: Which vegetables would you like to work with?", contents)
            self.assertIn("SELECTED: Which vegetables would you like to work with? -> Carrots", contents)
            self.assertIn("CLAUDE: Perfect! You selected Carrots.", contents)
            self.assertIn("[2026-03-27T02:50:16Z] CLAUDE: Perfect! You selected Carrots.", contents)

    def test_hook_stop_does_not_reuse_old_ask_user_question_details_on_later_turn(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            workspace = root / "workspace"
            workspace.mkdir()

            transcript_root = root / ".claude" / "projects" / "workspace"
            transcript_root.mkdir(parents=True)
            transcript_path = transcript_root / "session-claude.jsonl"
            transcript_path.write_text(
                "\n".join(
                    [
                        '{"timestamp":"2026-03-27T03:09:59Z","type":"user","message":{"role":"user","content":"ask me a question with the ask user a question tool"}}',
                        '{"timestamp":"2026-03-27T03:10:04.002Z","type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"AskUserQuestion","input":{"questions":[{"question":"What would you like to work on today?","options":[{"label":"Code"},{"label":"Other"}]}]}}],"stop_reason":"tool_use"}}',
                        '{"timestamp":"2026-03-27T03:10:08.214Z","type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"answer recorded"}]},"toolUseResult":{"questions":[{"question":"What would you like to work on today?"}],"answers":{"What would you like to work on today?":"Other"}}}',
                        '{"timestamp":"2026-03-27T03:10:09Z","type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Got it! Since you selected Other, what would you like to work on?"}],"stop_reason":"end_turn"}}',
                        '{"timestamp":"2026-03-27T03:10:32Z","type":"user","message":{"role":"user","content":"that is great, it did not break"}}',
                        "",
                    ]
                )
            )

            state = {
                "version": 2,
                "enabled": True,
                "session_id": "session-claude",
                "cwd": str(workspace),
                "transcript_path": str(transcript_path),
                "log_file": str(workspace / "clogger-files" / "clogger_test.txt"),
                "agent_label": "CLAUDE",
                "pending_user": {
                    "text": "that is great, it did not break",
                    "timestamp": "2026-03-27T03:10:32Z",
                },
                "pending_elicitation": None,
                "pending_elicitation_result": None,
                "last_logged_turn_id": None,
                "last_logged_exchange_hash": None,
            }
            clogger.save_session_state(workspace, "session-claude", state)

            clogger.hook_stop(
                {
                    "cwd": str(workspace),
                    "session_id": "session-claude",
                    "timestamp": "2026-03-27T03:10:35Z",
                    "last_assistant_message": "Excellent! Glad the clogger skill is working smoothly.",
                }
            )

            contents = (workspace / "clogger-files" / "clogger_test.txt").read_text()

            self.assertIn("USER: that is great, it did not break", contents)
            self.assertIn("CLAUDE: Excellent! Glad the clogger skill is working smoothly.", contents)
            self.assertNotIn("SELECTED:", contents)
            self.assertNotIn("What would you like to work on today?", contents)

    def test_hook_logs_elicitation_selection(self):
        entries = [
            {
                "timestamp": "2026-03-27T02:45:55Z",
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "show me a real selectable list",
                },
            },
            {
                "timestamp": "2026-03-27T02:45:58Z",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "AskUserQuestion",
                            "input": {
                                "questions": [
                                    {
                                        "question": "Which option would you like to choose?",
                                        "options": [
                                            {"label": "Option A"},
                                            {"label": "Option B"},
                                        ],
                                    }
                                ]
                            },
                        }
                    ],
                    "stop_reason": "tool_use",
                },
            },
            {
                "timestamp": "2026-03-27T02:46:02Z",
                "type": "user",
                "toolUseResult": {
                    "questions": [
                        {"question": "Which option would you like to choose?"}
                    ],
                    "answers": {
                        "Which option would you like to choose?": "Option B"
                    },
                },
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "content": 'User has answered your questions: "Which option would you like to choose?"="Option B".',
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-03-27T02:46:04Z",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "You selected Option B!",
                        }
                    ],
                    "stop_reason": None,
                },
            },
        ]

        turn = clogger.parse_latest_turn(entries)

        self.assertEqual(turn["user_text"], "show me a real selectable list")
        self.assertEqual(turn["elicitation_prompt"], "Which option would you like to choose?")
        self.assertEqual(
            turn["elicitation_selection"],
            "Which option would you like to choose? -> Option B",
        )
        self.assertEqual(turn["assistant_text"], "You selected Option B!")


if __name__ == "__main__":
    unittest.main()
