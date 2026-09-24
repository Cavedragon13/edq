#!/usr/bin/env python3
"""gen_machine_inventory.py — build a live inventory of the Dragon LAN.

Runs on udragon (cron, nightly 01:50, just before nightly_commit.sh). SSHes to
each machine, collects hardware/OS/network facts, and writes:

  ~/knowledge-base/claude-sync/machines.md    human/AI-readable (Syncthing -> every machine)
  ~/knowledge-base/claude-sync/machines.json  same data for scripts

The vault is pushed to the private GitHub repo each night, so any AI with the
GitHub connector (ChatGPT, Claude.ai) can read machines.md too.

Offline machines keep their last known facts, marked with the date last seen.
Deliberately NOT collected: serial numbers, MAC addresses, usernames/passwords.
Hand-written network notes (DNS, router, services) stay in network.md.
"""

import datetime
import json
import pathlib
import subprocess

OUT_DIR = pathlib.Path.home() / "knowledge-base/claude-sync"
MD_PATH = OUT_DIR / "machines.md"
JSON_PATH = OUT_DIR / "machines.json"

# name, role, probe type, how to reach it ("local" = this machine)
MACHINES = [
    ("udragon",    "Canonical service host: Dragonsuite, GPU work, Samba, cron",   "linux",    "local"),
    ("cdragon",    "Main Mac, perma-docked (\"c\" = couch). Client/editor",           "mac",      "cdragon"),
    ("odragon",    "Mac Mini. Client/editor",                                          "mac",      "odragon"),
    ("adragon",    "Travel MacBook Air",                                               "mac",      "adragon"),
    ("minidragon", "Home services: Pi-hole, Home Assistant, Vaultwarden",              "linux",    "minidragon"),
    ("ancalagon",  "Synology NAS (JBOD file server, nightly backups)",                 "synology", "ancalagon"),
]

STATIC = [
    ("pocketdragon", "iPhone", "Tailscale only (not probed)"),
]

# Each probe prints key=value lines. Keep them POSIX-sh friendly.
PROBES = {
    "mac": r'''
hw=$(system_profiler SPHardwareDataType 2>/dev/null)
val() { printf '%s\n' "$hw" | sed -n "s/^ *$1: //p" | head -1; }
echo "model=$(val 'Model Name') ($(val 'Model Identifier'))"
echo "cpu=$(val 'Chip'), $(val 'Total Number of Cores') cores"
echo "gpu=$(system_profiler SPDisplaysDataType 2>/dev/null | sed -n 's/^ *Total Number of Cores: //p' | head -1) GPU cores (integrated)"
echo "ram=$(val 'Memory')"
echo "os=macOS $(sw_vers -productVersion) ($(sw_vers -buildVersion))"
echo "disk=$(df -H / | awk 'NR==2{print $2" total, "$4" free"}')"
echo "lan_ip=$(for i in en0 en1 en2 en3 en4 en5 en6 en7 en8; do ipconfig getifaddr $i 2>/dev/null; done | grep '^192\.168\.' | head -1)"
ts=$(command -v tailscale || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)
echo "tailscale_ip=$("$ts" ip -4 2>/dev/null | head -1)"
echo "uptime=$(uptime | sed 's/.*up \([^,]*\),.*/\1/')"
b=$(pmset -g batt 2>/dev/null | grep -o '[0-9]*%' | head -1)
[ -n "$b" ] && echo "battery=$b, $(system_profiler SPPowerDataType 2>/dev/null | sed -n 's/^ *Cycle Count: //p' | head -1) cycles, $(system_profiler SPPowerDataType 2>/dev/null | sed -n 's/^ *Condition: //p' | head -1)"
''',
    "linux": r'''
echo "model=$(cat /sys/devices/virtual/dmi/id/sys_vendor 2>/dev/null) $(cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null)"
echo "cpu=$(lscpu | sed -n 's/^Model name: *//p' | head -1), $(nproc) threads"
g=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
echo "gpu=${g:-none}"
echo "ram=$(free -g | awk '/^Mem/{print $2" GB"}')"
echo "os=$(. /etc/os-release; echo "$PRETTY_NAME"), kernel $(uname -r)"
echo "disk=$(df -H / | awk 'NR==2{print $2" total, "$4" free"}') (root)"
echo "lan_ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep '^192\.168\.' | head -1)"
echo "tailscale_ip=$(tailscale ip -4 2>/dev/null | head -1)"
echo "uptime=$(uptime -p | sed 's/^up //')"
command -v docker >/dev/null && echo "containers=$(docker ps --format '{{.Names}}' 2>/dev/null | sort | paste -sd, -)"
''',
    "synology": r'''
. /etc.defaults/VERSION 2>/dev/null
echo "model=Synology $(cat /proc/sys/kernel/syno_hw_version 2>/dev/null)"
echo "cpu=$(uname -m), $(grep -c ^processor /proc/cpuinfo) cores"
echo "ram=$(awk '/MemTotal/{printf "%.0f GB", $2/1048576}' /proc/meminfo)"
echo "os=DSM $productversion-$buildnumber"
echo "disk=$(df -H 2>/dev/null | awk '$6 ~ /^\/volume[0-9]+$/ {print $6": "$2" total, "$4" free"}' | paste -sd';' -)"
echo "lan_ip=$(ip -4 addr 2>/dev/null | sed -n 's/.*inet \(192\.168\.[0-9.]*\).*/\1/p' | head -1)"
echo "uptime=$(uptime | sed 's/.*up \([^,]*\),.*/\1/')"
''',
}


def probe(kind, target):
    cmd = ["bash", "-s"] if target == "local" else [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, "sh -s"]
    try:
        r = subprocess.run(cmd, input=PROBES[kind], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0 and not r.stdout.strip():
        return None
    facts = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip(",").strip()
            if v and v not in ("()", "none GB", ","):
                facts[k] = v
    return facts or None


def main():
    today = datetime.date.today().isoformat()
    previous = {}
    if JSON_PATH.exists():
        try:
            previous = {m["name"]: m for m in json.loads(JSON_PATH.read_text())["machines"]}
        except Exception:
            previous = {}

    machines = []
    for name, role, kind, target in MACHINES:
        facts = probe(kind, target)
        if facts:
            machines.append({"name": name, "role": role, "online": True, "last_seen": today, "facts": facts})
        elif name in previous:
            old = dict(previous[name])
            old.update(role=role, online=False)
            machines.append(old)
        else:
            machines.append({"name": name, "role": role, "online": False, "last_seen": None, "facts": {}})

    JSON_PATH.write_text(json.dumps({"generated": today, "machines": machines}, indent=2) + "\n")

    order = ["model", "cpu", "gpu", "ram", "disk", "os", "lan_ip", "tailscale_ip", "uptime", "battery", "containers"]
    labels = {"lan_ip": "LAN IP", "tailscale_ip": "Tailscale IP", "cpu": "CPU", "gpu": "GPU",
              "ram": "RAM", "os": "OS"}
    lines = [
        "# Dragon LAN — Machine Inventory",
        "",
        f"**Generated {today} by `gen_machine_inventory.py` on udragon. Do not edit by hand — "
        "changes are overwritten nightly.** Hand-written network notes (DNS, router, SSH, "
        "services) live in `network.md`.",
        "",
        "| Machine | Role | Hardware | RAM | LAN IP | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for m in machines:
        f = m["facts"]
        status = "online" if m["online"] else (f"offline (last seen {m['last_seen']})" if m["last_seen"] else "never reached")
        lines.append(f"| {m['name']} | {m['role']} | {f.get('model', '?')} | {f.get('ram', '?')} | {f.get('lan_ip', '?')} | {status} |")
    for name, role, note in STATIC:
        lines.append(f"| {name} | {role} | — | — | — | {note} |")
    lines.append("")
    for m in machines:
        lines += [f"## {m['name']}", "", f"*{m['role']}*", ""]
        if not m["facts"]:
            lines += ["No data yet.", ""]
            continue
        for k in order:
            if k in m["facts"]:
                lines.append(f"- **{labels.get(k, k.capitalize())}:** {m['facts'][k]}")
        if not m["online"]:
            lines.append(f"- **Note:** offline at last run; facts from {m['last_seen']}")
        lines.append("")
    MD_PATH.write_text("\n".join(lines))
    print(f"wrote {MD_PATH} ({sum(m['online'] for m in machines)}/{len(machines)} online)")


if __name__ == "__main__":
    main()
