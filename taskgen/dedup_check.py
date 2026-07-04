#!/usr/bin/env python3
"""Dedup audit across the three frozen splits (M0 step 4b acceptance).

Asserts that no task_id, no normalized question, and no content key (tier +
verify_spec-without-register + answer) appears in more than one split.
Prints an overlap report; exits nonzero on any overlap.
"""

import json
import re
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from make_splits import content_key  # noqa: E402

SPLITS = ["train-pool", "eval", "eval-ood"]


def norm_question(q):
    return re.sub(r"\s+", " ", q.strip().lower())


def load(name):
    with open(HERE / "splits" / f"{name}.jsonl") as f:
        return [json.loads(line) for line in f]


def main():
    data = {s: load(s) for s in SPLITS}
    total_overlaps = 0

    for a, b in combinations(SPLITS, 2):
        for label, keyfn in [
            ("task_id", lambda t: t["task_id"]),
            ("question", lambda t: norm_question(t["question"])),
            ("content", content_key),
        ]:
            ka = {keyfn(t) for t in data[a]}
            kb = {keyfn(t) for t in data[b]}
            n = len(ka & kb)
            total_overlaps += n
            print(f"{a} vs {b} [{label}] overlap: {n}")

    # register guardrail: held-out register never in train-pool
    train_regs = {t["info"]["verify_spec"]["register"] for t in data["train-pool"]}
    print(f"train-pool registers used: {sorted(train_regs)}")
    assert 3 not in train_regs, "held-out register leaked into train-pool"

    sizes = {s: len(data[s]) for s in SPLITS}
    print(f"sizes: {sizes}")
    print(f"overlap: {total_overlaps}")
    if total_overlaps:
        sys.exit(1)


if __name__ == "__main__":
    main()
