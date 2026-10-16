"""Recover previous prompts/settings from the runner's existing generation logs."""
from datetime import datetime, timezone
from contextlib import closing
import re
import shlex
import sys
from pathlib import Path

from krea2_history import History


def import_logs(log_dir, output_dir):
    history = History(log_dir / "prompt-history.sqlite3")
    count = 0
    for path in sorted(log_dir.glob("krea2-*.log")):
        entry_id = "import:" + path.stem
        try:
            history.get(entry_id)
            continue
        except KeyError:
            pass
        try:
            with path.open(errors="replace") as stream:
                header = stream.read(100000).split("\n\nSTDOUT:", 1)[0]
            args = shlex.split(header.removeprefix("$ "))
            def flag(name, default=None):
                return args[args.index(name)+1] if name in args else default
            prompt = flag("-p")
            if not prompt:
                continue
            tags = re.findall(r"<lora:[^>]+>", prompt)
            payload = {"prompt": re.sub(r"<lora:[^>]+>", "", prompt).strip(),
                       "custom_lora_tags": "".join(tags), "loras": [],
                       "session_id": "import-" + path.stem[6:14],
                       "session_name": "Earlier prompts · " + path.stem[6:14]}
            fields = {"width":"-W", "height":"-H", "steps":"--steps", "seed":"-s",
                      "batch_count":"--batch-count", "cfg_scale":"--cfg-scale",
                      "flow_shift":"--flow-shift", "sampler":"--sampling-method",
                      "lora_apply_mode":"--lora-apply-mode", "strength":"--strength"}
            payload.update({key:flag(value) for key,value in fields.items() if flag(value) is not None})
            source = flag("-i")
            if source and Path(source).parent.resolve() == (log_dir / "inputs").resolve():
                payload["saved_init_image"] = Path(source).name
            output = Path(flag("-o", "missing.png"))
            batch = int(payload.get("batch_count", 1))
            paths = [output] if batch == 1 else [output.with_name(f"{output.stem}_{i}{output.suffix}") for i in range(batch)]
            urls = ["/outputs/" + p.name for p in paths if p.parent.resolve() == output_dir.resolve() and p.exists()]
            history.put(payload, "ok" if urls else "no output", {"image_urls":urls,"log":str(path)}, entry_id)
            timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            with closing(history.connect()) as db, db:
                db.execute("UPDATE history SET created=?,updated=? WHERE id=?", (timestamp,timestamp,entry_id))
            count += 1
        except (ValueError, IndexError, OSError):
            continue
    return count


if __name__ == "__main__":
    print(f"Imported {import_logs(Path(sys.argv[1]), Path(sys.argv[2]))} previous prompts.")
