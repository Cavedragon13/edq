#!/usr/bin/env python3
"""
Trading Dashboard — port 8048
Serves a live dark-mode portfolio dashboard.
  GET /              -> HTML dashboard (auto-refreshes every 30s)
  GET /api/portfolio -> combined portfolio JSON from both ledgers
"""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import datetime as dt
from dotenv import load_dotenv

load_dotenv("/srv/containers/edq/.env")
API_KEY = os.getenv("TRADING_DASHBOARD_API_KEY", "")

BASE      = Path(__file__).parent
DW_LEDGER = BASE / "dragonweyr/paper_ledger.json"
KS_LEDGER = BASE / "kalshi/paper_ledger.json"
TRADE_LOG = BASE / "trading_log.jsonl"
PORT      = 8048

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f0f1a; color: #e0e0e0; font-family: 'Courier New', monospace; font-size: 13px; }
header {
  background: #1a1a2e; border-bottom: 1px solid #2d2d4e;
  padding: 14px 24px; display: flex; justify-content: space-between; align-items: center;
}
header h1 { font-size: 16px; font-weight: 700; letter-spacing: 2px; color: #7dd3fc; }
.ts { color: #6b7280; font-size: 11px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #22c55e; margin-right: 6px; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
main { padding: 20px 24px; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 24px; }
.card { background: #1a1a2e; border: 1px solid #2d2d4e; border-radius: 8px; padding: 14px; }
.card .lbl { color: #9ca3af; font-size: 10px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; }
.card .val { font-size: 22px; font-weight: 700; }
.pos { color: #22c55e; } .neg { color: #ef4444; } .neu { color: #e0e0e0; }
h2 { font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: #9ca3af;
  margin: 20px 0 10px; border-bottom: 1px solid #2d2d4e; padding-bottom: 6px; }
.wrap { overflow-x: auto; margin-bottom: 8px; }
table { width: 100%; border-collapse: collapse; }
th { background: #1a1a2e; color: #9ca3af; font-size: 10px; letter-spacing: 1px;
  text-transform: uppercase; padding: 7px 10px; text-align: left; border-bottom: 1px solid #2d2d4e; }
td { padding: 7px 10px; border-bottom: 1px solid #1e1e30; vertical-align: top; }
tr:hover td { background: #1a1a2e; }
.badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 700; }
.b-pm { background: #2d1a4e; color: #c084fc; }
.b-ks { background: #1a2d4e; color: #60a5fa; }
.b-no { background: #2d1a1a; color: #f87171; }
.b-ye { background: #1a2d1a; color: #4ade80; }
.feed { max-height: 280px; overflow-y: auto; }
.fe { padding: 6px 10px; border-bottom: 1px solid #1e1e30; display: flex; gap: 10px; align-items: flex-start; }
.ft { font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 3px; white-space: nowrap; }
.fc { background: #3b1515; color: #f87171; }
.fn { background: #153b15; color: #4ade80; }
.fh { background: #1e1e30; color: #9ca3af; }
.fg { background: #1e2d1e; color: #86efac; }
.fx { color: #d1d5db; font-size: 11px; flex: 1; }
.fts { color: #6b7280; font-size: 10px; white-space: nowrap; }
.err { background: #2d1515; color: #f87171; padding: 12px; border-radius: 6px; margin: 12px 0; }
.ld  { color: #6b7280; padding: 40px; text-align: center; }
.trunc { max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
</head>
<body>
<header>
  <h1>TRADING DASHBOARD</h1>
  <div><span class="dot"></span><span class="ts" id="ts">Loading...</span></div>
</header>
<main id="root"><div class="ld">Fetching portfolio...</div></main>
<script>
function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function fmt(v, dec) {
  if (v == null) return '\u2014';
  dec = dec == null ? 2 : dec;
  return (v < 0 ? '-$' : '$') + Math.abs(v).toFixed(dec);
}
function pct(v) { return v == null ? '\u2014' : v.toFixed(1) + '%'; }
function pc(v) { return v == null ? 'neu' : v > 0 ? 'pos' : v < 0 ? 'neg' : 'neu'; }
function card(lbl, val, cls) {
  return '<div class="card"><div class="lbl">' + esc(lbl) + '</div><div class="val ' + cls + '">' + esc(val) + '</div></div>';
}
function platBadge(p) { return '<span class="badge ' + (p === 'polymarket' ? 'b-pm">PM' : 'b-ks">KS') + '</span>'; }
function intentBadge(i) { return '<span class="badge ' + (i === 'BUY_NO' ? 'b-no">BUY_NO' : 'b-ye">BUY_YES') + '</span>'; }

function render(d) {
  const s = d.summary;
  document.getElementById('ts').textContent =
    new Date(d.ts).toLocaleString('en-US', {hour12: false});

  let h = '';

  // Summary cards
  h += '<div class="summary-grid">';
  h += card('Total P&L',  fmt(s.total_pnl_usd),      pc(s.total_pnl_usd));
  h += card('Realized',   fmt(s.realized_pnl_usd),   pc(s.realized_pnl_usd));
  h += card('Unrealized', fmt(s.unrealized_pnl_usd), pc(s.unrealized_pnl_usd));
  h += card('Cash',       fmt(s.total_cash_usd),      'neu');
  h += card('Open',       String(s.num_open),          'neu');
  h += card('Closed',     String(s.num_closed),        'neu');
  h += '</div>';

  // Open positions
  if (d.positions.length) {
    h += '<h2>Open Positions</h2><div class="wrap"><table>';
    h += '<tr><th>ID</th><th>Market</th><th>Plt</th><th>Intent</th><th>Entry</th><th>Cur YES</th><th>MTM P&L</th><th>My Prob</th><th>Edge</th><th>Resolves</th></tr>';
    for (const t of d.positions) {
      const dl   = t.decision_log || [];
      const last = dl[dl.length - 1] || {};
      const mtm  = last.mtm_pnl_usd;
      const mpct = last.mtm_pnl_pct;
      const ep   = t.no_price_at_entry || t.no_mid_at_entry || t.yes_price_at_entry || t.yes_mid_at_entry;
      const myP  = t.intent === 'BUY_NO' ? t.my_probability_no : t.my_probability_yes;
      const curY = last.bbo_yes;
      h += '<tr>';
      h += '<td>' + esc(t.id) + '</td>';
      h += '<td class="trunc">' + esc(t.market) + '</td>';
      h += '<td>' + platBadge(t.platform) + '</td>';
      h += '<td>' + intentBadge(t.intent) + '</td>';
      h += '<td>' + (ep != null ? ep.toFixed(3) : '\u2014') + '</td>';
      h += '<td>' + (curY != null ? curY.toFixed(3) : '\u2014') + '</td>';
      h += '<td class="' + pc(mtm) + '">' + fmt(mtm) + (mpct != null ? ' (' + pct(mpct) + ')' : '') + '</td>';
      h += '<td>' + (myP != null ? (myP * 100).toFixed(0) + '%' : '\u2014') + '</td>';
      h += '<td>' + (t.edge_pp != null ? t.edge_pp + 'pp' : '\u2014') + '</td>';
      h += '<td>' + esc(t.resolves || '') + '</td>';
      h += '</tr>';
    }
    h += '</table></div>';
  }

  // Closed trades
  if (d.closed.length) {
    h += '<h2>Closed Trades</h2><div class="wrap"><table>';
    h += '<tr><th>ID</th><th>Market</th><th>Plt</th><th>Opened</th><th>Closed</th><th>P&L</th><th>P&L%</th></tr>';
    for (const t of [...d.closed].reverse()) {
      h += '<tr>';
      h += '<td>' + esc(t.id) + '</td>';
      h += '<td class="trunc">' + esc(t.market) + '</td>';
      h += '<td>' + platBadge(t.platform) + '</td>';
      h += '<td>' + esc(t.opened || '') + '</td>';
      h += '<td>' + esc(t.closed || '') + '</td>';
      h += '<td class="' + pc(t.pnl_usd) + '">' + fmt(t.pnl_usd) + '</td>';
      h += '<td class="' + pc(t.pnl_pct) + '">' + pct(t.pnl_pct) + '</td>';
      h += '</tr>';
    }
    h += '</table></div>';
  }

  // Watchlist
  const wl = (d.watchlist || []).filter(w => w.intent && w.intent !== 'NONE');
  if (wl.length) {
    h += '<h2>Watchlist</h2><div class="wrap"><table>';
    h += '<tr><th>Market</th><th>Plt</th><th>Intent</th><th>Mkt</th><th>My Prob</th><th>Edge</th><th>Priority</th><th>Resolves</th></tr>';
    for (const w of wl) {
      const liveYes = w.pm_yes != null ? w.pm_yes : w.mid;
      const ep = w.edge_pp;
      const ecls = ep >= 8 ? 'pos' : ep >= 5 ? 'neu' : 'neg';
      h += '<tr>';
      h += '<td class="trunc">' + esc(w.market) + '</td>';
      h += '<td>' + platBadge(w.platform) + '</td>';
      h += '<td>' + intentBadge(w.intent) + '</td>';
      h += '<td>' + (liveYes != null ? liveYes.toFixed(3) : '\u2014') + '</td>';
      h += '<td>' + (w.my_probability_yes != null ? (w.my_probability_yes * 100).toFixed(0) + '%' : '\u2014') + '</td>';
      h += '<td class="' + ecls + '">' + (ep != null ? ep + 'pp' : '\u2014') + '</td>';
      h += '<td>' + esc(w.priority || '') + '</td>';
      h += '<td>' + esc(w.resolves || '') + '</td>';
      h += '</tr>';
    }
    h += '</table></div>';
  }

  // Decision feed
  const feed = (d.recent_decisions || []).slice(0, 30);
  if (feed.length) {
    h += '<h2>Recent Decisions</h2><div class="feed">';
    for (const e of feed) {
      const tp  = e.type || 'HOLD';
      const cls = tp === 'CLOSE' ? 'fc' : tp === 'ENTER' ? 'fn' : tp === 'GDPNOW' ? 'fg' : 'fh';
      const ts  = e.ts ? new Date(e.ts).toLocaleString('en-US', {hour12: false}) : '';
      let txt = '';
      if (tp === 'CLOSE')  txt = (e.platform || '') + ' ' + (e.trade_id || '') + ': P&L ' + fmt(e.pnl_usd) + ' \u2014 ' + (e.reason || '').substring(0, 80);
      else if (tp === 'ENTER')  txt = (e.platform || '') + ' ' + (e.trade_id || '') + ': ' + (e.market || '') + ' edge=' + (e.edge_pp || '') + 'pp $' + (e.size_usd || '');
      else if (tp === 'GDPNOW') txt = 'GDPNow: ' + (e.value || '') + '% (' + (e.date || '') + ')';
      else txt = (e.trade_id || '') + ' ' + (e.reason || '').substring(0, 100);
      h += '<div class="fe"><span class="ft ' + cls + '">' + esc(tp) + '</span>';
      h += '<span class="fx">' + esc(txt) + '</span>';
      h += '<span class="fts">' + esc(ts) + '</span></div>';
    }
    h += '</div>';
  }

  document.getElementById('root').textContent = '';
  const tmp = document.createElement('div');
  tmp.innerHTML = h;
  document.getElementById('root').appendChild(tmp);
}

const API_KEY = '__API_KEY__';
async function load() {
  try {
    const data = await fetch('/api/portfolio', {
      headers: { 'X-API-Key': API_KEY }
    }).then(r => r.json());
    render(data);
  } catch(e) {
    const el = document.getElementById('root');
    el.textContent = '';
    const div = document.createElement('div');
    div.className = 'err';
    div.textContent = 'Error: ' + e.message;
    el.appendChild(div);
  }
}

load();
setInterval(load, 30000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/api/portfolio":
            self._serve_portfolio()
        elif self.path in ("/", "/index.html"):
            self._serve_html()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self):
        # Inject the API key into the page so the browser's fetch can include it.
        # The key is only exposed to whoever can already reach this server.
        body = DASHBOARD_HTML.replace("__API_KEY__", API_KEY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_api_key(self):
        """Return True if request carries a valid API key."""
        auth = self.headers.get("X-API-Key", "")
        return API_KEY and auth == API_KEY

    def _serve_portfolio(self):
        if not self._check_api_key():
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return
        try:
            dw = json.loads(DW_LEDGER.read_text())
            ks = json.loads(KS_LEDGER.read_text())

            dw_trades = [{"platform": "polymarket", **t} for t in dw["trades"]]
            ks_trades = [{"platform": "kalshi",     **t} for t in ks["trades"]]
            all_trades    = dw_trades + ks_trades
            open_trades   = [t for t in all_trades if t.get("status") == "OPEN"]
            closed_trades = [t for t in all_trades if t.get("status") == "CLOSED"]

            realized   = sum(t.get("pnl_usd") or 0 for t in closed_trades)
            unrealized = 0.0
            for t in open_trades:
                dl = t.get("decision_log", [])
                if dl:
                    unrealized += dl[-1].get("mtm_pnl_usd") or 0

            total_cash = (dw["account"].get("cash_remaining_usd", 0) +
                          ks["account"].get("cash_remaining_usd", 0))

            watchlist = (
                [{"platform": "polymarket", **w} for w in dw.get("watchlist", [])] +
                [{"platform": "kalshi",     **w} for w in ks.get("watchlist", [])]
            )

            recent = []
            if TRADE_LOG.exists():
                for line in TRADE_LOG.read_text().strip().split("\n")[-50:]:
                    try:
                        recent.append(json.loads(line))
                    except Exception:
                        pass

            data = {
                "ts": dt.datetime.utcnow().isoformat() + "Z",
                "summary": {
                    "realized_pnl_usd":   round(realized, 4),
                    "unrealized_pnl_usd": round(unrealized, 4),
                    "total_pnl_usd":      round(realized + unrealized, 4),
                    "total_cash_usd":     round(total_cash, 4),
                    "num_open":   len(open_trades),
                    "num_closed": len(closed_trades),
                },
                "positions": open_trades,
                "closed":    closed_trades,
                "watchlist": watchlist,
                "recent_decisions": list(reversed(recent[-20:])),
                "run_log": [],
            }

            body = json.dumps(data, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        except Exception as e:
            err = str(e).encode()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(err)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Trading dashboard -> http://0.0.0.0:{PORT}")
    server.serve_forever()
