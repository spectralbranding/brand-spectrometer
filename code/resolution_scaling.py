#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""How much data would the Brand Spectrometer need to RESOLVE a cohort pair?

Companion to aggregate_reflections.py. Answers "what N gives enough resolution" by
decomposing the per-pair signal-to-noise into what shrinks with more data and
what does not.

THE DECOMPOSITION
-----------------
S/N = d(Ci,Cj) / max(O_i, O_j), with the operator floor O = cosine distance
between a cohort's primary-operator mean and its alternate-operator mean over
the SAME sources. Both means are estimated from n_sources sources, so each
carries sampling scatter ~ 1/sqrt(n). Independent scatter in two vectors only
ADDS cosine distance, so the MEASURED operator floor is inflated above its
asymptotic systematic value O_inf and DECREASES toward O_inf as n grows. The
same inflation affects the measured pair distance d. Therefore:

  - the part of the floor that is SAMPLING NOISE shrinks with more sources /
    artifacts (collect more);
  - the part that is SYSTEMATIC cross-operator bias (O_inf) does NOT shrink with
    more artifacts -- it only falls with better or more-averaged operator pairs,
    or is cleared by a window whose true cohort separation d_inf is larger.

If the asymptotic S/N (d_inf / O_inf) already exceeds 1, there is a finite
source count n* at which the pair resolves and we estimate it. If it does not,
no amount of artifact collection resolves that pair on that window -- resolution
is operator-limited or window-limited, and we say so rather than promising N.

METHOD (empirical, offline, seeded)
-----------------------------------
1. Source-subsample learning curve: for n = 3..n_sources, draw B subsamples of
   sources (without replacement), recompute the aggregate S/N, report median and
   2.5/97.5 percentiles -- the observed trajectory of S/N with sample size.
2. Asymptote estimate: fit measured floor^2(n) ~ O_inf^2 + a/n (the leading
   sampling-noise term for squared cosine distance) by OLS on 1/n, read O_inf;
   likewise d_inf. Report S/N_inf = d_inf / O_inf and, when the trajectory is
   rising and S/N_inf>1, the extrapolated n* where median S/N first exceeds 1.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/resolution_scaling.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --grain host --draws 4000 --seed 20260621
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from aggregate_reflections import (
    DIMENSIONS,
    cosdist,
    load_reflections,
    source_mean,
)  # noqa


def cohort_sn_from_sources(reflections_c: dict, prim_groups: dict, src_subset: list):
    """Aggregate-window helper not used directly; kept for symmetry."""
    raise NotImplementedError


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument(
        "--grain", choices=["source", "outlet", "host", "artifact"], default="host"
    )
    ap.add_argument("--draws", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20260621)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    reflections = load_reflections(args.atlas, args.grain)
    cids = sorted(reflections.keys())

    # per-cohort: source -> list of (op -> mean vec over that source's reflections)
    # we need, for each cohort, the source keys and per-source per-op reflection lists
    src_keys, per = {}, {}
    for c in cids:
        groups: dict = {}
        for a in sorted(reflections[c]["primary"].keys()):
            groups.setdefault(reflections[c]["primary"][a]["src"], []).append(a)
        src_keys[c] = list(groups.keys())
        per[c] = groups

    def agg_sn_for_subset(subset: dict) -> float:
        """subset: cohort -> list of chosen source keys -> aggregate S/N."""
        cvec, ofloor = {}, {}
        for c in cids:
            prim = reflections[c]["primary"]
            ids = [a for s in subset[c] for a in per[c][s]]
            m = source_mean(prim, ids)
            cvec[c] = m
            alt = []
            for op, oa in reflections[c].items():
                if op == "primary":
                    continue
                sel = [a for a in ids if a in oa]
                if sel:
                    alt.append(cosdist(m, source_mean(oa, sel)))
            ofloor[c] = max(alt) if alt else np.nan
        dists = [cosdist(cvec[a], cvec[b]) for a, b in combinations(cids, 2)]
        of = [ofloor[c] for c in cids if not np.isnan(ofloor[c])]
        return float(np.mean(dists)) / float(np.mean(of))

    nmax = min(len(src_keys[c]) for c in cids)
    curve = {}
    floor_by_n, dist_by_n = {}, {}  # for asymptote fit (aggregate means)
    for n in range(3, nmax + 1):
        sns, floors, dists = [], [], []
        for _ in range(args.draws):
            subset = {
                c: list(rng.choice(src_keys[c], size=n, replace=False)) for c in cids
            }
            # collect floor/dist means too
            cvec, ofloor = {}, {}
            for c in cids:
                prim = reflections[c]["primary"]
                ids = [a for s in subset[c] for a in per[c][s]]
                m = source_mean(prim, ids)
                cvec[c] = m
                alt = []
                for op, oa in reflections[c].items():
                    if op == "primary":
                        continue
                    sel = [a for a in ids if a in oa]
                    if sel:
                        alt.append(cosdist(m, source_mean(oa, sel)))
                ofloor[c] = max(alt) if alt else np.nan
            d = float(
                np.mean([cosdist(cvec[a], cvec[b]) for a, b in combinations(cids, 2)])
            )
            of = float(np.mean([ofloor[c] for c in cids if not np.isnan(ofloor[c])]))
            sns.append(d / of)
            floors.append(of)
            dists.append(d)
        lo, med, hi = np.percentile(sns, [2.5, 50, 97.5])
        curve[n] = {
            "median": round(float(med), 4),
            "lo": round(float(lo), 4),
            "hi": round(float(hi), 4),
        }
        floor_by_n[n] = float(np.mean(floors))
        dist_by_n[n] = float(np.mean(dists))

    # asymptote fit: floor^2 ~ Oinf^2 + a/n ; dist^2 ~ dinf^2 + b/n
    ns = np.array(sorted(floor_by_n))
    inv = 1.0 / ns

    def fit_inf(y2):
        A = np.vstack([np.ones_like(inv), inv]).T
        coef, *_ = np.linalg.lstsq(A, y2, rcond=None)
        return float(np.sqrt(max(coef[0], 0.0)))  # intercept = squared asymptote

    o_inf = fit_inf(np.array([floor_by_n[n] for n in ns]) ** 2)
    d_inf = fit_inf(np.array([dist_by_n[n] for n in ns]) ** 2)
    sn_inf = d_inf / o_inf if o_inf else float("nan")

    # extrapolate n* where median S/N first exceeds 1 (model S/N(n) via fitted
    # floor(n), dist(n): floor(n)=sqrt(Oinf^2+a/n), dist(n)=sqrt(dinf^2+b/n))
    def coef_fit(y2):
        A = np.vstack([np.ones_like(inv), inv]).T
        coef, *_ = np.linalg.lstsq(A, y2, rcond=None)
        return float(max(coef[0], 0.0)), float(coef[1])

    o2, oa = coef_fit(np.array([floor_by_n[n] for n in ns]) ** 2)
    d2, db = coef_fit(np.array([dist_by_n[n] for n in ns]) ** 2)
    n_star = None
    if sn_inf > 1.0:
        for n in range(3, 100000):
            fl = np.sqrt(max(o2 + oa / n, 1e-12))
            ds = np.sqrt(max(d2 + db / n, 1e-12))
            if ds / fl > 1.0:
                n_star = n
                break

    # current full-sample aggregate S/N (all sources) and the LEVERS that would
    # reach resolution, since the n* route returns None when not sample-limited.
    sn_now = agg_sn_for_subset({c: src_keys[c] for c in cids})
    levers = {
        "aggregate_sn_full_sample": round(sn_now, 4),
        "operator_tighten_factor_for_sn_gt_1": round(1.0 / sn_now, 3),
        "operator_tighten_factor_for_sn_gt_2": round(2.0 / sn_now, 3),
        "divergence_multiple_for_sn_gt_1": round(1.0 / sn_now, 3),
        "divergence_multiple_for_sn_gt_2": round(2.0 / sn_now, 3),
        "note": (
            "S/N = d / O. The learning curve is ~flat in n and its CI "
            "TIGHTENS around a sub-1 value as sources grow, so collecting "
            "more artifacts makes the abstention MORE confident, not less. "
            "To resolve, cut the systematic operator floor O by the tighten "
            "factor (more/better-agreeing cross-family operator pairs) OR "
            "measure a window whose true cohort divergence d is larger by "
            "the divergence multiple."
        ),
    }

    result = {
        "atlas": args.atlas.name,
        "grain": args.grain,
        "draws": args.draws,
        "seed": args.seed,
        "n_sources_per_cohort": {c: len(src_keys[c]) for c in cids},
        "resolution_levers": levers,
        "learning_curve_aggregate_sn": curve,
        "asymptote": {
            "operator_floor_inf": round(o_inf, 4),
            "pair_distance_inf": round(d_inf, 4),
            "aggregate_sn_inf": round(sn_inf, 4),
        },
        "interpretation": (
            "resolution-feasible: a finite source count reaches S/N>1"
            if (sn_inf > 1.0)
            else "operator/window-limited: asymptotic S/N<=1, so more artifacts alone "
            "do not resolve; needs tighter operators (more/better cross-family "
            "pairs lowering the systematic floor) or a window with larger true "
            "cohort divergence"
        ),
        "n_star_sources_for_sn_gt_1": n_star,
    }
    out = args.atlas / "reflections" / f"resolution_scaling_{args.grain}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\n=== {args.atlas.name} resolution scaling (grain={args.grain}) ===")
    print("n_sources/cohort:", result["n_sources_per_cohort"])
    print("learning curve (aggregate S/N median [lo,hi]):")
    for n in sorted(curve):
        c = curve[n]
        print(f"  n={n:2d}  {c['median']}  [{c['lo']}, {c['hi']}]")
    print("asymptote:", result["asymptote"])
    print("levers:", {k: v for k, v in levers.items() if k != "note"})
    print("verdict:", result["interpretation"])
    print("n* sources for S/N>1:", n_star)


if __name__ == "__main__":
    main()
