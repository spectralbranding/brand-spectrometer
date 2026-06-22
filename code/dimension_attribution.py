#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""Which of the 8 dimensions drive the owners-vs-press separation? (#8)

The distributional test (cohort_separability.py) shows actual-owners separates
from the press cohorts in the fresh window, and the magnitude/shape decomposition
shows the separation is overwhelmingly MAGNITUDE (owners read the brand low across
dimensions, press read it high). This tool localizes that magnitude gap to
SPECIFIC dimensions with univariate effect sizes -- the interpretable companion to
the multivariate verdict.

Units are SOURCE-level dimension values (signal-source clustered, same as
cohort_separability.py: one value per source = mean of that source's primary
reflections on that dimension). For each dimension d it contrasts the focal cohort
(default actual-owners) against the pooled press cohorts AND against each press
cohort separately:

  - raw mean difference (press - focal) on the 0-10 scale (magnitude, in points);
  - Cohen's d (pooled-SD standardized effect size);
  - a source-label permutation p (9999 perms, seeded), Holm-corrected over the 8
    dimensions.

Offline, deterministic, no network.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/dimension_attribution.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --grain host --focal actual-owners --perms 9999 --seed 20260621
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from aggregate_reflections import DIMENSIONS, load_reflections, source_mean  # noqa


def cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return float("nan")
    sp2 = ((nx - 1) * x.var(ddof=1) + (ny - 1) * y.var(ddof=1)) / (nx + ny - 2)
    sp = np.sqrt(sp2)
    return float((y.mean() - x.mean()) / sp) if sp > 0 else 0.0


def perm_p_meandiff(x: np.ndarray, y: np.ndarray, perms: int, rng) -> float:
    """Two-sided permutation p on |mean(y) - mean(x)| over source labels."""
    obs = abs(y.mean() - x.mean())
    pool = np.concatenate([x, y])
    nx = len(x)
    ge = 1
    for _ in range(perms):
        perm = rng.permutation(len(pool))
        if abs(pool[perm[nx:]].mean() - pool[perm[:nx]].mean()) >= obs:
            ge += 1
    return ge / (perms + 1)


def source_dim_values(prim: dict, dim_idx: int) -> np.ndarray:
    """Per-source value on one dimension (mean of the source's primary reflections)."""
    groups: dict = {}
    for a in sorted(prim.keys()):
        groups.setdefault(prim[a]["src"], []).append(a)
    return np.array([source_mean(prim, ids)[dim_idx] for ids in groups.values()])


def holm(raw_p: np.ndarray) -> np.ndarray:
    m = len(raw_p)
    order = np.argsort(raw_p)
    out = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * raw_p[i])
        out[i] = min(running, 1.0)
    return out


def contrast(focal_prim, other_prims, perms, rng) -> dict:
    """Per-dimension owners-vs-(pooled other) contrast."""
    res = {}
    raw = []
    for di, dim in enumerate(DIMENSIONS):
        fx = source_dim_values(focal_prim, di)
        gy = np.concatenate([source_dim_values(p, di) for p in other_prims])
        p = perm_p_meandiff(fx, gy, perms, rng)
        raw.append(p)
        res[dim] = {
            "focal_mean": round(float(fx.mean()), 3),
            "other_mean": round(float(gy.mean()), 3),
            "raw_mean_diff": round(float(gy.mean() - fx.mean()), 3),
            "cohens_d": round(cohens_d(fx, gy), 3),
            "perm_p": round(p, 4),
            "n_focal_sources": len(fx),
            "n_other_sources": len(gy),
        }
    h = holm(np.array(raw))
    for j, dim in enumerate(DIMENSIONS):
        res[dim]["perm_p_holm"] = round(float(h[j]), 4)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument(
        "--grain", choices=["source", "outlet", "host", "artifact"], default="host"
    )
    ap.add_argument("--focal", default="actual-owners")
    ap.add_argument("--perms", type=int, default=9999)
    ap.add_argument("--seed", type=int, default=20260621)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    reflections = load_reflections(args.atlas, args.grain)
    cids = sorted(reflections.keys())
    if args.focal not in cids:
        raise SystemExit(f"focal {args.focal!r} not in {cids}")
    focal_prim = reflections[args.focal]["primary"]
    press = [c for c in cids if c != args.focal]

    pooled = contrast(
        focal_prim, [reflections[c]["primary"] for c in press], args.perms, rng
    )
    per_cohort = {
        c: contrast(focal_prim, [reflections[c]["primary"]], args.perms, rng)
        for c in press
    }

    out = {
        "atlas": args.atlas.name,
        "grain": args.grain,
        "focal": args.focal,
        "press_cohorts": press,
        "perms": args.perms,
        "seed": args.seed,
        "effect_size": "Cohen's d (pooled SD); raw_mean_diff on 0-10 scale",
        "multiple_comparison": "Holm (FWER) over the 8 dimensions",
        "focal_vs_pooled_press": pooled,
        "focal_vs_each_press": per_cohort,
        "note": (
            "source-level per-dimension values (signal-source clustered). "
            "Localizes the multivariate owners-vs-press separation to "
            "specific dimensions; positive raw_mean_diff = press read the "
            "brand HIGHER than owners on that dimension."
        ),
    }
    (
        args.atlas / "reflections" / f"dimension_attribution_{args.grain}.json"
    ).write_text(json.dumps(out, indent=2) + "\n")
    print(
        f"\n=== {args.atlas.name} dimension attribution: "
        f"{args.focal} vs pooled press (grain={args.grain}) ==="
    )
    print(f"{'dimension':14s} focal  press  diff   d     perm_p  Holm")
    for dim in sorted(DIMENSIONS, key=lambda d: -abs(pooled[d]["cohens_d"])):
        r = pooled[dim]
        star = " *" if r["perm_p_holm"] < 0.05 else ""
        print(
            f"  {dim:12s} {r['focal_mean']:5.2f} {r['other_mean']:5.2f} "
            f"{r['raw_mean_diff']:+5.2f} {r['cohens_d']:+5.2f} "
            f"{r['perm_p']:.4f}  {r['perm_p_holm']:.4f}{star}"
        )


if __name__ == "__main__":
    main()
