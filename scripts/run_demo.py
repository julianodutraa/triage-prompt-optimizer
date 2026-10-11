"""End-to-end, reproducible demo for the triage-prompt-optimizer project.

Running this script:

  1. Regenerates the synthetic ticket dataset (20 validation + 30 held-out
     test tickets) from a fixed seed.
  2. Loads the cached prompt-optimization trajectory (5 prompt variants
     across a seed round and 2 optimization rounds) and scores every
     variant against the validation set.
  3. Selects the best-scoring variant (ties broken by shorter prompt).
  4. Loads the cached held-out test evaluation and reports whether the
     selected "optimized" prompt actually generalizes better than the
     original seed prompt, which, honestly, it does not.

Run with: python3 scripts/run_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.optimizer import evaluate_rounds, held_out_comparison, load_trajectory, select_best
from src.tickets import Ticket, generate_tickets, split_tickets

TICKET_SEED = 20261011
SPLIT_SEED = 7
N_PER_COMBO = 3
N_VAL = 20
N_TEST = 30


def main():
    tickets = generate_tickets(n_per_combo=N_PER_COMBO, seed=TICKET_SEED)
    val, test = split_tickets(tickets, seed=SPLIT_SEED, n_val=N_VAL, n_test=N_TEST)

    print("=" * 78)
    print("TRIAGE PROMPT OPTIMIZER (reproducible demo)")
    print("=" * 78)
    print(f"\nDataset: {len(val)} validation tickets, {len(test)} held-out test tickets")

    trajectory_path = Path(__file__).resolve().parents[1] / "fixtures" / "optimization_trajectory.json"
    trajectory = load_trajectory(trajectory_path)

    results = evaluate_rounds(trajectory, val)

    print("\n--- Validation accuracy per round ---")
    for r in results:
        print(
            f"  round {r.round}  {r.label:<14s} exact_match={r.report.exact_match_accuracy:.2f}  "
            f"category={r.report.category_accuracy:.2f}  severity={r.report.severity_accuracy:.2f}  "
            f"errors={len(r.report.errors)}  prompt_len={len(r.prompt)}"
        )

    best = select_best(results)
    print(f"\nSelected as best: '{best.label}' (validation exact_match={best.report.exact_match_accuracy:.2f}, "
          f"prompt length {len(best.prompt)} chars)")

    comparison = held_out_comparison(trajectory, test)
    seed_report = comparison["seed"]
    best_report = comparison["selected_best"]

    print("\n--- Held-out test accuracy (never seen during optimization) ---")
    print(f"  seed prompt (never optimized): exact_match={seed_report.exact_match_accuracy:.3f}  "
          f"({len(test) - len(seed_report.errors)}/{len(test)})")
    print(f"  selected best ('{best.label}'):          exact_match={best_report.exact_match_accuracy:.3f}  "
          f"({len(test) - len(best_report.errors)}/{len(test)})")

    gap = best.report.exact_match_accuracy - best_report.exact_match_accuracy
    delta_vs_seed = best_report.exact_match_accuracy - seed_report.exact_match_accuracy
    print(f"\n  overfitting gap for selected best (validation minus test): {gap:+.3f}")
    print(f"  selected best minus seed, on test only:                      {delta_vs_seed:+.3f}")
    if delta_vs_seed < 0:
        print("  CONCLUSION: 2 rounds of automatic prompt optimization produced a prompt that")
        print("  reached perfect validation accuracy but generalizes WORSE than the original,")
        print("  un-optimized seed prompt on held-out data. See ARTICLE.md for why.")

    if best_report.errors:
        print("\n  remaining test error(s) for the selected best prompt:")
        for ticket_id, true_cat, pred_cat, true_sev, pred_sev in best_report.errors:
            print(f"    {ticket_id}: true=({true_cat}, {true_sev}) predicted=({pred_cat}, {pred_sev})")


if __name__ == "__main__":
    main()
