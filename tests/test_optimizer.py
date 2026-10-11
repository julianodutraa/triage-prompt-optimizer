import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.optimizer import evaluate_rounds, held_out_comparison, load_trajectory, select_best
from src.tickets import generate_tickets, split_tickets

TICKET_SEED = 20261011
SPLIT_SEED = 7
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "optimization_trajectory.json"


@pytest.fixture(scope="module")
def dataset():
    tickets = generate_tickets(n_per_combo=3, seed=TICKET_SEED)
    val, test = split_tickets(tickets, seed=SPLIT_SEED, n_val=20, n_test=30)
    return val, test


@pytest.fixture(scope="module")
def trajectory():
    return load_trajectory(FIXTURE_PATH)


def test_trajectory_loads_five_rounds(trajectory):
    assert len(trajectory["rounds"]) == 5
    labels = [r["label"] for r in trajectory["rounds"]]
    assert labels == ["seed", "candidate_1", "candidate_2", "candidate_3", "candidate_4"]


def test_seed_prompt_scores_eighty_five_percent_on_validation(trajectory, dataset):
    val, _ = dataset
    results = evaluate_rounds(trajectory, val)
    seed_result = next(r for r in results if r.label == "seed")
    assert seed_result.report.exact_match_accuracy == pytest.approx(0.85)


def test_round_one_candidates_regress_below_seed(trajectory, dataset):
    """The central honest surprise in round 1: both candidates, each
    explicitly designed to fix the seed's 3 known errors, score LOWER
    than the seed on the full validation set, because each introduced
    new errors elsewhere.
    """
    val, _ = dataset
    results = evaluate_rounds(trajectory, val)
    seed_acc = next(r for r in results if r.label == "seed").report.exact_match_accuracy
    for label in ("candidate_1", "candidate_2"):
        acc = next(r for r in results if r.label == label).report.exact_match_accuracy
        assert acc < seed_acc


def test_round_two_candidates_reach_perfect_validation_accuracy(trajectory, dataset):
    val, _ = dataset
    results = evaluate_rounds(trajectory, val)
    for label in ("candidate_3", "candidate_4"):
        acc = next(r for r in results if r.label == label).report.exact_match_accuracy
        assert acc == 1.0


def test_select_best_picks_shorter_prompt_on_tie(trajectory, dataset):
    val, _ = dataset
    results = evaluate_rounds(trajectory, val)
    best = select_best(results)
    assert best.label == "candidate_4"
    assert best.report.exact_match_accuracy == 1.0


def test_selected_best_generalizes_worse_than_seed_on_held_out_test(trajectory, dataset):
    """The project's central finding: perfect validation accuracy after
    optimization does not translate into better held-out performance.
    This is checked, not assumed: if the cached test predictions ever
    changed, this test would catch a regression in the claim.
    """
    _, test = dataset
    comparison = held_out_comparison(trajectory, test)
    seed_acc = comparison["seed"].exact_match_accuracy
    best_acc = comparison["selected_best"].exact_match_accuracy
    assert seed_acc == 1.0
    assert best_acc < seed_acc
    assert best_acc == pytest.approx(29 / 30)


def test_no_dash_punctuation_in_any_cached_prompt(trajectory):
    """Every cached prompt variant must satisfy the project's no em dash,
    no en dash, no spaced-hyphen style rule, since these prompts are
    quoted verbatim in README.md and ARTICLE.md.
    """
    import re

    for r in trajectory["rounds"]:
        prompt = r["prompt"]
        assert "—" not in prompt, r["label"]
        assert "–" not in prompt, r["label"]
        assert not re.search(r"\S \- \S", prompt), r["label"]
