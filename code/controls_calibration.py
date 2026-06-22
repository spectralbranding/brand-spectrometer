#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""Positive + negative controls (#5) and false-positive calibration (#6).

The collapsed two-window contrast used to play the role of showing the instrument
can BOTH resolve and abstain. Controls replace that role on firmer ground, and the
calibration delivers the paper's promised Monte-Carlo appendix.

NEGATIVE CONTROL (must ABSTAIN).
  Split ONE real cohort's sources into two random pseudo-cohorts. They are the
  same cohort, so a calibrated metric must not separate them: we report the share
  of random splits whose operator-floored distributional S/N exceeds 1 and whose
  energy-distance permutation p < .05 -- the empirical false-resolution rate on
  same-cohort data. Should sit near the nominal level, not high.

FALSE-POSITIVE CALIBRATION (the Monte-Carlo appendix, #6).
  Pool ALL source units across cohorts and repeatedly split them at random into
  two groups (no real cohort structure). The resulting operator-floored S/N values
  are the NULL distribution of the rule. From it we read (a) the empirical FPR of
  the S/N>1 call and (b) the threshold k giving target FPRs (5%, 1%) -- i.e. how
  conservative S/N>1 actually is.

POSITIVE CONTROL (must RESOLVE).
  Take the same pooled random split but ADD a known magnitude shift delta to one
  group's vectors (a planted, magnitude-only separation -- the kind owners-vs-press
  exhibits). The S/N must rise through 1 as delta grows, proving the operator
  floors are not trivially inflated to suppress all signal. Reported as a small
  delta sweep (mean S/N + resolve rate).

Units are SOURCE units carrying every operator's reflections, so operator floors are
computed exactly as in cohort_separability.py. Offline, deterministic, no network.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/controls_calibration.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --grain host --splits 500 --perms 999 --draws 4000 --seed 20260621
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from aggregate_reflections import load_reflections  # noqa
from cohort_separability import energy_distance  # noqa


def source_units(reflections_c: dict) -> dict:
    """One cohort's reflections -> {src: {op: [vecs]}} (a source carries every operator)."""
    units: dict = {}
    for op, d in reflections_c.items():
        for rec in d.values():
            units.setdefault(rec["src"], {}).setdefault(op, []).append(rec["vec"])
    return units


def primary_cloud(units: dict, keys: list, shift: np.ndarray | None = None):
    rows = []
    for s in keys:
        ops = units[s]
        if "primary" in ops:
            v = np.mean(ops["primary"], axis=0)
            rows.append(v + shift if shift is not None else v)
    return np.array(rows)


def op_floor(units: dict, keys: list, shift: np.ndarray | None = None) -> float:
    """Distributional operator floor over the given source keys (shift cancels)."""
    P = primary_cloud(units, keys, shift)
    if len(P) == 0:
        return float("nan")
    alts = set()
    for s in keys:
        alts |= set(units[s].keys())
    alts.discard("primary")
    floors = []
    for op in alts:
        a_rows = []
        for s in keys:
            if op in units[s]:
                v = np.mean(units[s][op], axis=0)
                a_rows.append(v + shift if shift is not None else v)
        if a_rows:
            floors.append(energy_distance(P, np.array(a_rows)))
    return max(floors) if floors else float("nan")


def sn(units: dict, keysA: list, keysB: list, shiftA=None, shiftB=None) -> float:
    PA = primary_cloud(units, keysA, shiftA)
    PB = primary_cloud(units, keysB, shiftB)
    if len(PA) == 0 or len(PB) == 0:
        return float("nan")
    fl = max(op_floor(units, keysA, shiftA), op_floor(units, keysB, shiftB))
    D = energy_distance(PA, PB)
    return D / fl if fl and fl > 0 else float("nan")


def perm_p(units: dict, keysA: list, keysB: list, perms: int, rng) -> float:
    PA, PB = primary_cloud(units, keysA), primary_cloud(units, keysB)
    if len(PA) == 0 or len(PB) == 0:
        return float("nan")
    obs = energy_distance(PA, PB)
    pool = keysA + keysB
    nA = len(keysA)
    ge = 1
    for _ in range(perms):
        perm = rng.permutation(len(pool))
        ka = [pool[i] for i in perm[:nA]]
        kb = [pool[i] for i in perm[nA:]]
        if energy_distance(primary_cloud(units, ka), primary_cloud(units, kb)) >= obs:
            ge += 1
    return ge / (perms + 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument(
        "--grain", choices=["source", "outlet", "host", "artifact"], default="host"
    )
    ap.add_argument(
        "--splits",
        type=int,
        default=500,
        help="random splits per negative-control cohort",
    )
    ap.add_argument(
        "--perms",
        type=int,
        default=999,
        help="permutations for the negative-control perm-p",
    )
    ap.add_argument(
        "--draws",
        type=int,
        default=4000,
        help="pooled random splits for the null S/N distribution",
    )
    ap.add_argument("--deltas", type=float, nargs="+", default=[0.5, 1.0, 2.0, 3.0])
    ap.add_argument("--seed", type=int, default=20260621)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    reflections = load_reflections(args.atlas, args.grain)
    cids = sorted(reflections.keys())

    # ---- NEGATIVE CONTROL: same-cohort random splits must abstain ----
    neg = {}
    for c in cids:
        units = source_units(reflections[c])
        keys = [s for s in units if "primary" in units[s]]
        if len(keys) < 4:
            neg[c] = {"skipped": f"only {len(keys)} sources"}
            continue
        sns, ps = [], []
        for _ in range(args.splits):
            perm = list(rng.permutation(keys))
            half = len(perm) // 2
            kA, kB = perm[:half], perm[half:]
            s = sn(units, kA, kB)
            if not np.isnan(s):
                sns.append(s)
            ps.append(perm_p(units, kA, kB, args.perms, rng))
        sns, ps = np.array(sns), np.array(ps)
        neg[c] = {
            "n_sources": len(keys),
            "median_sn": round(float(np.median(sns)), 4),
            "mean_sn": round(float(np.mean(sns)), 4),
            "false_resolve_rate_sn_gt_1": round(float(np.mean(sns > 1)), 4),
            "false_resolve_rate_permp_lt_.05": round(float(np.mean(ps < 0.05)), 4),
        }

    # ---- pooled source units across all cohorts (namespaced) ----
    pooled: dict = {}
    for c in cids:
        for s, ops in source_units(reflections[c]).items():
            pooled[f"{c}::{s}"] = ops
    pkeys = [s for s in pooled if "primary" in pooled[s]]
    # representative split size = median cohort source count
    sizes = sorted(
        len(
            [
                s
                for s in source_units(reflections[c])
                if "primary" in source_units(reflections[c])[s]
            ]
        )
        for c in cids
    )
    nA = sizes[len(sizes) // 2]

    # ---- FALSE-POSITIVE CALIBRATION: null S/N distribution (delta=0) ----
    null_sn = []
    for _ in range(args.draws):
        perm = list(rng.permutation(pkeys))
        kA, kB = perm[:nA], perm[nA : 2 * nA]
        s = sn(pooled, kA, kB)
        if not np.isnan(s):
            null_sn.append(s)
    null_sn = np.array(null_sn)
    k5, k1 = np.percentile(null_sn, [95, 99])
    calibration = {
        "null_split_sizes": [nA, nA],
        "draws": len(null_sn),
        "null_sn_percentiles": {
            p: round(float(np.percentile(null_sn, p)), 4) for p in (50, 90, 95, 99)
        },
        "empirical_fpr_at_sn_gt_1": round(float(np.mean(null_sn > 1)), 4),
        "k_for_fpr_.05": round(float(k5), 4),
        "k_for_fpr_.01": round(float(k1), 4),
        "note": (
            "null = random splits of all source units pooled across cohorts; "
            "S/N>1 FPR is how often a no-structure split looks resolved."
        ),
    }

    # ---- POSITIVE CONTROL: planted magnitude shift must resolve ----
    positive = {}
    for delta in args.deltas:
        shift = np.full(8, float(delta))
        sns = []
        for _ in range(args.draws // 4):
            perm = list(rng.permutation(pkeys))
            kA, kB = perm[:nA], perm[nA : 2 * nA]
            s = sn(pooled, kA, kB, shiftB=shift)  # shift group B only
            if not np.isnan(s):
                sns.append(s)
        sns = np.array(sns)
        positive[f"delta_{delta}"] = {
            "shift_per_dim": delta,
            "median_sn": round(float(np.median(sns)), 4),
            "resolve_rate_sn_gt_1": round(float(np.mean(sns > 1)), 4),
            "resolve_rate_sn_gt_k5": round(float(np.mean(sns > k5)), 4),
        }

    out = {
        "atlas": args.atlas.name,
        "grain": args.grain,
        "seed": args.seed,
        "splits": args.splits,
        "perms": args.perms,
        "draws": args.draws,
        "negative_control": neg,
        "false_positive_calibration": calibration,
        "positive_control": positive,
        "interpretation": (
            "Negative: same-cohort splits should rarely resolve (low false-resolve "
            "rate). Calibration: S/N>1 has the reported empirical FPR; k_for_fpr_.05 "
            "is the threshold matching a 5% false-resolution rate. Positive: a "
            "planted magnitude shift resolves as delta grows, so the floors are not "
            "trivially inflated. Together they bracket the instrument: it abstains "
            "on no-structure data and resolves a real magnitude separation."
        ),
    }
    (args.atlas / "reflections" / f"controls_calibration_{args.grain}.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(f"\n=== {args.atlas.name} controls + calibration (grain={args.grain}) ===")
    print("NEGATIVE CONTROL (same-cohort splits should abstain):")
    for c in cids:
        r = neg[c]
        if "skipped" in r:
            print(f"  {c:18s} skipped ({r['skipped']})")
        else:
            print(
                f"  {c:18s} median S/N={r['median_sn']} "
                f"false-resolve(S/N>1)={r['false_resolve_rate_sn_gt_1']} "
                f"false-resolve(p<.05)={r['false_resolve_rate_permp_lt_.05']}"
            )
    cal = calibration
    print(
        f"\nCALIBRATION (null split {cal['null_split_sizes']}, {cal['draws']} draws):"
    )
    print(f"  null S/N pct {cal['null_sn_percentiles']}")
    print(f"  empirical FPR at S/N>1 = {cal['empirical_fpr_at_sn_gt_1']}")
    print(
        f"  k for FPR .05 = {cal['k_for_fpr_.05']}; k for FPR .01 = {cal['k_for_fpr_.01']}"
    )
    print("\nPOSITIVE CONTROL (planted shift must resolve):")
    for d, r in positive.items():
        print(
            f"  {d:10s} median S/N={r['median_sn']} "
            f"resolve(S/N>1)={r['resolve_rate_sn_gt_1']} "
            f"resolve(S/N>k5)={r['resolve_rate_sn_gt_k5']}"
        )


if __name__ == "__main__":
    main()
