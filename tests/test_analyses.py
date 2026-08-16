from __future__ import annotations

from src.analysis.analyses import EXPECTEDNESS_NOTE
from src.analysis.base import run_analyses


def _cell(result, **match):
    for row in result.table:
        if all(row.get(key) == value for key, value in match.items()):
            return row
    raise KeyError(match)


def test_case_counts_golden(real_cases):
    result = run_analyses(["case_counts"], real_cases)["case_counts"]
    assert result.facts["total_cases"] == 1024
    assert result.facts["serious_cases"] == 1023
    assert result.facts["non_serious_cases"] == 1
    assert result.facts["expedited_cases"] == 1023
    assert len(result.evidence["Serious"]) == 1023
    assert "1023" in result.numbers()
    assert "1024" in result.numbers()


def test_reactions_serious_golden(real_cases):
    result = run_analyses(["reactions"], real_cases)["reactions"]
    assert _cell(result, scope="Serious cases", reaction="Acute kidney injury")["cases"] == 80
    assert _cell(result, scope="Serious cases", reaction="Drug ineffective")["cases"] == 53
    assert _cell(result, scope="Serious cases", reaction="Hypotension")["cases"] == 46
    assert _cell(result, scope="Serious cases", reaction="Drug interaction")["cases"] == 43
    assert len(result.evidence["Serious cases: Acute kidney injury"]) == 80


def test_demographics_golden(real_cases):
    result = run_analyses(["demographics"], real_cases)["demographics"]
    assert result.facts["age_reported"] == 931
    assert result.facts["age_median"] == 73
    assert result.facts["age_mean"] == 70.6
    assert _cell(result, dimension="Country", group="eu")["cases"] == 342


def test_outcomes_golden(real_cases):
    result = run_analyses(["outcomes"], real_cases)["outcomes"]
    assert _cell(result, outcome="recovered/resolved")["reaction_records"] == 1280
    assert _cell(result, outcome="unknown")["reaction_records"] == 1033
    assert _cell(result, outcome="fatal")["reaction_records"] == 134


def test_seriousness_breakdown_golden(real_cases):
    result = run_analyses(["seriousness_breakdown"], real_cases)["seriousness_breakdown"]
    assert result.facts["death"] == 68
    assert result.facts["life_threatening"] == 105
    assert result.facts["hospitalization"] == 482
    assert result.facts["disabling"] == 44
    assert result.facts["congenital_anomaly"] == 7
    assert result.facts["other"] == 905


def test_alert_cases_golden(real_cases):
    result = run_analyses(["alert_cases"], real_cases)["alert_cases"]
    assert result.facts["alert_window_days"] == 15
    assert result.facts["expedited_cases"] == 1023
    assert "15" in result.numbers()


def test_alert_cases_states_expectedness_gap(real_cases):
    result = run_analyses(["alert_cases"], real_cases)["alert_cases"]
    assert EXPECTEDNESS_NOTE in result.notes


def test_history_of_actions_sentinel(real_cases):
    result = run_analyses(["history_of_actions"], real_cases)["history_of_actions"]
    assert result.table == []
    assert result.facts == {}
    assert result.notes
    assert "No history of actions" in result.notes[0]


def test_trends_totals(real_cases):
    result = run_analyses(["trends"], real_cases)["trends"]
    dated = sum(1 for value in real_cases.cases["receive_date"] if value is not None)
    assert sum(row["cases"] for row in result.table) == dated
    assert result.facts["months_covered"] == 13


def test_case_index_lists_all(real_cases):
    result = run_analyses(["case_index"], real_cases)["case_index"]
    assert result.facts["n_cases"] == 1024
    assert len(result.table) == 1024
