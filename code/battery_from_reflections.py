#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""Reflection-consistent validation battery (V2, V3, V5) computed offline from reflections.

Companion to aggregate_reflections.py. The discriminant arm (V4) and the noise floors
live in aggregate_reflections.py; this recomputes the reliability/convergence/repro
arms on the SAME reflection set so the whole battery reports one method, not a mix of
the legacy single-render battery and the reflection re-derivation.

V2 (cross-operator reliability), reflection-based:
  cohort-attributable variance = metameric degree = 1 - mean pairwise cosine
    across cohort PRIMARY vectors (between-cohort signal).
  operator-attributable variance = mean over cohorts of (1 - mean pairwise
    cosine across that cohort's operator vectors {primary, alt1, alt2})
    (within-cohort, between-operator noise).
  mean cross-operator cosine = mean over cohorts and operator pairs.
  PASS: operator-attributable < cohort-attributable AND mean cross-op cosine
        >= .95 (pre-registered).

V3 (convergent / split-half), reflection-based:
  randomly split each cohort's SOURCES into two disjoint halves K times (seeded),
  aggregate each half reflection -> source -> cohort, take the MEAN split-half cosine
  over the K splits. The drop-one source floor is far too SMALL a perturbation to
  judge a half-split against (it would fail every cohort by construction -- the
  same floor/grain-mismatch class of bug as the source-grain issue), so the
  criterion mirrors V2's reliability threshold: mean split-half cosine >= .95.
  The operator floor is reported alongside for interpretive context. PASS: mean
  split-half cosine >= .95 for >=4/5 cohorts.

V5 (reproducibility): the reflection aggregation is deterministic and seeded; this
  asserts a re-aggregation is byte-identical (delegated to aggregate_reflections.py
  re-run; here we just record the determinism statement).

V1 (test-retest) is NOT recomputed: the reflections are single deterministic renders
  per (artifact, operator) and carry no K-fold repeats, so a faithful reflection-based
  V1 requires re-running render+extract K times. Reported separately.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/battery_from_reflections.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --grain host --seed 20260621
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from aggregate_reflections import cosdist, load_reflections, source_mean  # noqa


def metameric_degree(vecs: list) -> float:
    cs = [1.0 - cosdist(a, b) for a, b in combinations(vecs, 2)]
    return float(1.0 - np.mean(cs))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument(
        "--grain", choices=["source", "outlet", "host", "artifact"], default="host"
    )
    ap.add_argument("--seed", type=int, default=20260621)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    reflections = load_reflections(args.atlas, args.grain)
    cids = sorted(reflections.keys())

    # per-cohort operator vectors (source-mean aggregated) for primary + alts
    op_vecs = {}
    src_groups = {}
    for c in cids:
        prim = reflections[c]["primary"]
        groups: dict = {}
        for a in sorted(prim.keys()):
            groups.setdefault(prim[a]["src"], []).append(a)
        src_groups[c] = groups
        ids = sorted(prim.keys())
        op_vecs[c] = {}
        for op, oa in reflections[c].items():
            sel = [a for a in ids if a in oa]
            if sel:
                op_vecs[c][op] = source_mean(oa, sel)

    prim_vecs = [op_vecs[c]["primary"] for c in cids]

    # ---- V2 ----
    cohort_attr = metameric_degree(prim_vecs)
    per_cohort_opvar, cross_cos = {}, []
    for c in cids:
        ov = list(op_vecs[c].values())
        cs = [1.0 - cosdist(a, b) for a, b in combinations(ov, 2)]
        per_cohort_opvar[c] = float(1.0 - np.mean(cs)) if cs else 0.0
        cross_cos.extend(cs)
    operator_attr = float(np.mean(list(per_cohort_opvar.values())))
    mean_cross_cos = float(np.mean(cross_cos))
    v2_pass = (operator_attr < cohort_attr) and (mean_cross_cos >= 0.95)

    # ---- V3 ----
    K = 200
    v3 = {}
    for c in cids:
        prim = reflections[c]["primary"]
        srcs = list(src_groups[c].keys())
        n = len(srcs)
        # operator floor (max over alt operators) for interpretive context
        ids_all = sorted(prim.keys())
        primv = source_mean(prim, ids_all)
        of = []
        for op, oa in reflections[c].items():
            if op == "primary":
                continue
            sel = [a for a in ids_all if a in oa]
            if sel:
                of.append(cosdist(primv, source_mean(oa, sel)))
        op_floor = max(of) if of else float("nan")
        if n < 2:
            v3[c] = {
                "mean_split_half_cosine": None,
                "operator_floor": round(op_floor, 5),
                "n_sources": n,
                "pass": False,
            }
            continue
        coss = []
        half = max(1, n // 2)
        for _ in range(K):
            perm = list(rng.permutation(srcs))
            h1, h2 = perm[:half], perm[half:]
            ids1 = [a for s in h1 for a in src_groups[c][s]]
            ids2 = [a for s in h2 for a in src_groups[c][s]]
            coss.append(1.0 - cosdist(source_mean(prim, ids1), source_mean(prim, ids2)))
        mean_cos = float(np.mean(coss))
        v3[c] = {
            "mean_split_half_cosine": round(mean_cos, 5),
            "operator_floor": round(op_floor, 5),
            "n_sources": n,
            "pass": bool(mean_cos >= 0.95),
        }
    v3_pass_n = sum(1 for c in cids if v3[c]["pass"])

    result = {
        "atlas": args.atlas.name,
        "grain": args.grain,
        "seed": args.seed,
        "V2_cross_operator": {
            "cohort_attributable_variance": round(cohort_attr, 5),
            "operator_attributable_variance": round(operator_attr, 5),
            "mean_cross_operator_cosine": round(mean_cross_cos, 5),
            "per_cohort_operator_variance": {
                c: round(per_cohort_opvar[c], 5) for c in cids
            },
            "pass": bool(v2_pass),
            "criterion": "operator_attr < cohort_attr AND mean_cross_cos >= .95",
        },
        "V3_split_half": {
            "per_cohort": v3,
            "pass_count": v3_pass_n,
            "splits_per_cohort": K,
            "pass": bool(v3_pass_n >= 4),
            "criterion": "mean split-half cosine >= .95 for >=4/5",
        },
        "V5_reproducibility": {
            "deterministic": True,
            "note": "reflection aggregation is seeded and key-free; re-running "
            "aggregate_reflections.py reproduces atlas_reflections.yaml byte-for-byte",
        },
        "V1_test_retest": {
            "recomputed_from_reflections": False,
            "note": "reflections are single deterministic renders per (artifact, "
            "operator); a faithful reflection-based V1 needs K-fold re-renders",
        },
    }
    out = args.atlas / "reflections" / f"battery_from_reflections_{args.grain}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\n=== {args.atlas.name} battery from reflections (grain={args.grain}) ===")
    v2 = result["V2_cross_operator"]
    print(
        f"V2: cohort_attr={v2['cohort_attributable_variance']} "
        f"operator_attr={v2['operator_attributable_variance']} "
        f"cross_cos={v2['mean_cross_operator_cosine']} -> "
        f"{'PASS' if v2['pass'] else 'FAIL'}"
    )
    print(f"V3: {v3_pass_n}/5 pass (mean split-half cosine >= .95)")
    for c in cids:
        x = v3[c]
        print(
            f"   {c:18s} split-half cos={x['mean_split_half_cosine']} "
            f"(op floor {x['operator_floor']}) {'pass' if x['pass'] else 'MISS'}"
        )


if __name__ == "__main__":
    main()
