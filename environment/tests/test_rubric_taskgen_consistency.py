"""Integration guarantee: the rubric accepts taskgen's own ground truth.

For every T1-T3 task in all three frozen splits, a completion that ends with
`ANSWER: <the task's answer>` must score terminal 1.0. Any failure means the
generator and the grader disagree about format — a bug that would silently
punish correct agents."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "environment"))

from bodega_env.rubric import score_answer_match  # noqa: E402

SPLITS = ROOT / "taskgen" / "splits"


def load_all_answer_tasks():
    tasks = []
    for split in ("train-pool", "eval", "test", "eval-ood"):
        with open(SPLITS / f"{split}.jsonl") as f:
            for line in f:
                t = json.loads(line)
                if t["info"]["tier"] in ("t1", "t2", "t3"):
                    tasks.append(t)
    return tasks


def test_ground_truth_scores_full_marks():
    tasks = load_all_answer_tasks()
    assert len(tasks) >= 400  # 250 train + 150 (eval public + test held-out) + ood t1-t3
    for t in tasks:
        completion = f"I looked it up on the site.\nANSWER: {t['answer']}"
        fields = t["info"]["verify_spec"]["fields"]
        score = score_answer_match(completion, t["answer"], fields)
        assert score == 1.0, f"{t['task_id']}: rubric rejects its own ground truth ({t['answer']!r})"


def test_ground_truth_with_dollar_prefix_still_passes():
    # models often add '$' to prices; normalization must absorb it
    tasks = [t for t in load_all_answer_tasks() if "price" in t["info"]["verify_spec"]["fields"]]
    assert tasks
    for t in tasks[:50]:
        if "|" in t["answer"]:
            name, _, price = t["answer"].rpartition("|")
            completion = f"ANSWER: {name.strip()} | ${price.strip()}"
        else:
            completion = f"ANSWER: ${t['answer']}"
        fields = t["info"]["verify_spec"]["fields"]
        assert score_answer_match(completion, t["answer"], fields) == 1.0, t["task_id"]
