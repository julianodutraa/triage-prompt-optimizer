"""Generate the synthetic ticket dataset and write the validation and test
splits to fixtures/dataset.json. Deterministic, no LLM involved.

Run with: python3 scripts/build_dataset.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tickets import generate_tickets, split_tickets

TICKET_SEED = 20261011
SPLIT_SEED = 7
N_PER_COMBO = 3
N_VAL = 20
N_TEST = 30


def main():
    tickets = generate_tickets(n_per_combo=N_PER_COMBO, seed=TICKET_SEED)
    val, test = split_tickets(tickets, seed=SPLIT_SEED, n_val=N_VAL, n_test=N_TEST)

    out = {
        "ticket_seed": TICKET_SEED,
        "split_seed": SPLIT_SEED,
        "validation": [dataclasses.asdict(t) for t in val],
        "test": [dataclasses.asdict(t) for t in test],
    }
    out_path = Path(__file__).resolve().parents[1] / "fixtures" / "dataset.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {len(val)} validation + {len(test)} test tickets to {out_path}")


if __name__ == "__main__":
    main()
