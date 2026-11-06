#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Brand-name mention density by cohort for the fresh-window atlas (offline).

Checks whether the two cohorts of the resolved pair (actual-owners vs
non-italian-press) differ in how often their artifacts name the brand. If they
did, part of the distributional separation could reflect name frequency rather
than observer voice. Answers the precondition only: no LLM calls, and no claim
that the instrument is invariant to name density.

Input: name_density_rows.csv in the atlas directory, one row per artifact with
word count and brand-mention count. The counts were taken from the artifact
excerpts the renderer read (the marque, "Ferrari" / "法拉利", counted; the
product name counted separately and never pooled). The excerpts themselves
belong to the acquisition layer and are not redistributed; the counts are.

Statistic: brand mentions per 1,000 words, difference in cohort means, two-sided
permutation test (99,999 permutations, seed 20260830). Writes name_density.json
in the atlas directory. Deterministic.

Run:
    uv run python code/name_density.py --atlas data/ferrari_luce_fresh_2606
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from pathlib import Path

SEED = 20260830
ITERS = 99_999
PAIR = ("actual-owners", "non-italian-press")


def per_1k(row: dict) -> float:
    return round(1000 * int(row["brand_mentions"]) / int(row["words"]), 2)


def permutation_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Two-sided permutation test on the absolute difference in means."""
    rng = random.Random(SEED)
    obs = abs(statistics.mean(a) - statistics.mean(b))
    pool = a + b
    n = len(a)
    hits = 0
    for _ in range(ITERS):
        rng.shuffle(pool)
        if abs(statistics.mean(pool[:n]) - statistics.mean(pool[n:])) >= obs:
            hits += 1
    return obs, (hits + 1) / (ITERS + 1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--atlas", required=True, type=Path)
    args = ap.parse_args()

    with (args.atlas / "name_density_rows.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))

    cohorts: dict[str, list[float]] = {}
    for r in rows:
        cohorts.setdefault(r["cohort"], []).append(per_1k(r))

    summary = {
        c: {
            "n": len(v),
            "mean_per_1k": round(statistics.mean(v), 2),
            "median_per_1k": round(statistics.median(v), 2),
        }
        for c, v in sorted(cohorts.items())
    }
    a, b = cohorts[PAIR[0]], cohorts[PAIR[1]]
    diff, p = permutation_test(a, b)
    result = {
        "statistic": "brand mentions per 1,000 words",
        "seed": SEED,
        "permutations": ITERS,
        "by_cohort": summary,
        "resolved_pair": {
            "pair": f"{PAIR[0]}|{PAIR[1]}",
            "abs_mean_difference_per_1k": round(diff, 2),
            "permutation_p": round(p, 3),
        },
    }
    (args.atlas / "name_density.json").write_text(json.dumps(result, indent=2) + "\n")

    for c, s in summary.items():
        print(f"  {c:<20} n={s['n']:<3} mean {s['mean_per_1k']:6.2f}")
    print(
        f"  resolved pair {PAIR[0]} vs {PAIR[1]}: |difference| = {diff:.2f} "
        f"per 1k words, permutation p = {p:.3f}"
    )


if __name__ == "__main__":
    main()
