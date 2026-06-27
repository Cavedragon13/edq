#!/usr/bin/env python3
"""
Dragonsuite Trading Agent
Autonomous paper trading agent — runs hourly via cron.
Makes close/enter decisions, updates both ledgers, writes dashboard data.

Decision rules:
  CLOSE  BUY_NO  when cur_no  >= 0.94   (captured most upside)
  CLOSE  BUY_YES when cur_yes >= 0.97   (near-certainty captured)
  STOP   either  when position collapses <= 0.10
  ENTER  when watchlist edge >= 8pp and cash available
"""
import asyncio, httpx, json, csv, io, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE      = Path(__file__).parent
DW_LEDGER = BASE / "dragonweyr/paper_ledger.json"
KS_LEDGER = BASE / "kalshi/paper_ledger.json"
TRADE_LOG = BASE / "trading_log.jsonl"
DASH_DATA = BASE / "trading_dashboard_data.json"

PM_BASE    = "https://gateway.polymarket.us"
KS_BASE    = "https://api.elections.kalshi.com/trade-api/v2"
GDPNOW_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDPNOW"

# ── Thresholds ────────────────────────────────────────────────────────────────
CLOSE_NO_THRESHOLD  = 0.94   # BUY_NO:  close when cur_no  >= this
CLOSE_YES_THRESHOLD = 0.97   # BUY_YES: close when cur_yes >= this
STOP_LOSS_THRESHOLD = 0.10   # either:  close if collapses below this
MIN_EDGE_PP         = 8.0    # minimum edge (pp) to enter a new position
MAX_POSITION_SIZE   = 15.0   # max USD per new position
MAX_POSITION_PCT    = 0.70   # max fraction of available cash per position
LOG_PRICE_MOVE_PP   = 1.0    # only add decision_log entry if price moved >= this pp


# ── Price fetch ───────────────────────────────────────────────────────────────
async def fetch_pm_bbo(slug: str, client: httpx.AsyncClient) -> tuple[Optional[float], Optional[float]]:
    """Fetch Polymarket BBO. Returns (cur_yes, cur_no) or (None, None)."""
    try:
        r = await client.get(f"{PM_BASE}/v1/markets/{slug}/bbo",
                             headers={"Accept": "application/json"}, timeout=15)
        if r.status_code == 200:
            bbo = r.json().get("marketData", {})
            px = None
            if bbo.get("currentPx"):
                px = float(bbo["currentPx"]["value"])
            elif bbo.get("lastTradePx"):
                px = float(bbo["lastTradePx"]["value"])
            if px is not None:
                return round(px, 4), round(1 - px, 4)
    except Exception as e:
        _warn(f"fetch_pm_bbo({slug}): {e}")
    return None, None


def _ks_px(mkt: dict, field: str) -> Optional[float]:
    v = mkt.get(field)
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


async def fetch_kalshi_market(ticker: str, client: httpx.AsyncClient) -> tuple[Optional[float], Optional[float]]:
    """Fetch Kalshi market prices. Returns (cur_yes_mid, cur_no_mid) or (None, None)."""
    try:
        r = await client.get(f"{KS_BASE}/markets/{ticker}",
                             headers={"Accept": "application/json"}, timeout=15)
        if r.status_code == 200:
            mkt = r.json().get("market", r.json())
            no_bid = _ks_px(mkt, "no_bid_dollars")
            no_ask = _ks_px(mkt, "no_ask_dollars")
            if no_bid is not None and no_ask is not None:
                cur_no = round((no_bid + no_ask) / 2, 4)
                return round(1 - cur_no, 4), cur_no
            yb = _ks_px(mkt, "yes_bid_dollars")
            ya = _ks_px(mkt, "yes_ask_dollars")
            if yb is not None and ya is not None:
                cur_yes = round((yb + ya) / 2, 4)
                return cur_yes, round(1 - cur_yes, 4)
    except Exception as e:
        _warn(f"fetch_kalshi_market({ticker}): {e}")
    return None, None


async def fetch_gdpnow(client: httpx.AsyncClient) -> tuple[Optional[float], Optional[str]]:
    """Fetch latest GDPNow from FRED CSV. Returns (value_pct, date_str) or (None, None)."""
    try:
        r = await client.get(GDPNOW_URL, timeout=15)
        if r.status_code == 200:
            rows = list(csv.reader(io.StringIO(r.text)))
            for row in reversed(rows[1:]):
                if len(row) >= 2 and row[1] not in ("", "."):
                    return float(row[1]), row[0]
    except Exception as e:
        _warn(f"fetch_gdpnow: {e}")
    return None, None


def _warn(msg: str):
    print(f"  [warn] {msg}", file=sys.stderr)


# ── Decision rules ────────────────────────────────────────────────────────────
def should_close(trade: dict, cur_yes: float, cur_no: float) -> tuple[bool, str]:
    intent = trade["intent"]
    entry_no  = trade.get("no_price_at_entry") or trade.get("no_mid_at_entry", 0.5)
    entry_yes = trade.get("yes_price_at_entry") or trade.get("yes_mid_at_entry", 0.5)

    if intent == "BUY_NO":
        if cur_no >= CLOSE_NO_THRESHOLD:
            pct = (cur_no - entry_no) / max(1.0 - entry_no, 0.001) * 100
            return True, (f"AUTO-CLOSE: NO={cur_no:.3f} >= {CLOSE_NO_THRESHOLD}. "
                          f"Captured {pct:.0f}% of move toward fair value. Redeploying capital.")
        if cur_no <= STOP_LOSS_THRESHOLD:
            return True, f"STOP-LOSS: NO collapsed to {cur_no:.3f}. Thesis failed. Cutting loss."
    elif intent == "BUY_YES":
        if cur_yes >= CLOSE_YES_THRESHOLD:
            pct = (cur_yes - entry_yes) / max(1.0 - entry_yes, 0.001) * 100
            return True, (f"AUTO-CLOSE: YES={cur_yes:.3f} >= {CLOSE_YES_THRESHOLD}. "
                          f"Captured {pct:.0f}% of move toward fair value. Redeploying capital.")
        if cur_yes <= STOP_LOSS_THRESHOLD:
            return True, f"STOP-LOSS: YES collapsed to {cur_yes:.3f}. Thesis failed. Cutting loss."
    return False, ""


def edge_pp(item: dict, live_yes: float) -> float:
    """Edge in pp: positive = we have an edge, negative = we don't."""
    my_prob = item.get("my_probability_yes")
    if my_prob is None:
        return 0.0
    intent = item.get("intent", "")
    if intent == "BUY_YES":
        return (my_prob - live_yes) * 100
    elif intent == "BUY_NO":
        return (live_yes - my_prob) * 100  # YES overpriced = NO has edge
    return 0.0


def next_id(ledger: dict, prefix: str) -> str:
    nums = [int(t["id"][len(prefix):]) for t in ledger["trades"]
            if t["id"].startswith(prefix) and t["id"][len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1):03d}" if nums else f"{prefix}001"


def calc_size(cash: float) -> float:
    return round(min(cash * MAX_POSITION_PCT, MAX_POSITION_SIZE), 2)


# ── Execute close ─────────────────────────────────────────────────────────────
def execute_close(trade: dict, ledger: dict, cur_yes: float, cur_no: float,
                  reason: str, now_utc: datetime) -> float:
    """Closes trade in-place. Returns proceeds."""
    if trade["intent"] == "BUY_NO":
        proceeds = round(trade["shares"] * cur_no, 4)
    else:
        proceeds = round(trade["shares"] * cur_yes, 4)
    pnl = round(proceeds - trade["cost_usd"], 4)
    pct = round((pnl / trade["cost_usd"]) * 100, 1) if trade["cost_usd"] > 0 else 0.0

    trade["status"]             = "CLOSED"
    trade["outcome"]            = "WIN" if pnl > 0 else "LOSS"
    trade["closed"]             = now_utc.strftime("%Y-%m-%d")
    trade["close_price_yes"]    = cur_yes
    trade["close_price_no"]     = cur_no
    trade["close_proceeds_usd"] = proceeds
    trade["close_reason"]       = reason
    trade["pnl_usd"]            = pnl
    trade["pnl_pct"]            = pct
    trade["decision_log"].append({
        "date":        now_utc.strftime("%Y-%m-%d"),
        "time_utc":    now_utc.strftime("%H:%M"),
        "action":      "CLOSE",
        "bbo_yes":     cur_yes,
        "bbo_no":      cur_no,
        "proceeds_usd": proceeds,
        "pnl_usd":     pnl,
        "pnl_pct":     pct,
        "reasoning":   reason,
    })
    acc = ledger["account"]
    acc["cash_remaining_usd"] = round(acc.get("cash_remaining_usd", 0) + proceeds, 4)
    return proceeds


# ── Execute entry (Kalshi) ────────────────────────────────────────────────────
def execute_enter_kalshi(item: dict, ledger: dict, cur_yes: float, cur_no: float,
                         size: float, ep: float, now_utc: datetime) -> str:
    intent = item["intent"]
    if intent == "BUY_YES":
        ask = min(cur_yes + 0.01, 0.99)
        shares = round(size / ask, 4)
    else:
        ask_no = min(cur_no + 0.01, 0.99)
        shares = round(size / ask_no, 4)
    max_win = round(shares - size, 4)
    new_id  = next_id(ledger, "K")
    my_prob = item.get("my_probability_yes", 0.5)

    ledger["trades"].append({
        "id": new_id, "opened": now_utc.strftime("%Y-%m-%d"),
        "market": item["market"], "ticker": item["ticker"],
        "series": item.get("series", ""), "intent": intent,
        "yes_mid_at_entry": cur_yes, "no_mid_at_entry": cur_no,
        "yes_ask_at_entry": cur_yes + 0.01, "no_ask_at_entry": cur_no + 0.01,
        "shares": shares, "cost_usd": size, "max_win_usd": max_win,
        "resolves": item.get("resolves", ""),
        "thesis": item.get("note", "Auto-entered by trading agent."),
        "my_probability_yes": my_prob, "my_probability_no": round(1 - my_prob, 3),
        "edge_pp": round(ep, 1), "status": "OPEN",
        "decision_log": [{
            "date": now_utc.strftime("%Y-%m-%d"), "time_utc": now_utc.strftime("%H:%M"),
            "action": "ENTER", "bbo_yes": cur_yes, "bbo_no": cur_no,
            "cost_usd": size, "shares": shares,
            "reasoning": f"AUTO-ENTER: edge={ep:.1f}pp >= {MIN_EDGE_PP}pp. YES mid={cur_yes:.3f}. Size=${size:.2f}.",
        }],
        "outcome": None, "closed": None, "pnl_usd": None,
    })
    acc = ledger["account"]
    acc["cash_remaining_usd"] = round(acc.get("cash_remaining_usd", 0) - size, 4)
    return new_id


# ── Execute entry (Polymarket) ────────────────────────────────────────────────
def execute_enter_pm(item: dict, ledger: dict, cur_yes: float, cur_no: float,
                     size: float, ep: float, now_utc: datetime) -> str:
    intent = item["intent"]
    if intent == "BUY_YES":
        ask = min(cur_yes + 0.01, 0.99)
        shares = round(size / ask, 4)
    else:
        ask_no = min(cur_no + 0.01, 0.99)
        shares = round(size / ask_no, 4)
    max_win  = round(shares - size, 4)
    new_id   = next_id(ledger, "T")
    my_prob  = item.get("my_probability_yes", 0.5)
    entry_px = cur_yes if intent == "BUY_YES" else cur_no

    ledger["trades"].append({
        "id": new_id, "opened": now_utc.strftime("%Y-%m-%d"),
        "market": item["market"], "slug": item["slug"], "intent": intent,
        "yes_price_at_entry": cur_yes, "no_price_at_entry": cur_no,
        "shares": shares, "cost_usd": size, "max_win_usd": max_win,
        "resolves": item.get("resolves", ""),
        "thesis": item.get("note", "Auto-entered by trading agent."),
        "my_probability_yes": my_prob, "my_probability_no": round(1 - my_prob, 3),
        "expected_value_per_share": round(my_prob - entry_px, 4),
        "ev_roi_pct": round((my_prob / entry_px - 1) * 100, 1) if entry_px > 0 else 0,
        "status": "OPEN",
        "decision_log": [{
            "date": now_utc.strftime("%Y-%m-%d"), "time_utc": now_utc.strftime("%H:%M"),
            "action": "ENTER", "bbo_yes": cur_yes, "bbo_no": cur_no,
            "cost_usd": size, "shares": shares,
            "reasoning": f"AUTO-ENTER: edge={ep:.1f}pp >= {MIN_EDGE_PP}pp. YES mid={cur_yes:.3f}. Size=${size:.2f}.",
        }],
        "outcome": None, "closed": None, "pnl_usd": None,
    })
    acc = ledger["account"]
    acc["cash_remaining_usd"] = round(acc.get("cash_remaining_usd", 0) - size, 4)
    return new_id


# ── MTM helper ────────────────────────────────────────────────────────────────
def calc_mtm(trade: dict, cur_yes: float, cur_no: float) -> tuple[float, float, float]:
    if trade["intent"] == "BUY_NO":
        mtm_val = round(trade["shares"] * cur_no, 4)
    else:
        mtm_val = round(trade["shares"] * cur_yes, 4)
    pnl = round(mtm_val - trade["cost_usd"], 4)
    pct = round((pnl / trade["cost_usd"]) * 100, 1) if trade["cost_usd"] > 0 else 0.0
    return mtm_val, pnl, pct


# ── Dashboard data writer ─────────────────────────────────────────────────────
def write_dashboard(dw_ledger: dict, ks_ledger: dict, run_log: list, ts: str):
    dw_trades = [{"platform": "polymarket", **t} for t in dw_ledger["trades"]]
    ks_trades = [{"platform": "kalshi",     **t} for t in ks_ledger["trades"]]
    all_trades   = dw_trades + ks_trades
    open_trades  = [t for t in all_trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in all_trades if t.get("status") == "CLOSED"]

    realized_pnl   = sum(t.get("pnl_usd") or 0 for t in closed_trades)
    unrealized_pnl = 0.0
    for t in open_trades:
        dl = t.get("decision_log", [])
        if dl:
            last = dl[-1]
            unrealized_pnl += last.get("mtm_pnl_usd") or 0

    total_cash = (dw_ledger["account"].get("cash_remaining_usd", 0) +
                  ks_ledger["account"].get("cash_remaining_usd", 0))

    watchlist = (
        [{"platform": "polymarket", **w} for w in dw_ledger.get("watchlist", [])] +
        [{"platform": "kalshi",     **w} for w in ks_ledger.get("watchlist", [])]
    )

    # Last 50 entries from trade log
    recent = []
    if TRADE_LOG.exists():
        for line in TRADE_LOG.read_text().strip().split("\n")[-50:]:
            try:
                recent.append(json.loads(line))
            except Exception:
                pass

    data = {
        "ts": ts,
        "summary": {
            "realized_pnl_usd":   round(realized_pnl, 4),
            "unrealized_pnl_usd": round(unrealized_pnl, 4),
            "total_pnl_usd":      round(realized_pnl + unrealized_pnl, 4),
            "total_cash_usd":     round(total_cash, 4),
            "num_open":   len(open_trades),
            "num_closed": len(closed_trades),
        },
        "positions":         open_trades,
        "closed":            closed_trades,
        "watchlist":         watchlist,
        "recent_decisions":  list(reversed(recent[-20:])),
        "run_log":           run_log,
    }
    DASH_DATA.write_text(json.dumps(data, indent=2))


# ── Main agent loop ───────────────────────────────────────────────────────────
async def run_agent():
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    now_str = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    dw_ledger = json.loads(DW_LEDGER.read_text())
    ks_ledger = json.loads(KS_LEDGER.read_text())

    run_log    = []
    dw_changed = False
    ks_changed = False

    async with httpx.AsyncClient(timeout=20) as client:

        # ── GDPNow (weekdays only) ────────────────────────────────────────────
        gdpnow_val, gdpnow_date = None, None
        if now_utc.weekday() < 5:
            gdpnow_val, gdpnow_date = await fetch_gdpnow(client)
            if gdpnow_val:
                run_log.append({"ts": now_iso, "type": "GDPNOW",
                                "value": gdpnow_val, "date": gdpnow_date})

        # ── Polymarket: open trades ───────────────────────────────────────────
        for trade in dw_ledger["trades"]:
            if trade["status"] != "OPEN":
                continue
            cur_yes, cur_no = await fetch_pm_bbo(trade["slug"], client)
            if cur_yes is None:
                continue

            mtm_val, mtm_pnl, mtm_pct = calc_mtm(trade, cur_yes, cur_no)

            close, reason = should_close(trade, cur_yes, cur_no)
            if close:
                execute_close(trade, dw_ledger, cur_yes, cur_no, reason, now_utc)
                run_log.append({"ts": now_iso, "type": "CLOSE", "platform": "polymarket",
                                "trade_id": trade["id"], "reason": reason,
                                "pnl_usd": trade["pnl_usd"]})
                print(f"[CLOSE] polymarket {trade['id']}: {reason}")
                dw_changed = True
                continue

            # Log on significant price move or GDPNow change
            dl = trade["decision_log"]
            last_yes = dl[-1].get("bbo_yes", trade.get("yes_price_at_entry", 0.5)) if dl else trade.get("yes_price_at_entry", 0.5)
            if abs(cur_yes - last_yes) * 100 >= LOG_PRICE_MOVE_PP:
                dl.append({
                    "date": now_utc.strftime("%Y-%m-%d"),
                    "time_utc": now_utc.strftime("%H:%M"),
                    "action": "HOLD",
                    "bbo_yes": cur_yes, "bbo_no": cur_no,
                    "mtm_value_usd": mtm_val, "mtm_pnl_usd": mtm_pnl, "mtm_pnl_pct": mtm_pct,
                    "reasoning": f"Price moved {abs(cur_yes-last_yes)*100:.1f}pp. YES={cur_yes:.3f}. MTM {mtm_pnl:+.4f} ({mtm_pct:+.1f}%). No close trigger.",
                })
                dw_changed = True

        # ── Polymarket: watchlist scan for new entries ────────────────────────
        open_pm_slugs = {t["slug"] for t in dw_ledger["trades"] if t["status"] == "OPEN"}
        dw_cash = dw_ledger["account"].get("cash_remaining_usd", 0)
        for item in dw_ledger.get("watchlist", []):
            if item.get("intent") in (None, "NONE", "") or not item.get("my_probability_yes"):
                continue
            if item["slug"] in open_pm_slugs:
                continue
            cur_yes, cur_no = await fetch_pm_bbo(item["slug"], client)
            if cur_yes is None:
                continue
            item["pm_yes"] = round(cur_yes, 4)
            ep = edge_pp(item, cur_yes)
            if ep >= MIN_EDGE_PP and dw_cash >= 0.50:
                size   = calc_size(dw_cash)
                new_id = execute_enter_pm(item, dw_ledger, cur_yes, cur_no, size, ep, now_utc)
                open_pm_slugs.add(item["slug"])
                dw_cash = dw_ledger["account"].get("cash_remaining_usd", 0)
                run_log.append({"ts": now_iso, "type": "ENTER", "platform": "polymarket",
                                "trade_id": new_id, "market": item["market"],
                                "edge_pp": round(ep, 1), "size_usd": size})
                print(f"[ENTER] polymarket {new_id}: {item['market']} edge={ep:.1f}pp size=${size:.2f}")
            dw_changed = True

        # ── Kalshi: open trades ───────────────────────────────────────────────
        for trade in ks_ledger["trades"]:
            if trade["status"] != "OPEN":
                continue
            cur_yes, cur_no = await fetch_kalshi_market(trade["ticker"], client)
            if cur_yes is None:
                continue

            mtm_val, mtm_pnl, mtm_pct = calc_mtm(trade, cur_yes, cur_no)

            close, reason = should_close(trade, cur_yes, cur_no)
            if close:
                execute_close(trade, ks_ledger, cur_yes, cur_no, reason, now_utc)
                run_log.append({"ts": now_iso, "type": "CLOSE", "platform": "kalshi",
                                "trade_id": trade["id"], "reason": reason,
                                "pnl_usd": trade["pnl_usd"]})
                print(f"[CLOSE] kalshi {trade['id']}: {reason}")
                ks_changed = True
                continue

            # Log on price move OR new GDPNow reading for GDP series
            dl = trade["decision_log"]
            last_yes = dl[-1].get("bbo_yes", trade.get("yes_mid_at_entry", 0.5)) if dl else trade.get("yes_mid_at_entry", 0.5)
            log_entry = None

            if abs(cur_yes - last_yes) * 100 >= LOG_PRICE_MOVE_PP:
                log_entry = {
                    "date": now_utc.strftime("%Y-%m-%d"), "time_utc": now_utc.strftime("%H:%M"),
                    "action": "HOLD", "bbo_yes": cur_yes, "bbo_no": cur_no,
                    "mtm_value_usd": mtm_val, "mtm_pnl_usd": mtm_pnl, "mtm_pnl_pct": mtm_pct,
                    "reasoning": f"Price moved {abs(cur_yes-last_yes)*100:.1f}pp. YES={cur_yes:.3f}. MTM {mtm_pnl:+.4f} ({mtm_pct:+.1f}%). No close trigger.",
                }
            elif gdpnow_val and trade.get("series") == "KXGDP":
                last_gdpnow = dl[-1].get("gdpnow") if dl else None
                if last_gdpnow != gdpnow_val:
                    thesis_ok = gdpnow_val < float(trade["ticker"].split("-T")[-1])
                    log_entry = {
                        "date": now_utc.strftime("%Y-%m-%d"), "time_utc": now_utc.strftime("%H:%M"),
                        "action": "HOLD", "bbo_yes": cur_yes, "bbo_no": cur_no,
                        "mtm_value_usd": mtm_val, "mtm_pnl_usd": mtm_pnl, "mtm_pnl_pct": mtm_pct,
                        "gdpnow": gdpnow_val,
                        "reasoning": f"GDPNow updated: {gdpnow_val}% ({gdpnow_date}). Thesis {'INTACT' if thesis_ok else 'CHALLENGED'}. NO={cur_no:.3f}. MTM {mtm_pnl:+.4f}.",
                    }

            if log_entry:
                dl.append(log_entry)
                ks_changed = True

        # ── Kalshi: watchlist scan for new entries ────────────────────────────
        open_ks_tickers = {t["ticker"] for t in ks_ledger["trades"] if t["status"] == "OPEN"}
        ks_cash = ks_ledger["account"].get("cash_remaining_usd", 0)
        for item in ks_ledger.get("watchlist", []):
            if item.get("intent") in (None, "NONE", "") or not item.get("my_probability_yes"):
                continue
            if item["ticker"] in open_ks_tickers:
                continue
            cur_yes, cur_no = await fetch_kalshi_market(item["ticker"], client)
            if cur_yes is None:
                continue
            item["mid"] = round(cur_yes, 4)
            ep = edge_pp(item, cur_yes)
            if ep >= MIN_EDGE_PP and ks_cash >= 0.50:
                size   = calc_size(ks_cash)
                new_id = execute_enter_kalshi(item, ks_ledger, cur_yes, cur_no, size, ep, now_utc)
                open_ks_tickers.add(item["ticker"])
                ks_cash = ks_ledger["account"].get("cash_remaining_usd", 0)
                run_log.append({"ts": now_iso, "type": "ENTER", "platform": "kalshi",
                                "trade_id": new_id, "market": item["market"],
                                "edge_pp": round(ep, 1), "size_usd": size})
                print(f"[ENTER] kalshi {new_id}: {item['market']} edge={ep:.1f}pp size=${size:.2f}")
            ks_changed = True

    # ── Persist ───────────────────────────────────────────────────────────────
    if dw_changed:
        dw_ledger["account"]["last_reviewed"] = now_utc.strftime("%Y-%m-%d")
        DW_LEDGER.write_text(json.dumps(dw_ledger, indent=2))

    if ks_changed:
        ks_ledger["account"]["last_reviewed"] = now_utc.strftime("%Y-%m-%d")
        KS_LEDGER.write_text(json.dumps(ks_ledger, indent=2))

    write_dashboard(dw_ledger, ks_ledger, run_log, now_iso)

    if run_log:
        with TRADE_LOG.open("a") as f:
            for entry in run_log:
                f.write(json.dumps(entry) + "\n")

    actions = [e for e in run_log if e.get("type") in ("CLOSE", "ENTER")]
    if not actions:
        print(f"No actions. {now_str}")
    return run_log


if __name__ == "__main__":
    asyncio.run(run_agent())
