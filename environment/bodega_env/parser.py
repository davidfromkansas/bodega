"""ANSWER: extraction + normalization (spec Part III §5, amendment A5).

Contract:
- the final assistant message must end with a line `ANSWER: <...>`
- the LAST `ANSWER:` line in the text wins (models sometimes restate)
- normalization: strip '$', case-insensitive, whitespace-collapsed, numeric
  equality ignores trailing zeros (89.99 == $89.99 == 89.990)
- `name | value` answers split on the LAST ' | ' (A5: names never contain '|',
  enforced at catalog generation)
"""

import re

ANSWER_RE = re.compile(r"^\s*ANSWER:\s*(.+?)\s*$", re.MULTILINE)


def extract_answer(text: str):
    """Return the payload of the last ANSWER: line, or None."""
    if not text:
        return None
    matches = ANSWER_RE.findall(text)
    if not matches:
        return None
    ans = matches[-1].strip()
    # an echo of the question's format hint is not an answer
    if ans.startswith("<") and ans.endswith(">"):
        return None
    return ans


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def norm_number(s: str):
    """'$89.99' -> 89.99 ; '89.990' -> 89.99 ; returns None if not numeric."""
    cleaned = s.strip().lstrip("$").replace(",", "").strip()
    try:
        return round(float(cleaned), 6)
    except ValueError:
        return None


def split_name_value(s: str):
    """Split 'Product Name | 89.99' on the LAST pipe. Returns (name, value_str)
    or None if there is no pipe."""
    if "|" not in s:
        return None
    name, _, value = s.rpartition("|")
    return name.strip(), value.strip()


def answers_equal(got: str, expected: str, fields) -> bool:
    """Compare a raw extracted answer against the task's expected answer,
    per the task's verify_spec fields."""
    if got is None:
        return False
    fields = list(fields)

    if fields == ["price"] or fields == ["value"]:
        # numeric or yes/no single-field answers
        exp_num = norm_number(expected)
        if exp_num is not None:
            got_num = norm_number(got)
            return got_num is not None and got_num == exp_num
        return norm_text(got) == norm_text(expected)

    if fields in (["name", "price"], ["name", "value"]):
        exp_parts = split_name_value(expected)
        got_parts = split_name_value(got)
        if exp_parts is None or got_parts is None:
            return False
        exp_name, exp_val = exp_parts
        got_name, got_val = got_parts
        if norm_text(got_name) != norm_text(exp_name):
            return False
        exp_num = norm_number(exp_val)
        if exp_num is not None:
            got_num = norm_number(got_val)
            return got_num is not None and got_num == exp_num
        return norm_text(got_val) == norm_text(exp_val)

    raise ValueError(f"unknown fields spec: {fields}")
