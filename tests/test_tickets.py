import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tickets import CATEGORIES, SEVERITIES, generate_tickets, split_tickets


def test_generate_tickets_is_deterministic():
    t1 = generate_tickets(n_per_combo=2, seed=1)
    t2 = generate_tickets(n_per_combo=2, seed=1)
    assert [t.text for t in t1] == [t.text for t in t2]


def test_generate_tickets_covers_every_combo():
    tickets = generate_tickets(n_per_combo=2, seed=1)
    combos = {(t.true_category, t.true_severity) for t in tickets}
    assert combos == {(c, s) for c in CATEGORIES for s in SEVERITIES}
    assert len(tickets) == len(CATEGORIES) * len(SEVERITIES) * 2


def test_split_is_deterministic_and_disjoint():
    tickets = generate_tickets(n_per_combo=3, seed=1)
    val1, test1 = split_tickets(tickets, seed=5, n_val=10, n_test=10)
    val2, test2 = split_tickets(tickets, seed=5, n_val=10, n_test=10)
    assert [t.ticket_id for t in val1] == [t.ticket_id for t in val2]
    val_ids = {t.ticket_id for t in val1}
    test_ids = {t.ticket_id for t in test1}
    assert val_ids.isdisjoint(test_ids)
    assert len(val1) == 10 and len(test1) == 10


def test_ticket_ids_are_unique():
    tickets = generate_tickets(n_per_combo=3, seed=1)
    ids = [t.ticket_id for t in tickets]
    assert len(ids) == len(set(ids))
