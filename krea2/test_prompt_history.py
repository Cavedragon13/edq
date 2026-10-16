import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from krea2_history import History
import krea2_runner as runner


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = History(self.root / "history.sqlite3")
        self.payload = {"prompt":"Glass dragon observatory", "session_id":"session-a",
                        "session_name":"Harbor", "width":1024, "loras":[{"tag":"a","weight":0}]}

    def test_cross_client_persistence_and_settings(self):
        entry = self.history.put(self.payload)
        other = History(self.history.path)
        self.assertEqual(other.get(entry)["payload"], self.payload)
        self.assertEqual(len(other.list("Harbor")), 1)

    def test_draft_upsert_and_generation_retention(self):
        first = self.history.put(self.payload)
        self.history.put(self.payload, "ok", {"image_urls":["/outputs/a.png"]})
        self.payload["prompt"] = "A revised observatory"
        self.assertEqual(self.history.put(self.payload), first)
        self.assertEqual(len(self.history.list()), 2)
        self.assertEqual(self.history.get(first)["payload"]["prompt"], self.payload["prompt"])

    def test_sessions_and_search_are_separate(self):
        self.history.put(self.payload)
        self.history.put({**self.payload,"session_id":"b","prompt":"Mountain chapel"})
        self.assertEqual(len(self.history.list()), 2)
        self.assertEqual(len(self.history.list("Mountain")), 1)
        self.assertEqual(self.history.list("' OR 1=1 --"), [])

    def test_rename_preserves_group(self):
        entry = self.history.put(self.payload, "ok")
        self.history.put({**self.payload,"session_name":"Renamed"})
        self.assertEqual(self.history.get(entry)["name"], "Renamed")

    def test_sequential_outputs_persist_and_do_not_overwrite(self):
        (self.root / 'Harbor-0001.png').write_bytes(b'existing')
        paths = self.history.reserve_outputs('Harbor', 2, self.root)
        self.assertEqual([p.name for p in paths], ['Harbor-0003.png','Harbor-0004.png'])
        other = History(self.history.path)
        self.assertEqual(other.reserve_outputs('Harbor', 1, self.root)[0].name,'Harbor-0005.png')
        self.assertEqual((self.root/'Harbor-0001.png').read_bytes(),b'existing')

    def test_validation_error_releases_generation_lock(self):
        with patch.object(runner,"status_payload",return_value={"ready":True}), \
             patch.object(runner,"OUTPUT_DIR",self.root), patch.object(runner,"LOG_DIR",self.root), \
             patch.object(runner,"save_init_image",side_effect=ValueError("bad image")):
            with self.assertRaises(ValueError):
                runner.run_generation(self.payload)
        self.assertFalse(runner.GENERATE_LOCK.locked())

    def test_oom_saved_and_lock_released(self):
        with patch.object(runner,"status_payload",return_value={"ready":True}), \
             patch.object(runner,"OUTPUT_DIR",self.root), patch.object(runner,"LOG_DIR",self.root), \
             patch.object(runner,"HISTORY",self.history), patch.object(runner,"build_command",return_value=["fake"]), \
             patch.object(runner,"lora_prompt",return_value=("prompt",[])), \
             patch.object(runner.subprocess,"run",return_value=subprocess.CompletedProcess([],1,"","cudaMalloc failed: out of memory")):
            with self.assertRaisesRegex(RuntimeError,"GPU memory ran out"):
                runner.run_generation(self.payload)
        self.assertFalse(runner.GENERATE_LOCK.locked())
        self.assertEqual(self.history.list()[0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
