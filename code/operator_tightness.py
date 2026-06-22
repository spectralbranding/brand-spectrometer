#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""Can tighter operators lower the floor enough to resolve? Offline preview.

The operator floor is the binding noise (see resolution_scaling.py). This asks,
WITHOUT spending on new renders, how much headroom the operators we ALREADY have
imply, by examining the three operators per cohort (primary + 2 alts):

1. Per-cohort pairwise operator agreement (which family pairing agrees most).
2. MAX-pairwise floor (current definition) vs ENSEMBLE-centroid floor (max
   distance of any single operator from the 3-operator centroid). Averaging
   operators (an ensemble renderer/extractor) shrinks the floor toward the
   centroid; this previews the gain from ensembling the operators we have.
3. TIGHTEST-pair floor: if we kept only the single best-agreeing alt operator
   pair, what floor and aggregate S/N would result -- the optimistic bound from
   operator SELECTION rather than collection.

Reports the aggregate S/N under each floor definition so we can see whether any
operator strategy on the CURRENT operator set crosses S/N=1 before committing to
new model families.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/operator_tightness.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --grain host
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from aggregate_reflections import cosdist, load_reflections, source_mean  # noqa


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument(
        "--grain", choices=["source", "outlet", "host", "artifact"], default="host"
    )
    args = ap.parse_args()
    reflections = load_reflections(args.atlas, args.grain)
    cids = sorted(reflections.keys())

    op_vecs, floors = {}, {}
    for c in cids:
        prim = reflections[c]["primary"]
        ids = sorted(prim.keys())
        op_vecs[c] = {}
        for op, oa in reflections[c].items():
            sel = [a for a in ids if a in oa]
            if sel:
                op_vecs[c][op] = source_mean(oa, sel)
        primv = op_vecs[c]["primary"]
        alts = {op: v for op, v in op_vecs[c].items() if op != "primary"}
        # current MAX-pairwise floor = max dist(primary, alt)
        max_floor = max(cosdist(primv, v) for v in alts.values())
        # ensemble centroid of all operators
        cent = np.mean(list(op_vecs[c].values()), axis=0)
        ens_floor = max(cosdist(cent, v) for v in op_vecs[c].values())
        # tightest single alt pair
        tight_alt = min(alts, key=lambda op: cosdist(primv, alts[op]))
        tight_floor = cosdist(primv, alts[tight_alt])
        floors[c] = {
            "max_pairwise_floor": round(max_floor, 4),
            "ensemble_centroid_floor": round(ens_floor, 4),
            "tightest_alt": tight_alt,
            "tightest_pair_floor": round(tight_floor, 4),
            "alt_distances": {
                op: round(cosdist(primv, v), 4) for op, v in alts.items()
            },
        }

    prim_vecs = {c: op_vecs[c]["primary"] for c in cids}
    cent_vecs = {c: np.mean(list(op_vecs[c].values()), axis=0) for c in cids}

    def agg_sn(vec_of, floor_key):
        dists = [cosdist(vec_of[a], vec_of[b]) for a, b in combinations(cids, 2)]
        ofs = [floors[c][floor_key] for c in cids]
        return round(float(np.mean(dists)) / float(np.mean(ofs)), 4)

    out = {
        "atlas": args.atlas.name,
        "grain": args.grain,
        "per_cohort": floors,
        "aggregate_sn": {
            "current_max_pairwise": agg_sn(prim_vecs, "max_pairwise_floor"),
            "ensemble_centroid": agg_sn(cent_vecs, "ensemble_centroid_floor"),
            "tightest_pair_selection": agg_sn(prim_vecs, "tightest_pair_floor"),
        },
        "note": (
            "ensemble_centroid uses the 3-operator mean as the cohort "
            "vector AND the centroid floor; tightest_pair keeps only the "
            "best-agreeing alt. Both are OPTIMISTIC previews from the "
            "current operator set -- a true test needs NEW model families."
        ),
    }
    (args.atlas / "reflections" / f"operator_tightness_{args.grain}.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(f"\n=== {args.atlas.name} operator tightness (grain={args.grain}) ===")
    for c in cids:
        f = floors[c]
        print(
            f"  {c:18s} max={f['max_pairwise_floor']} "
            f"ens={f['ensemble_centroid_floor']} "
            f"tight={f['tightest_pair_floor']} ({f['tightest_alt']}) "
            f"alts={f['alt_distances']}"
        )
    print("aggregate S/N:", out["aggregate_sn"])


if __name__ == "__main__":
    main()
