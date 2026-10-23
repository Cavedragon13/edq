"""Regression checks for service ownership, eviction and restore without loading models."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import overnight_services as services
import overnight_supervisor as supervisor


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = Path(self.temp.name) / "services.json"
        services.save(self.journal, {"dry_run": False, "preexisting": ["krea2-turbo"],
                                     "evicted": [], "owned": {}})

    def test_running_krea_blocks_competing_launch(self):
        rows = [{"id": "test", "running": False}, {"id": "krea2-turbo", "running": True}]
        with patch.object(services, "api", return_value={"services": rows}) as api:
            with self.assertRaises(RuntimeError):
                services.start(self.journal, "test")
        self.assertEqual(api.call_count, 1)
        self.assertEqual(json.loads(self.journal.read_text())["owned"], {})

    def test_evicted_service_may_be_tested(self):
        services.save(self.journal, {"dry_run": False, "preexisting": ["moss-image"],
                                     "evicted": ["moss-image"], "owned": {}})
        rows = [{"id": "moss-image", "running": False, "vram_gb": 3.0}]
        with patch.object(services, "api", return_value={"services": rows}), \
             patch.object(services.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "")):
            services.start(self.journal, "moss-image")
        self.assertIn("moss-image", json.loads(self.journal.read_text())["owned"])

    def test_record_before_launch_even_when_request_fails(self):
        def api(path, post=False):
            if post:
                self.assertIn("test", json.loads(self.journal.read_text())["owned"])
                raise OSError("request failed after server may have launched")
            return {"services": [{"id": "test", "running": False}]}
        with patch.object(services, "api", side_effect=api), patch.object(
                services.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "")):
            with self.assertRaises(OSError):
                services.start(self.journal, "test")

    def test_cleanup_never_stops_preexisting_or_krea(self):
        services.save(self.journal, {"preexisting": ["existing"],
                                     "owned": {"test": 0, "existing": 0, "krea2-turbo": 0}})
        with patch.object(services, "api", return_value={"services": []}) as api:
            with patch.object(services.time, "sleep"):
                services.cleanup(self.journal)
        stops = [c.args[0] for c in api.call_args_list if c.kwargs.get("post")]
        self.assertEqual(stops, ["/api/stop/test"])

    def test_cleanup_survives_deleted_journal(self):
        self.journal.unlink()
        fallback = {"preexisting": [], "evicted": [], "owned": {"test": 0}}
        with patch.object(services, "api", return_value={"services": []}) as api:
            with patch.object(services.time, "sleep"):
                services.cleanup(self.journal, fallback)
        stops = [c.args[0] for c in api.call_args_list if c.kwargs.get("post")]
        self.assertEqual(stops, ["/api/stop/test"])

    def test_excluded_dedupe_services(self):
        for sid in ("minimax-music3",):
            with patch.object(services, "api", return_value={"services": [{"id": sid}]}):
                with self.assertRaises(RuntimeError):
                    services.start(self.journal, sid)

    def test_gpu_query_failure_prevents_launch(self):
        with patch.object(services, "api", return_value={"services": [{"id": "test", "running": False}]}) as api, \
             patch.object(services.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "nvidia-smi")):
            with self.assertRaises(subprocess.CalledProcessError):
                services.start(self.journal, "test")
        self.assertEqual(api.call_count, 1)
        self.assertEqual(json.loads(self.journal.read_text())["owned"], {})

    def test_dry_run_prevents_launch(self):
        services.save(self.journal, {"dry_run": True, "preexisting": [], "owned": {}})
        with patch.object(services, "api", return_value={"services": [{"id": "test", "running": False}]}) as api:
            with self.assertRaises(RuntimeError):
                services.start(self.journal, "test")
        self.assertEqual(api.call_count, 1)

    def run_supervisor(self, fail_wait=False, busy=True, rows=None):
        """Simulate a run against a fake dashboard. Returns (rc, POSTed paths, report text)."""
        report = Path(self.temp.name) / "report.md"
        running = {r["id"] for r in (rows or []) if r["running"]}
        posts = []

        def api(path, post=False):
            if post:
                posts.append(path)
                sid = path.split("/")[-1].split("?")[0]
                if path.startswith("/api/stop/"):
                    running.discard(sid)
                else:
                    running.add(sid)
                return {"status": "stopped" if "stop" in path else "started"}
            return {"services": [dict(r, running=r["id"] in running) for r in (rows or [])]}

        child = unittest.mock.Mock(pid=99999999, returncode=0)
        child.poll.return_value = None if fail_wait else 0
        with patch.dict("os.environ", {"OVERNIGHT_SERVICE_JOURNAL": str(self.journal),
                                      "OVERNIGHT_REPORT": str(report), "DRY_RUN": "0"}), \
             patch.object(supervisor, "api", side_effect=api), \
             patch.object(supervisor, "gpu_busy", return_value=(busy, 50 if busy else 0)), \
             patch.object(supervisor, "ollama_unload", return_value=[]), \
             patch.object(supervisor, "gpu_used_mib", return_value=900), \
             patch.object(supervisor.subprocess, "Popen", return_value=child), \
             patch.object(supervisor.os, "killpg"), \
             patch.object(supervisor.signal, "signal"), \
             patch.object(supervisor.time, "sleep", side_effect=InterruptedError("interrupted")), \
             patch.object(supervisor, "cleanup") as cleanup:
            rc = supervisor.main()
        cleanup.assert_called_once()
        self.assertEqual(cleanup.call_args.args[0], self.journal)
        self.assertTrue(report.exists())
        return rc, posts, report.read_text()

    def test_normal_exit_always_cleans(self):
        self.assertEqual(self.run_supervisor()[0], 0)

    def test_interrupted_wait_always_cleans(self):
        self.assertEqual(self.run_supervisor(fail_wait=True)[0], 1)

    def test_busy_gpu_evicts_nothing(self):
        rows = [{"id": "krea2-turbo", "running": True}, {"id": "moss-image", "running": True, "vram_gb": 3.0}]
        rc, posts, _ = self.run_supervisor(busy=True, rows=rows)
        self.assertEqual(rc, 0)
        self.assertEqual(posts, [])

    def test_idle_gpu_evicts_then_restores(self):
        rows = [{"id": "krea2-turbo", "running": True}, {"id": "moss-image", "running": True, "vram_gb": 3.0},
                {"id": "jellyfin", "running": True}, {"id": "gemma4", "running": True}]
        rc, posts, text = self.run_supervisor(busy=False, rows=rows)
        self.assertEqual(rc, 0)
        self.assertEqual(posts, ["/api/stop/krea2-turbo", "/api/stop/moss-image",
                                 "/api/start/krea2-turbo", "/api/start/moss-image"])
        self.assertIn("restored and verified running: krea2-turbo, moss-image", text)


if __name__ == "__main__":
    unittest.main()
