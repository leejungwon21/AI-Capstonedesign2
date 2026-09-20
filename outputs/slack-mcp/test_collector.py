import unittest
from collector import collect

class CollectorTests(unittest.TestCase):
    def test_allowlist(self):
        with self.assertRaises(ValueError):
            collect("C0C2ZMZ1ZPW", lambda _: self.fail("Must not request private channel"))

    def test_pagination_and_labels(self):
        def fetch(p):
            self.assertEqual(p["channel"], "C0C3QGPCB0Q")
            indices = [6, 5, 4] if not p.get("cursor") else [3, 2, 1]
            return {"messages": [{"ts": f"100.{i:06}", "user": "ONE_ACCOUNT",
                      "text": f"[S{i:03} | Tuesday]\nManager → Intern\nMessage {i}"} for i in indices],
                    "response_metadata": {"next_cursor": "page2" if not p.get("cursor") else ""}}
        result = collect("sap", fetch)
        self.assertTrue(result["complete"])
        self.assertEqual(result["records"][0]["source_id"], "S001")
        self.assertEqual(result["records"][0]["speaker_label"], "Manager → Intern")

    def test_missing_and_threads_are_not_complete(self):
        result = collect("sap", lambda _: {"messages": [{"ts": "1.000001", "text": "[S001 | t]\na\nb", "reply_count": 1}]})
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["missing_ids"]), 5)
        self.assertTrue(result["thread_parent_ts"])

    def test_repeated_cursor_fails(self):
        with self.assertRaises(RuntimeError):
            collect("sap", lambda _: {"messages": [], "response_metadata": {"next_cursor": "same"}})

if __name__ == "__main__":
    unittest.main()
