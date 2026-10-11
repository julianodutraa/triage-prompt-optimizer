"""Scoring utilities for the prompt optimization loop.

All functions here are pure and deterministic: they take a set of ground
truth tickets and a set of predictions (however those predictions were
produced) and compute accuracy, per-field accuracy, and a confusion
matrix. None of this depends on an LLM; it is the analysis layer that
runs, in the test suite and in scripts/run_demo.py, against whatever
predictions are cached in fixtures/.
"""

from __future__ import annotations

import dataclasses
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from src.tickets import Ticket


@dataclasses.dataclass
class Prediction:
    ticket_id: str
    predicted_category: str
    predicted_severity: str


@dataclasses.dataclass
class ScoreReport:
    n: int
    exact_match_accuracy: float
    category_accuracy: float
    severity_accuracy: float
    errors: List[Tuple[str, str, str, str, str]]  # ticket_id, true_cat, pred_cat, true_sev, pred_sev
    confusion_category: Dict[str, Dict[str, int]]


def score(tickets: List[Ticket], predictions: List[Prediction]) -> ScoreReport:
    pred_by_id = {p.ticket_id: p for p in predictions}
    missing = [t.ticket_id for t in tickets if t.ticket_id not in pred_by_id]
    if missing:
        raise ValueError(f"missing predictions for ticket ids: {missing}")

    n = len(tickets)
    exact = 0
    cat_correct = 0
    sev_correct = 0
    errors = []
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for t in tickets:
        p = pred_by_id[t.ticket_id]
        confusion[t.true_category][p.predicted_category] += 1
        cat_ok = p.predicted_category == t.true_category
        sev_ok = p.predicted_severity == t.true_severity
        if cat_ok:
            cat_correct += 1
        if sev_ok:
            sev_correct += 1
        if cat_ok and sev_ok:
            exact += 1
        else:
            errors.append((t.ticket_id, t.true_category, p.predicted_category, t.true_severity, p.predicted_severity))

    return ScoreReport(
        n=n,
        exact_match_accuracy=exact / n,
        category_accuracy=cat_correct / n,
        severity_accuracy=sev_correct / n,
        errors=errors,
        confusion_category={k: dict(v) for k, v in confusion.items()},
    )


def error_summary_for_prompt(report: ScoreReport, tickets_by_id: Dict[str, Ticket], max_examples: int = 8) -> str:
    """Render a compact, deterministic text summary of a ScoreReport's
    errors, suitable for feeding back into a prompt-optimizer step as
    "here is what went wrong."
    """
    lines = [f"{len(report.errors)} of {report.n} tickets misclassified:"]
    for ticket_id, true_cat, pred_cat, true_sev, pred_sev in report.errors[:max_examples]:
        text = tickets_by_id[ticket_id].text
        lines.append(
            f"- ticket {ticket_id}: true=({true_cat}, {true_sev}) predicted=({pred_cat}, {pred_sev}) text: \"{text}\""
        )
    return "\n".join(lines)
