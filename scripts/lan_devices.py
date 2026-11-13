#!/usr/bin/env python3
"""lan_devices.py — work out what the devices on the home LAN are.

Pi-hole's query log has no hostnames (the Arris router provides none), so this
joins four sources for every client that sent DNS to Pi-hole recently:

  1. Pi-hole FTL database: query count, last-seen time, and each client's most
     queried domains (the best hint: steam/xboxlive = gaming PC, ring.com = Ring
     device, roku.com = Roku, netflix + lge.com = LG TV, apple-dns.net = Apple...).
  2. nmap ping sweep: which addresses are up right now (and fills the ARP table).
  3. ARP table (`ip neigh`): the MAC for devices that are up or recently were.
  4. IEEE OUI table (/usr/share/ieee-data/oui.txt): MAC -> vendor. MACs with the
     "locally administered" bit set are private/randomized (iPhones, Macs, many
     Androids), so they have no vendor.

Addresses drift (DHCP, randomized MACs), so one device often shows up under many
addresses over two weeks. Treat results as hints; see knowledge-base/claude-sync/
network.md ("Other devices on the LAN") for what was concluded on 2026-11-12.

Usage (run on udragon; needs docker access to the `pihole` container and nmap):
  python3 -I scripts/lan_devices.py                 # scan now, last 14 days
  python3 -I scripts/lan_devices.py --days 30
  python3 -I scripts/lan_devices.py --nmap-file out.txt   # reuse an earlier nmap result
  python3 -I scripts/lan_devices.py | column -t -s $'\t'  # aligned view

Read-only: it only reads Pi-hole's database and pings the local /24. Output is
tab-separated, busiest client first.
"""

import argparse
import re
import subprocess
import sys

SUBNET = "192.168.7.0/24"
TOP_DOMAINS = 3
OUI_FILE = "/usr/share/ieee-data/oui.txt"


def load_oui():
    table = {}
    try:
        for line in open(OUI_FILE, errors="replace"):
            m = re.match(r"^([0-9A-F]{2})-([0-9A-F]{2})-([0-9A-F]{2})\s+\(hex\)\s+(.*)$", line.strip())
            if m:
                table["".join(m.groups()[:3]).lower()] = m.group(4).strip()
    except OSError:
        print(f"warning: {OUI_FILE} not found; vendors will be blank (apt install ieee-data)", file=sys.stderr)
    return table


def arp_table():
    out = subprocess.run(["ip", "-4", "neigh", "show"], capture_output=True, text=True).stdout
    arp = {}
    for line in out.splitlines():
        parts = line.split()
        if "lladdr" in parts:
            arp[parts[0]] = parts[parts.index("lladdr") + 1].lower()
    return arp


def scan_alive(nmap_file):
    """Return the set of addresses that answered. Reuses a saved nmap result if given."""
    if nmap_file:
        text = open(nmap_file, errors="replace").read()
    else:
        text = subprocess.run(["nmap", "-sn", "-n", SUBNET], capture_output=True, text=True).stdout
    alive = set()
    for line in text.splitlines():
        m = re.match(r"Nmap scan report for (?:\S+ \()?(\d+\.\d+\.\d+\.\d+)\)?$", line.strip())
        if m:
            alive.add(m.group(1))
    return alive


def pihole_sql(sql):
    result = subprocess.run(
        ["docker", "exec", "pihole", "pihole-FTL", "sqlite3", "-readonly",
         "/etc/pihole/pihole-FTL.db", sql],
        capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"Pi-hole query failed: {result.stderr.strip()}")
    return result.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=14, help="how far back to look (default 14)")
    ap.add_argument("--nmap-file", help="reuse saved `nmap -sn` output instead of scanning")
    args = ap.parse_args()
    days = int(args.days)  # interpolated into SQL below, so force an int

    oui = load_oui()
    alive = scan_alive(args.nmap_file)
    arp = arp_table()

    clients = pihole_sql(
        "select client, count(*), datetime(max(timestamp),'unixepoch','localtime') "
        f"from queries where timestamp > strftime('%s','now','-{days} days') "
        "and client like '192.168.7.%' group by client order by 2 desc")

    top = {}
    top_rows = pihole_sql(
        "with c as (select client, domain, count(*) n from queries "
        f"where timestamp > strftime('%s','now','-{days} days') and client like '192.168.7.%' "
        "group by client, domain), r as (select client, domain, "
        "row_number() over (partition by client order by n desc) rk from c) "
        f"select client, domain from r where rk <= {TOP_DOMAINS} order by client, rk")
    for line in top_rows.splitlines():
        client, domain = line.split("|", 1)
        top.setdefault(client, []).append(domain)

    print("ip\tqueries\tlast_seen\tup_now\tmac\tprivate_mac\tvendor\ttop_domains")
    for line in clients.splitlines():
        ip, n, last = line.split("|")
        mac = arp.get(ip, "")
        private = vendor = ""
        if mac:
            private = "yes" if int(mac[:2], 16) & 2 else "no"
            if private == "no":
                vendor = oui.get(mac.replace(":", "")[:6], "?")
        domains = " , ".join(top.get(ip, []))
        print(f"{ip}\t{n}\t{last}\t{'yes' if ip in alive else 'no'}\t{mac}\t{private}\t{vendor}\t{domains}")


if __name__ == "__main__":
    main()
