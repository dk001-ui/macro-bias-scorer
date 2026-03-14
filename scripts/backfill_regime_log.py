"""
Backfill regime_log.csv with historical macro scores.
Run once. Generates ~180 days of labeled regime data immediately.

Usage:
    python scripts/backfill_regime_log.py --days 180
"""

import argparse
import csv
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from macro_bias import INSTRUMENTS, fetch, score_instrument, get_session_mode, LOOKBACK_DAYS

LOG_PATH   = "data/regime_log.csv"
FIELDNAMES = ["timestamp_utc", "regime_label", "confidence",
              "dxy_score", "vix_score", "yield_score", "gold_score", "composite_score"]


def backfill(days: int = 180):
    # Fetch enough history to score each date in the window
    # Need LOOKBACK_DAYS of prior data before each target date
    all_data = {}
    for name, cfg in INSTRUMENTS.items():
        df = fetch(cfg["ticker"], days=days + LOOKBACK_DAYS + 10)
        if df is None:
            print(f"[WARN] Could not fetch {name}, skipping backfill.")
            return
        # Normalize multi-level columns if present (yfinance quirk)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        all_data[name] = df

    # Target dates: last `days` trading days in the fetched data
    ref_dates = all_data["DXY"].index[-days:]

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    rows = []

    for date in ref_dates:
        bearish_count = 0
        scores = {}

        for name, df in all_data.items():
            # Slice: only data up to and including this date (no lookahead)
            slice_df = df[df.index <= date].tail(LOOKBACK_DAYS)
            if len(slice_df) < 16:
                continue

            result = score_instrument(name, slice_df)
            scores[name] = result["score"]
            if result["score"] == 1:
                bearish_count += 1

        mode, _ = get_session_mode(bearish_count)
        confidence = round(
            (bearish_count if mode == "SHORT-BIASED" else 4 - bearish_count) / 4, 4
        )

        rows.append({
            "timestamp_utc":   date.strftime("%Y-%m-%dT09:30:00+00:00"),
            "regime_label":    mode,
            "confidence":      confidence,
            "dxy_score":       scores.get("DXY",   0),
            "vix_score":       scores.get("VIX",   0),
            "yield_score":     scores.get("US10Y", 0),
            "gold_score":      scores.get("GOLD",  0),
            "composite_score": bearish_count,
        })

    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Backfilled {len(rows)} trading days -> {LOG_PATH}")
    print(f"     Date range: {rows[0]['timestamp_utc'][:10]} to {rows[-1]['timestamp_utc'][:10]}")

    # Regime distribution summary
    labels = [r["regime_label"] for r in rows]
    for label in ["LONG-BIASED", "NEUTRAL", "SHORT-BIASED"]:
        count = labels.count(label)
        print(f"     {label}: {count} days ({100 * count // len(labels)}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=180)
    args = parser.parse_args()
    backfill(args.days)
