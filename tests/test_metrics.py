import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.metrics import Prediction, error_summary_for_prompt, score
from src.tickets import Ticket


def _ticket(tid, cat, sev, text="placeholder text"):
    return Ticket(ticket_id=tid, text=text, true_category=cat, true_severity=sev)


def test_score_perfect_predictions():
    tickets = [_ticket("A", "db_capacity", "P1"), _ticket("B", "pipeline_failure", "P3")]
    preds = [Prediction("A", "db_capacity", "P1"), Prediction("B", "pipeline_failure", "P3")]
    report = score(tickets, preds)
    assert report.exact_match_accuracy == 1.0
    assert report.category_accuracy == 1.0
    assert report.severity_accuracy == 1.0
    assert report.errors == []


def test_score_distinguishes_category_and_severity_errors():
    tickets = [
        _ticket("A", "db_capacity", "P1"),
        _ticket("B", "pipeline_failure", "P3"),
        _ticket("C", "security_alert", "P2"),
    ]
    preds = [
        Prediction("A", "db_capacity", "P2"),  # severity error only
        Prediction("B", "network_connectivity", "P3"),  # category error only
        Prediction("C", "security_alert", "P2"),  # correct
    ]
    report = score(tickets, preds)
    assert report.exact_match_accuracy == pytest.approx(1 / 3)
    assert report.category_accuracy == pytest.approx(2 / 3)
    assert report.severity_accuracy == pytest.approx(2 / 3)
    assert len(report.errors) == 2


def test_score_raises_on_missing_prediction():
    tickets = [_ticket("A", "db_capacity", "P1"), _ticket("B", "pipeline_failure", "P3")]
    preds = [Prediction("A", "db_capacity", "P1")]
    with pytest.raises(ValueError):
        score(tickets, preds)


def test_confusion_matrix_counts():
    tickets = [_ticket("A", "db_capacity", "P1"), _ticket("B", "db_capacity", "P2")]
    preds = [Prediction("A", "db_capacity", "P1"), Prediction("B", "pipeline_failure", "P2")]
    report = score(tickets, preds)
    assert report.confusion_category["db_capacity"]["db_capacity"] == 1
    assert report.confusion_category["db_capacity"]["pipeline_failure"] == 1


def test_error_summary_includes_text_and_labels():
    tickets = [_ticket("A", "db_capacity", "P1", text="storage is nearly full")]
    preds = [Prediction("A", "db_capacity", "P2")]
    report = score(tickets, preds)
    tickets_by_id = {"A": tickets[0]}
    summary = error_summary_for_prompt(report, tickets_by_id)
    assert "storage is nearly full" in summary
    assert "P1" in summary and "P2" in summary
