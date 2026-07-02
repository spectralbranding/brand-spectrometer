# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "numpy>=1.26",
#   "pyyaml>=6.0",
# ]
# ///
"""
preflight.py — pre-run verification equipment for a Brand Spectrometer campaign.

Two checks, both METHODOLOGY §3 (v0.3 additive); run them before any campaign:

  concordance    Pre-flight operator concordance. Scores each configured
                 operator's leave-one-out vector concordance on a small pilot
                 (every operator reads the same stimuli) and applies the
                 mechanical exclusion rule fixed ex ante by PRISM-M
                 (Zharnikov 2026az, DOI 10.5281/zenodo.21125785): a unit whose
                 discordance exceeds 3x the median of the remaining units is
                 excluded from every floor and pooled vector, retained only as
                 a reported exploratory observer. The decision is mechanical —
                 the rule is invoked, not judged.

  version-floor  Pre-run version check. Compares the configured operator
                 model-version strings against the versions the sealed-panel
                 version floor was last measured under (PRISM-T, Zharnikov
                 2026ba, DOI 10.5281/zenodo.21128779; manifest at
                 ../data/version_floor_manifest.json). Any configured version
                 absent from the manifest makes the version floor STALE for
                 this run: the run report must carry the line
                 "version floor stale -- re-read the sealed panel".

Run:
    uv run python preflight.py concordance --readings pilot_readings.json
    uv run python preflight.py version-floor --operators claude-opus-4-8,gpt-5.4-mini-2026-03-17
    uv run python preflight.py version-floor --atlas ../atlases/<brand>/atlas.yaml

Readings input (concordance): JSON mapping operator -> list of 8-d vectors
aligned by index (same stimulus order per operator), or JSONL rows with
"operator", "stimulus", "dims" fields (grouped and aligned here).

Exit codes:
    0  check passed (no exclusions / versions fresh)
    1  finding (operator(s) excluded / version floor stale)
    2  invocation error

The concordance math lives in prism_core (the PRISM instrument-family base
library); this script invokes it, never re-implements it. On the public tool
mirror, prism_core ships with the PRISM paper repositories — clone one next
to this tree or point PYTHONPATH at it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
_RESEARCH_DIR = _CODE_DIR.parents[1]  # research/
sys.path.insert(0, str(_RESEARCH_DIR))

try:
    from prism_core.concordance import (  # noqa: E402
        RULE_MULTIPLE,
        apply_exclusion_rule,
        vector_concordance,
    )
except ImportError as e:  # pragma: no cover - mirror-layout guidance only
    print(
        "error: prism_core not importable ({}). The concordance rule lives in\n"
        "the PRISM instrument-family base library; run from the research tree\n"
        "or put prism_core's parent directory on PYTHONPATH.".format(e),
        file=sys.stderr,
    )
    raise SystemExit(2)

DEFAULT_MANIFEST = _CODE_DIR.parent / "data" / "version_floor_manifest.json"

STALE_LINE = "version floor stale -- re-read the sealed panel"


# ---------------------------------------------------------------------------
# concordance subcommand
# ---------------------------------------------------------------------------


def _load_readings(path: Path) -> dict[str, list]:
    """Load pilot readings as operator -> list of 8-d vectors.

    Accepts a JSON object {operator: [[8 floats], ...]} (aligned by index)
    or a JSONL file of rows {"operator": ..., "stimulus": ..., "dims": [8]}
    (aligned here on the sorted union of stimulus keys; a missing cell is
    None, which prism_core treats as absent).
    """
    if path.suffix == ".jsonl":
        rows = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
        stimuli = sorted({r["stimulus"] for r in rows})
        by_op: dict[str, dict] = {}
        for r in rows:
            by_op.setdefault(r["operator"], {})[r["stimulus"]] = r.get("dims")
        return {op: [cells.get(s) for s in stimuli] for op, cells in by_op.items()}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("readings JSON must map operator -> list of vectors")
    return data


def cmd_concordance(args: argparse.Namespace) -> int:
    readings = _load_readings(Path(args.readings))
    if len(readings) < 2:
        print("error: need >= 2 operators to score concordance", file=sys.stderr)
        return 2
    scores = vector_concordance(readings)
    verdict = apply_exclusion_rule(scores, multiple=args.multiple)
    print("Pre-flight operator concordance (leave-one-out, cosine)")
    print(f"  rule (fixed ex ante): {verdict['rule']}")
    for op in sorted(scores):
        mark = (
            "EXCLUDED" if any(e["unit"] == op for e in verdict["excluded"]) else "kept"
        )
        print(f"  {op:<40} {scores[op]:.4f}  {mark}")
    if args.out:
        Path(args.out).write_text(json.dumps(verdict, indent=2) + "\n")
        print(f"  verdict written: {args.out}")
    if verdict["excluded"]:
        for e in verdict["excluded"]:
            print(
                f"EXCLUDE {e['unit']}: score {e['score']:.4f} > "
                f"{args.multiple} x median(others) {e['median_others']:.4f} — "
                f"retain as exploratory observer only (no floor, no pooled vector)"
            )
        return 1
    print("all operators concordant; no exclusions")
    return 0


# ---------------------------------------------------------------------------
# version-floor subcommand
# ---------------------------------------------------------------------------


def _atlas_operator_ids(path: Path) -> set[str]:
    """Collect every operator model-version string an atlas declares."""
    import yaml

    atlas = yaml.safe_load(path.read_text())
    ids: set[str] = set()
    for cohort in (atlas.get("cohorts") or {}).values():
        if not isinstance(cohort, dict):
            continue
        for key in (
            "renderer_operator_id",
            "extractor_operator_id",
            "valence_extractor_operator_id",
        ):
            val = cohort.get(key)
            if isinstance(val, str) and val:
                ids.add(val)
    return ids


def cmd_version_floor(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.manifest).read_text())
    measured = set(manifest["measured_under"]["renderers"]) | set(
        manifest["measured_under"]["extractors"]
    )
    configured: set[str] = set()
    if args.operators:
        configured |= {s.strip() for s in args.operators.split(",") if s.strip()}
    if args.atlas:
        configured |= _atlas_operator_ids(Path(args.atlas))
    if not configured:
        print("error: pass --operators and/or --atlas", file=sys.stderr)
        return 2
    epoch = manifest["epoch"]
    print(
        f"Pre-run version check against epoch {epoch['id']} "
        f"(sealed panel read {epoch['date']}; source DOI {manifest['source']['doi']})"
    )
    stale = sorted(configured - measured)
    for op in sorted(configured):
        status = "measured at this epoch" if op in measured else "NOT measured"
        print(f"  {op:<40} {status}")
    if stale:
        print(STALE_LINE)
        print(
            "  unmeasured version(s): "
            + ", ".join(stale)
            + " — schedule the sealed-panel re-read (VE-2 procedure, "
            "prism_t code as-is) before epoch-stamping longitudinal claims."
        )
        return 1
    print(f"version floor fresh: every configured version measured at {epoch['id']}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_con = sub.add_parser("concordance", help="pre-flight operator concordance")
    p_con.add_argument("--readings", required=True, help="pilot readings JSON/JSONL")
    p_con.add_argument(
        "--multiple",
        type=float,
        default=RULE_MULTIPLE,
        help="exclusion multiple (fixed ex ante; default %(default)s)",
    )
    p_con.add_argument("--out", help="write the mechanical verdict JSON here")
    p_con.set_defaults(func=cmd_concordance)

    p_vf = sub.add_parser("version-floor", help="pre-run version check")
    p_vf.add_argument("--operators", help="comma-separated model-version strings")
    p_vf.add_argument("--atlas", help="atlas YAML to read operator ids from")
    p_vf.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="version-floor manifest (default: %(default)s)",
    )
    p_vf.set_defaults(func=cmd_version_floor)

    args = parser.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
