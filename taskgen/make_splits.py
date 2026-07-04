#!/usr/bin/env python3
"""Generate the three frozen task splits (run once, outputs committed).

  train-pool : T1-T3, catalog A, task-seed 0,    registers 0-2 (held-out excluded)
  eval       : all tiers, catalog A, task-seed 1000, all registers
               (T1-T3: 50 each per amendment A3; T4-T6: 20 each)
  eval-ood   : all tiers, catalog B, task-seed 2000, all registers (~50 total)

Guardrails:
- disjoint task seeds (0 / 1000 / 2000) => disjoint generation inputs
- content-level dedup: any eval task whose underlying spec collides with a
  train-pool task is dropped (we over-generate, then trim to target)
- register 3 (contextual) never appears in train-pool: language-generalization probe
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate import generate_tasks  # noqa: E402
from phrasing import ALL_REGISTERS, TRAIN_REGISTERS  # noqa: E402

ROOT = HERE.parent
CATALOG_A = str(ROOT / "storefront" / "seed" / "catalog-seed-A.json")
CATALOG_B = str(ROOT / "storefront" / "seed" / "catalog-seed-B.json")
OUT_DIR = HERE / "splits"

TRAIN_SEED, EVAL_SEED, OOD_SEED = 0, 1000, 2000

# per-tier target counts
TRAIN_TARGETS = {"t1": 84, "t2": 83, "t3": 83}          # ~250 total
EVAL_TARGETS = {"t1": 50, "t2": 50, "t3": 50, "t4": 20, "t5": 20, "t6": 20}  # A3
OOD_TARGETS = {"t1": 9, "t2": 9, "t3": 8, "t4": 8, "t5": 8, "t6": 8}         # ~50


def content_key(task):
    """Spec-level identity, ignoring surface phrasing (register) and ids.
    Two tasks with the same underlying spec+answer are duplicates even if
    worded differently."""
    spec = dict(task["info"]["verify_spec"])
    spec.pop("register", None)
    return json.dumps(
        {"tier": task["info"]["tier"], "spec": spec, "answer": task["answer"]},
        sort_keys=True,
    )


def take(tasks, tier_targets, forbidden_keys):
    """Deterministically keep the first N per tier whose content key is unseen."""
    out, seen = [], set(forbidden_keys)
    counts = {t: 0 for t in tier_targets}
    for t in tasks:  # generation order is deterministic
        tier = t["info"]["tier"]
        if tier not in tier_targets or counts[tier] >= tier_targets[tier]:
            continue
        key = content_key(t)
        if key in seen:
            continue
        seen.add(key)
        counts[tier] += 1
        out.append(t)
    for tier, want in tier_targets.items():
        assert counts[tier] == want, f"only {counts[tier]}/{want} for {tier}"
    return out


def write(path, tasks):
    with open(path, "w") as f:
        for t in tasks:
            f.write(json.dumps(t, sort_keys=True) + "\n")
    print(f"{path.name}: {len(tasks)} tasks")


def main():
    OUT_DIR.mkdir(exist_ok=True)

    # train-pool: over-generate, self-dedup, trim
    raw_train = generate_tasks(CATALOG_A, TRAIN_SEED, ["t1", "t2", "t3"],
                               n=110, registers=TRAIN_REGISTERS)
    train = take(raw_train, TRAIN_TARGETS, forbidden_keys=set())
    train_keys = {content_key(t) for t in train}

    # eval: over-generate, drop anything colliding with train-pool, trim
    raw_eval = generate_tasks(CATALOG_A, EVAL_SEED,
                              ["t1", "t2", "t3", "t4", "t5", "t6"],
                              n=80, registers=ALL_REGISTERS)
    ev = take(raw_eval, EVAL_TARGETS, forbidden_keys=train_keys)
    eval_keys = {content_key(t) for t in ev}

    # eval-ood: catalog B — different products, collisions impossible, but
    # guard anyway
    raw_ood = generate_tasks(CATALOG_B, OOD_SEED,
                             ["t1", "t2", "t3", "t4", "t5", "t6"],
                             n=30, registers=ALL_REGISTERS)
    ood = take(raw_ood, OOD_TARGETS, forbidden_keys=train_keys | eval_keys)

    write(OUT_DIR / "train-pool.jsonl", train)
    write(OUT_DIR / "eval.jsonl", ev)
    write(OUT_DIR / "eval-ood.jsonl", ood)


if __name__ == "__main__":
    main()
