#!/usr/bin/env python3
"""Replace byte-identical model files with hard links — safely, in three steps.

  link      for each duplicate: rename to <file>.dedupe-bak, hard-link the kept copy
            into its place (every path keeps working; the original bytes stay on disk)
  verify    re-hash every linked path through the new link against the group sha256
  finalize  delete the .dedupe-bak copies (frees the space) — run only after the
            affected services pass their tests
  rollback  put every .dedupe-bak back

The plan is a JSON list of {"size", "sha256", "files": [...]} groups, verified by
full sha256 (see the survey that produced it). The journal of what was linked is
written next to the plan so finalize/rollback act on exactly those files.

  python3 scripts/dedupe_models.py link     PLAN.json
  python3 scripts/dedupe_models.py verify   PLAN.json
  python3 scripts/dedupe_models.py finalize PLAN.json [KEEP_SUBSTRING ...]
  python3 scripts/dedupe_models.py rollback PLAN.json
"""
import hashlib
import json
import os
import sys
from pathlib import Path

BAK = ".dedupe-bak"


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(16 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    mode, plan_path = sys.argv[1], Path(sys.argv[2])
    journal_path = plan_path.with_suffix(".journal.json")
    plan = json.loads(plan_path.read_text())

    if mode == "link":
        journal = []
        for g in plan:
            keep, *dupes = g["files"]
            for d in dupes:
                if os.path.samefile(keep, d):
                    continue                      # already linked
                os.rename(d, d + BAK)
                os.link(keep, d)
                journal.append({"file": d, "keep": keep, "sha256": g["sha256"], "size": g["size"]})
                print(f"linked  {d}")
        journal_path.write_text(json.dumps(journal, indent=1))
        print(f"{len(journal)} files linked; originals kept as *{BAK} until finalize")

    elif mode == "verify":
        journal = json.loads(journal_path.read_text())
        bad = 0
        for j in journal:
            ok = os.path.samefile(j["file"], j["keep"]) and sha256(j["file"]) == j["sha256"]
            bad += not ok
            print(f"{'ok  ' if ok else 'FAIL'}  {j['file']}")
        print(f"{len(journal) - bad}/{len(journal)} verified")
        sys.exit(1 if bad else 0)

    elif mode == "finalize":
        # optional extra args: path substrings whose backups must be KEPT
        # (their service hasn't passed its test yet)
        keep = sys.argv[3:]
        journal = json.loads(journal_path.read_text())
        freed = 0
        for j in journal:
            b = j["file"] + BAK
            if any(k in j["file"] for k in keep):
                if os.path.exists(b):
                    print(f"kept    {b}")
                continue
            if os.path.exists(b):
                os.remove(b)
                freed += j["size"]
        print(f"removed backups, freed {freed / 1024**3:.1f} GB")

    elif mode == "rollback":
        journal = json.loads(journal_path.read_text())
        for j in journal:
            b = j["file"] + BAK
            if os.path.exists(b):
                os.remove(j["file"])
                os.rename(b, j["file"])
                print(f"restored {j['file']}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
