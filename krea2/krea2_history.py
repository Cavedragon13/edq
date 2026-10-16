"""Server-side prompt history shared by every browser using this runner."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


class History:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("""CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL,
            created TEXT NOT NULL, updated TEXT NOT NULL, status TEXT NOT NULL,
            payload TEXT NOT NULL, result TEXT NOT NULL)""")
        return db

    def put(self, payload, status="draft", result=None, entry_id=None):
        if not isinstance(payload, dict) or not str(payload.get("prompt", "")).strip():
            raise ValueError("A prompt is required to save history.")
        sid = str(payload.get("session_id") or uuid.uuid4())[:100]
        name = str(payload.get("session_name") or "Untitled session").strip()[:150]
        entry_id = entry_id or ("draft:" + sid if status == "draft" else str(uuid.uuid4()))
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db, db:
            db.execute("UPDATE history SET name=? WHERE session_id=?", (name, sid))
            db.execute("""INSERT INTO history VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, updated=excluded.updated,
                status=excluded.status, payload=excluded.payload, result=excluded.result""",
                (entry_id, sid, name, now, now, status, json.dumps(payload), json.dumps(result or {})))
        return entry_id

    def list(self, search="", limit=100):
        with closing(self.connect()) as db:
            rows = db.execute("""SELECT id,session_id,name,updated,status,
                substr(json_extract(payload,'$.prompt'),1,1200) AS prompt,result
                FROM history WHERE name LIKE ? OR json_extract(payload,'$.prompt') LIKE ?
                ORDER BY updated DESC LIMIT ?""", ("%" + search[:500] + "%", "%" + search[:500] + "%", limit))
            return [{"id": r["id"], "session_id": r["session_id"], "name": r["name"],
                     "updated": r["updated"], "status": r["status"],
                     "prompt": r["prompt"],
                     "image_urls": json.loads(r["result"]).get("image_urls", [])} for r in rows]

    def get(self, entry_id):
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM history WHERE id=?", (entry_id,)).fetchone()
        if row is None:
            raise KeyError("History entry not found")
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        result["result"] = json.loads(result["result"])
        return result

    def reserve_outputs(self, prefix, count, output_dir):
        """Reserve stable per-name numbers, across tabs and restarts, without overwrites."""
        with closing(self.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS output_counters (prefix TEXT PRIMARY KEY, next INTEGER NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT next FROM output_counters WHERE prefix=?', (prefix,)).fetchone()
            start = row[0] if row else 1
            while any((Path(output_dir) / f'{prefix}-{number:04d}.png').exists()
                      for number in range(start, start + count)):
                start += count
            db.execute('INSERT INTO output_counters VALUES (?,?) ON CONFLICT(prefix) DO UPDATE SET next=excluded.next',
                       (prefix, start + count))
        return [Path(output_dir) / f'{prefix}-{number:04d}.png' for number in range(start, start + count)]
