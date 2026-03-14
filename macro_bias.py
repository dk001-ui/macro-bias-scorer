"""
macro_bias.py - Daily Macro Session Bias Scorer
Pulls DXY, VIX, US 10Y Yield, Gold each morning and scores the session.

Session Modes:
  0-1 bearish  -> LONG-BIASED  (take longs freely, shorts need extra confirmation)
  2   bearish  -> NEUTRAL      (trade both sides, reduce size, respect range)
  3-4 bearish  -> SHORT-BIASED (take shorts freely, fade pumps, avoid chasing longs)

Usage:
  pip install yfinance pandas rich
  python macro_bias.py
"""

import sys
from datetime import datetime, timedelta

try:
    import yfinance as yf
except ImportError:
    print("[ERROR] yfinance not installed. Run: pip install yfinance pandas rich")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

import pandas as pd
import numpy as np

console = Console() if HAS_RICH else None

INSTRUMENTS = {
    "DXY":   {"ticker": "DX-Y.NYB", "label": "DXY (Dollar Index)", "bearish_when": "rising"},
    "VIX":   {"ticker": "^VIX",     "label": "VIX (Fear Index)",   "bearish_when": "rising"},
    "US10Y": {"ticker": "^TNX",     "label": "US 10Y Yield",       "bearish_when": "rising"},
    "GOLD":  {"ticker": "GC=F",     "label": "Gold",               "bearish_when": "falling"},
}

LOOKBACK_DAYS = 30
RSI_PERIOD    = 14
MA_FAST       = 10
MA_SLOW       = 20


def fetch(ticker, days=LOOKBACK_DAYS):
    end   = datetime.today()
    start = end - timedelta(days=days + 10)
    try:
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"),
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        return df.tail(days)
    except Exception as e:
        print(f"[WARN] Failed to fetch {ticker}: {e}")
        return None


def calc_rsi(series, period=RSI_PERIOD):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def pct_change_n(series, n):
    if len(series) < n + 1:
        return 0.0
    return float((series.iloc[-1] - series.iloc[-n - 1]) / series.iloc[-n - 1] * 100)


def score_instrument(name, df):
    cfg     = INSTRUMENTS[name]
    close   = df["Close"].squeeze()
    last    = float(close.iloc[-1])
    prev    = float(close.iloc[-2]) if len(close) >= 2 else last
    rsi     = calc_rsi(close)
    rsi_now = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
    ma_fast = float(close.rolling(MA_FAST).mean().iloc[-1])
    ma_slow = float(close.rolling(MA_SLOW).mean().iloc[-1])
    chg_1d  = pct_change_n(close, 1)
    chg_5d  = pct_change_n(close, 5)

    rising          = (last > prev) and (ma_fast > ma_slow) and (chg_5d > 0)
    falling         = (last < prev) and (ma_fast < ma_slow) and (chg_5d < 0)
    strong_rsi_up   = rsi_now > 60
    strong_rsi_down = rsi_now < 40
    bearish_when    = cfg["bearish_when"]

    if bearish_when == "rising":
        if rising and strong_rsi_up:
            signal, score, reason = "BEARISH", 1, f"Rising {chg_5d:+.2f}% (5d), RSI {rsi_now:.0f}, MA{MA_FAST}>{MA_SLOW}"
        elif falling and strong_rsi_down:
            signal, score, reason = "BULLISH", -1, f"Falling {chg_5d:+.2f}% (5d), RSI {rsi_now:.0f}, MA{MA_FAST}<{MA_SLOW}"
        else:
            signal, score, reason = "NEUTRAL", 0, f"No strong trend, RSI {rsi_now:.0f}, chg5d {chg_5d:+.2f}%"
    else:
        if falling and strong_rsi_down:
            signal, score, reason = "BEARISH", 1, f"Falling {chg_5d:+.2f}% (5d), RSI {rsi_now:.0f}, MA{MA_FAST}<{MA_SLOW}"
        elif rising and strong_rsi_up:
            signal, score, reason = "BULLISH", -1, f"Rising {chg_5d:+.2f}% (5d), RSI {rsi_now:.0f}, MA{MA_FAST}>{MA_SLOW}"
        else:
            signal, score, reason = "NEUTRAL", 0, f"No strong trend, RSI {rsi_now:.0f}, chg5d {chg_5d:+.2f}%"

    return {
        "name": name, "label": cfg["label"], "last": last,
        "chg_1d": chg_1d, "chg_5d": chg_5d, "rsi": rsi_now,
        "signal": signal, "score": score, "reason": reason,
    }


def get_session_mode(bearish_count):
    if bearish_count <= 1:
        return "LONG-BIASED", "green"
    elif bearish_count == 2:
        return "NEUTRAL", "yellow"
    else:
        return "SHORT-BIASED", "red"


def scalp_guidance(mode, bearish_count):
    if mode == "LONG-BIASED":
        return [
            "Take long scalps freely on aligned indicator signals.",
            "Short scalps need extra confirmation -- require 4/5 confluence.",
            "Hold winners slightly longer on long side.",
            "Cut losing longs at first sign of failure -- no macro support below.",
        ]
    elif mode == "NEUTRAL":
        return [
            "Trade both sides but reduce position size by 30-50%.",
            "Respect the intraday range -- fade extremes rather than breakouts.",
            "Tighten stops on both sides -- directional conviction is low.",
            "BTC structure check is critical today before any alt scalps.",
        ]
    else:
        return [
            "Take short scalps freely on aligned indicator signals.",
            "Do NOT chase longs -- macro environment is risk-off.",
            "Hold shorts slightly longer than usual -- downside moves are asymmetric.",
            "Cut long scalps faster than normal (25-50% of usual hold time).",
            f"Macro score {bearish_count}/4 bearish -- highest conviction short day.",
        ]


def run():
    now = datetime.now()
    print(f"\nMacro Session Bias Scorer | {now.strftime('%A %d %b %Y %H:%M')}\n")

    results = []
    for name in INSTRUMENTS:
        df = fetch(INSTRUMENTS[name]["ticker"])
        if df is None or len(df) < RSI_PERIOD + 2:
            print(f"[WARN] Insufficient data for {name}, skipping.")
            continue
        results.append(score_instrument(name, df))

    if not results:
        print("[ERROR] Could not fetch any instrument data. Check your internet connection.")
        sys.exit(1)

    bearish_count = sum(1 for r in results if r["score"] == 1)
    mode, color = get_session_mode(bearish_count)
    guidance = scalp_guidance(mode, bearish_count)

    if HAS_RICH:
        t = Table(title="Macro Instrument Scores", box=box.SIMPLE_HEAVY, show_lines=True)
        t.add_column("Instrument", style="bold white", min_width=22)
        t.add_column("Last", justify="right", min_width=10)
        t.add_column("1D Chg", justify="right", min_width=9)
        t.add_column("5D Chg", justify="right", min_width=9)
        t.add_column("RSI", justify="right", min_width=6)
        t.add_column("Signal", justify="center", min_width=10)
        t.add_column("Reason", style="dim", min_width=40)

        sig_colors = {"BEARISH": "red", "NEUTRAL": "yellow", "BULLISH": "green"}

        for r in results:
            sc = sig_colors.get(r["signal"], "white")
            chg1_color = "green" if r["chg_1d"] >= 0 else "red"
            chg5_color = "green" if r["chg_5d"] >= 0 else "red"
            t.add_row(
                r["label"],
                f"{r['last']:.3f}",
                f"[{chg1_color}]{r['chg_1d']:+.2f}%[/]",
                f"[{chg5_color}]{r['chg_5d']:+.2f}%[/]",
                f"{r['rsi']:.0f}",
                f"[{sc}]{r['signal']}[/]",
                r["reason"],
            )

        console.print(t)

        summary = f"[bold {color}]{mode}[/] | [white]{bearish_count}/4 instruments bearish[/]"
        guide_text = "\n".join(f" [dim]-[/] {g}" for g in guidance)
        console.print(Panel(
            f"{summary}\n\n{guide_text}",
            title="[bold]Session Bias[/]",
            border_style=color,
            padding=(1, 2),
        ))

    else:
        header = f"{'Instrument':<25} {'Last':>10} {'1D%':>7} {'5D%':>7} {'RSI':>6} {'Signal':<10} Reason"
        print(header)
        print("-" * len(header))
        for r in results:
            print(
                f"{r['label']:<25} {r['last']:>10.3f} "
                f"{r['chg_1d']:>+7.2f} {r['chg_5d']:>+7.2f} "
                f"{r['rsi']:>6.0f} {r['signal']:<10} {r['reason']}"
            )
        print(f"\nSESSION MODE: {mode} ({bearish_count}/4 bearish)\n")
        for g in guidance:
            print(f"  - {g}")
        print()


# ---------------------------------------------------------------------------
# Regime logging
# ---------------------------------------------------------------------------
import csv as _csv
from pathlib import Path as _Path

_LOG_PATH = _Path("data/regime_log.csv")
_LOG_FIELDS = ["date", "dxy_score", "vix_score", "yield_score", "gold_score",
               "weighted_score", "bearish_count", "mode"]


def log_regime(scores: dict, weighted: float, bearish_count: int, mode: str,
               log_path: _Path = _LOG_PATH) -> None:
    """Append today's regime row to regime_log.csv (creates file if missing)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists()
    today = __import__("datetime").date.today().isoformat()
    row = {
        "date":           today,
        "dxy_score":      scores.get("DXY",   0),
        "vix_score":      scores.get("VIX",   0),
        "yield_score":    scores.get("YIELD", 0),
        "gold_score":     scores.get("GOLD",  0),
        "weighted_score": round(weighted, 4),
        "bearish_count":  bearish_count,
        "mode":           mode,
    }
    with open(log_path, "a", newline="") as f:
        writer = _csv.DictWriter(f, fieldnames=_LOG_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    run()
