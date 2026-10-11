"""Load and analyze a cached prompt-optimization trajectory.

This module does not call an LLM. The trajectory it analyzes (every
prompt variant tried, and every prediction made under it) was produced
once, by a Claude subagent, and cached in
fixtures/optimization_trajectory.json with a provenance note describing
exactly how (see that file's "provenance" field). This mirrors the
pattern used for the brief faithfulness fixture in sibling projects: the
LLM step is real and auditable, but not re-run at test or demo time, so
the numbers below are fully reproducible without any API dependency.

The selection rule for "the optimized prompt" is: highest validation
exact-match accuracy across every round, ties broken by shorter prompt
character length (a simple Occam's razor tie-break, chosen because
nothing in the validation accuracy itself distinguishes equally-scoring
candidates).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Dict, List

from src.metrics import Prediction, ScoreReport, score
from src.tickets import Ticket


@dataclasses.dataclass
class RoundResult:
    round: int
    label: str
    prompt: str
    parent: str
    report: ScoreReport


def _to_predictions(raw: List[dict]) -> List[Prediction]:
    return [Prediction(p["ticket_id"], p["predicted_category"], p["predicted_severity"]) for p in raw]


def load_trajectory(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_rounds(trajectory: dict, val_tickets: List[Ticket]) -> List[RoundResult]:
    results = []
    for r in trajectory["rounds"]:
        preds = _to_predictions(r["predictions"])
        report = score(val_tickets, preds)
        results.append(
            RoundResult(
                round=r["round"],
                label=r["label"],
                prompt=r["prompt"],
                parent=r.get("parent", ""),
                report=report,
            )
        )
    return results


def select_best(results: List[RoundResult]) -> RoundResult:
    """Highest validation accuracy; ties broken by shorter prompt."""
    return max(results, key=lambda r: (r.report.exact_match_accuracy, -len(r.prompt)))


def held_out_comparison(trajectory: dict, test_tickets: List[Ticket]) -> Dict[str, ScoreReport]:
    seed_preds = _to_predictions(trajectory["held_out_test"]["seed_predictions"])
    best_preds = _to_predictions(trajectory["held_out_test"]["selected_best_predictions"])
    return {
        "seed": score(test_tickets, seed_preds),
        "selected_best": score(test_tickets, best_preds),
    }
