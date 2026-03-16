"""
Backfill regime_log.csv with historical macro scores.
Run once. Generates ~180 days of labeled regime data immediately.

Usage:
    python scripts/backfill_regime_log.py
    python scripts/backfill_regime_log.py --days 90
    python scripts/backfill_regime_log.py --output data/regime_log.csv
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from macro_bias import fetch, score_instrument, SESSION_WEIGHTS

OUTPUT_DEFAULT = Path("data/regime_log.csv")
FIELDNAMES = ["date", "dxy_score", "vix_score", "yield_score", "gold_score",
              "weighted_score", "bearish_count", "mode"]


def backfill(days: int = 180, output: Path = OUTPUT_DEFAULT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Backfilling {days} days -> {output}")

    # Pull full history once per instrument
    history = {
        "DXY":   fetch("DX-Y.NYB", days=days + 10),
        "VIX":   fetch("^VIX",     days=days + 10),
        "US10Y": fetch("^TNX",     days=days + 10),
        "GOLD":  fetch("GC=F",     days=days + 10),
    }

    rows = []
    start = datetime.now(timezone.utc) - timedelta(days=days)

    for i in range(days):
        date = start + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")

        day_scores = {}
        bearish_count = 0

        for key, df in history.items():
            # Slice history up to this date
            mask = df.index <= date_str
            if mask.sum() < 2:
                continue
            sliced = df[mask]
            score = score_instrument(key, sliced)
            day_scores[key] = score
            if score < 0:
                bearish_count += 1

        if not day_scores:
            continue

        weighted = sum(
            day_scores.get(k, 0) * w
            for k, w in SESSION_WEIGHTS.items()
        )

        if weighted <= -0.3:
            mode = "SHORT-BIASED"
        elif weighted >= 0.3:
            mode = "LONG-BIASED"
        else:
            mode = "NEUTRAL"

        rows.append({
            "date":           date_str,
            "dxy_score":      day_scores.get("DXY",   0),
            "vix_score":      day_scores.get("VIX",   0),
            "yield_score":    day_scores.get("US10Y", 0),
            "gold_score":     day_scores.get("GOLD",  0),
            "weighted_score": round(weighted, 4),
            "bearish_count":  bearish_count,
            "mode":           mode,
        })

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. {len(rows)} rows written to {output}")
    short   = sum(1 for r in rows if r["mode"] == "SHORT-BIASED")
    neutral = sum(1 for r in rows if r["mode"] == "NEUTRAL")
    long_   = sum(1 for r in rows if r["mode"] == "LONG-BIASED")
    print(f"  SHORT-BIASED: {short}  NEUTRAL: {neutral}  LONG-BIASED: {long_}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",   type=int,  default=180)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    backfill(days=args.days, output=args.output)
