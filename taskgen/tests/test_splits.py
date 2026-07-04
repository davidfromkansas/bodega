"""M0 step 4b acceptance: frozen splits are reproducible, disjoint, and sized
per amendment A3. dedup_check.py must print 'overlap: 0'."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

TASKGEN = Path(__file__).resolve().parent.parent
SPLITS = TASKGEN / "splits"


def load(name):
    with open(SPLITS / f"{name}.jsonl") as f:
        return [json.loads(line) for line in f]


def test_dedup_check_passes():
    r = subprocess.run(
        [sys.executable, str(TASKGEN / "dedup_check.py")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "overlap: 0" in r.stdout


def test_split_sizes_per_a3():
    train = Counter(t["info"]["tier"] for t in load("train-pool"))
    ev = Counter(t["info"]["tier"] for t in load("eval"))
    ood = Counter(t["info"]["tier"] for t in load("eval-ood"))
    assert sum(train.values()) == 250 and set(train) == {"t1", "t2", "t3"}
    # A3: claim-bearing tiers get >=50 eval tasks each
    for tier in ("t1", "t2", "t3"):
        assert ev[tier] >= 50, (tier, ev[tier])
    for tier in ("t4", "t5", "t6"):
        assert ev[tier] == 20
    assert sum(ood.values()) == 50


def test_ood_uses_catalog_b():
    for t in load("eval-ood"):
        assert "-B" in t["task_id"].split("-")[1] or t["task_id"].split("-")[1].startswith("B"), t["task_id"]


def test_regeneration_is_byte_identical(tmp_path):
    """Rerunning make_splits must reproduce the frozen files exactly."""
    frozen = {
        name: hashlib.sha256((SPLITS / f"{name}.jsonl").read_bytes()).hexdigest()
        for name in ("train-pool", "eval", "eval-ood")
    }
    r = subprocess.run(
        [sys.executable, str(TASKGEN / "make_splits.py")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    for name, digest in frozen.items():
        now = hashlib.sha256((SPLITS / f"{name}.jsonl").read_bytes()).hexdigest()
        assert now == digest, f"{name} changed on regeneration"
