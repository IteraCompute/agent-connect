import json
import unittest

from iteraconnect.smoke import reply_received


class SmokeEvidenceTests(unittest.TestCase):
    def test_echoed_prompt_or_error_is_not_client_success(self):
        for target in ("claude", "codex", "openclaw", "hermes"):
            self.assertFalse(reply_received(target, 'Asked: "Reply with exactly ITERACONNECT_OK".'))
        self.assertFalse(
            reply_received(
                "openclaw",
                json.dumps({"payloads": [{"text": "Failed"}], "debug": "ITERACONNECT_OK"}),
            )
        )
        self.assertFalse(
            reply_received(
                "codex",
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "ITERACONNECT_OK"},
                    }
                ),
            )
        )

    def test_success_requires_actual_completed_reply(self):
        self.assertTrue(
            reply_received(
                "hermes", json.dumps({"type": "result", "exit_code": 0, "text": "ITERACONNECT_OK"})
            )
        )
        self.assertFalse(
            reply_received(
                "hermes", json.dumps({"type": "result", "exit_code": 1, "text": "ITERACONNECT_OK"})
            )
        )
        self.assertFalse(
            reply_received("hermes", json.dumps({"type": "text", "text": "ITERACONNECT_OK"}))
        )
        self.assertTrue(reply_received("claude", "ITERACONNECT_OK\n"))
        self.assertTrue(
            reply_received("openclaw", json.dumps({"payloads": [{"text": "ITERACONNECT_OK"}]}))
        )
        self.assertTrue(
            reply_received(
                "codex",
                "\n".join(
                    json.dumps(e)
                    for e in [
                        {
                            "type": "item.completed",
                            "item": {"type": "agent_message", "text": "ITERACONNECT_OK"},
                        },
                        {"type": "turn.completed", "usage": {}},
                    ]
                ),
            )
        )
