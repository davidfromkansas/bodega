#!/usr/bin/env python3
"""Task generator CLI. Pure function of its inputs: same args => byte-identical JSONL.

Usage:
  python generate.py --catalog ../storefront/seed/catalog-seed-A.json \
      --task-seed 0 --tier all --n 50 --out /tmp/sample.jsonl
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import load_catalog  # noqa: E402
from phrasing import ALL_REGISTERS  # noqa: E402
from templates import TEMPLATES  # noqa: E402

TIER_MAX_TURNS = {"t1": 5, "t2": 8, "t3": 8, "t4": 10, "t5": 14, "t6": 16}


def generate_tasks(catalog_path, task_seed, tiers, n, difficulty_range=None,
                   registers=None):
    catalog = load_catalog(catalog_path)
    catalog_seed = catalog["catalog_seed"]
    registers = registers or ALL_REGISTERS
    all_tasks = []
    for tier in tiers:
        # independent RNG per tier so tiers don't perturb each other
        rng = random.Random(f"bodega-task-{catalog_seed}-{task_seed}-{tier}")
        tasks = TEMPLATES[tier].gen(catalog, rng, n, catalog_seed, task_seed,
                                    registers=registers)
        for t in tasks:
            t["info"]["max_turns"] = TIER_MAX_TURNS[tier]
        if difficulty_range:
            lo, hi = difficulty_range
            tasks = [t for t in tasks if lo <= t["info"]["difficulty"] <= hi]
        all_tasks.extend(tasks)
    return all_tasks


def parse_tiers(s):
    if s == "all":
        return ["t1", "t2", "t3", "t4", "t5", "t6"]
    tiers = [t.strip() for t in s.split(",")]
    for t in tiers:
        if t not in TEMPLATES:
            raise SystemExit(f"unknown tier: {t}")
    return tiers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--task-seed", type=int, required=True)
    ap.add_argument("--tier", default="all")
    ap.add_argument("--n", type=int, default=50, help="tasks per tier")
    ap.add_argument("--difficulty", default=None, help="lo,hi filter e.g. 0.2,0.6")
    ap.add_argument("--registers", default=None,
                    help="comma list of phrasing registers, e.g. 0,1,2 (default all)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    drange = None
    if args.difficulty:
        lo, hi = args.difficulty.split(",")
        drange = (float(lo), float(hi))

    regs = [int(r) for r in args.registers.split(",")] if args.registers else None
    tasks = generate_tasks(args.catalog, args.task_seed, parse_tiers(args.tier), args.n,
                           drange, registers=regs)
    with open(args.out, "w") as f:
        for t in tasks:
            f.write(json.dumps(t, sort_keys=True) + "\n")
    print(f"wrote {len(tasks)} tasks to {args.out}")


if __name__ == "__main__":
    main()
