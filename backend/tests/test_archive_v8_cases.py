"""Check the synthetic evaluation material before any paid requests."""
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[2] / "scripts" / "archive_v8_cases.py"
spec = importlib.util.spec_from_file_location("archive_v8_cases", path)
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


@pytest.mark.parametrize("case", cases.CASES, ids=lambda c: c["id"])
def test_fictional_rounds_have_explicit_correctly_shaped_roles(case):
    assert case["steps"] and case["expect"]
    for rows in case["steps"]:
        assert isinstance(rows, list) and len(rows) >= 2
        assert {r for r, _ in rows} == {"self", "other"}
        assert sum(len(t) for _, t in rows) <= 40000


def test_correction_and_completion_stay_with_the_original_speaker():
    by_id = {c["id"]: c for c in cases.CASES}
    assert by_id["contradictory_dates"]["steps"][1][0][0] == "other"
    assert by_id["accepted_then_completed"]["steps"][1][0][0] == "other"
