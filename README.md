# Triage Prompt Optimizer

An automatic prompt optimization loop for an LLM based on-call incident
triage classifier, with an honest, measured answer to the question every
team doing this in production eventually has to ask: does a prompt that
got better on your validation set actually get better in production, or
did you just teach it your validation set.

## Executive summary

Every data platform team that puts an LLM in front of its on-call queue
ends up doing the same thing: write a prompt, look at a few misclassified
tickets, tweak the prompt to fix them, and repeat. It feels like progress
because the numbers on the sample you are looking at keep going up. This
project builds the smallest honest version of that loop, automates it so
the human bias of "I'll just fix what I'm looking at" is made explicit and
measurable, and then checks the one thing that loop almost never checks on
its own: whether the gains hold up on tickets nobody tuned against.

They did not. In this project's run, two rounds of automated prompt
refinement took a plain, undecorated seed prompt from 85 percent accuracy
up to a perfect 100 percent on a 20 ticket validation set, by adding an
explicit severity rubric and category disambiguation rules. On a 30 ticket
held out test set that was never used to pick a single word of either
prompt, the original, un-optimized seed prompt scored 100 percent, and the
"optimized" prompt that had just reached a perfect validation score scored
96.7 percent, a full 3.3 points worse than the prompt it was supposed to
improve on. The business implication is direct: a team that ships a prompt
the moment its validation metric looks good, without a held out check, can
easily ship a regression while celebrating an improvement. The rest of
this document is the specific, inspectable reason that happened, because
the reason is more useful than the headline number.

## What it does, concretely

1. Generates a synthetic, deterministic dataset of 60 on-call incident
   ticket texts across 5 categories (database capacity, pipeline failure,
   network connectivity, deployment regression, security alert) and 4
   severities (P1 through P4), split into 20 validation and 30 held out
   test tickets, with ground truth baked into which template produced
   each ticket.
2. Scores a seed prompt (a short, generic triage instruction with no
   severity rubric) on the validation set, and records every error.
3. Runs 2 rounds of optimization. In each round, the current error list is
   handed to an LLM acting as the "optimizer," which proposes 2 new
   candidate prompts intended to fix those errors, and each candidate is
   then independently scored on the same validation set.
4. Selects the best scoring prompt across every round and every candidate
   (ties broken by shorter prompt length), then evaluates both that
   selected prompt and the original seed prompt on the 30 ticket held out
   test set, which neither prompt's authoring process ever saw.
5. Reports the full accuracy trajectory, the specific errors at every
   step, and the generalization gap, honestly, including the result that
   does not flatter the method.

## Architecture

```
synthetic ticket generator (60 tickets, 5 categories x 4 severities)
        |
        +--> validation split (20 tickets)
        |
        +--> held out test split (30 tickets, untouched until the end)
        |
        v
round 0: seed prompt  -->  score on validation  -->  error list
        |
        v
round 1: optimizer proposes 2 candidates from the error list
         -->  score each candidate on validation  -->  new error lists
        |
        v
round 2: optimizer proposes 2 more candidates from the FULL trajectory
         (seed + both round 1 candidates, with their scores and errors)
         -->  score each candidate on validation
        |
        v
select best validation scorer across all 5 variants
        |
        v
final: evaluate selected best AND the original seed on the held out test set
```

## Method

### The optimization loop

This follows the same shape as Automatic Prompt Engineer, APE (Zhou et
al., 2022) and Optimization by PROmpting, OPRO (Yang et al., 2023): an LLM
is given the current best instruction, or instructions, along with
concrete evidence of where it failed, and asked to propose improved
instructions. OPRO in particular feeds the optimizer a trajectory of
multiple past (instruction, score) pairs rather than a single one, which
this project's round 2 step does directly: the round 2 optimizer call
receives the seed prompt and both round 1 candidates, each with its exact
validation accuracy and its exact error list, not just the single most
recent attempt.

### Why round 1 made things worse, specifically

The seed prompt's only 3 validation errors were all severity
underestimates in the pipeline_failure category (predicting P2 instead of
P1, P3 instead of P2, and so on). Both round 1 candidates added an
explicit severity rubric that fixed exactly that pattern. In doing so, the
rubric also had to describe the categories in more detail than the seed
prompt did, and that description is where the regression came from: the
new network_connectivity category description explicitly mentioned
"certificate and TLS issues" as an example, which now competed with
security_alert's "suspicious credentials" framing for the exact two
tickets in the validation set that describe an expired certificate. The
seed prompt, which gave the model no category guidance at all beyond a
bare list of names, had gotten both of those right by relying on its own
unguided judgment. The more detailed, more carefully reasoned prompt gave
it a specific, locally sensible reason to get them wrong. This is not a
one off coding bug, it is the generic risk of writing detailed rules from
a small number of observed failures: every rule fixes what it was written
for and can break something the rule's author was not looking at.

### Why round 2 reaching 100 percent on validation was not actually victory

Round 2 was given the full trajectory, including the certificate
regression, and explicitly instructed to fix it without breaking anything
else. It worked, in the narrow sense that both round 2 candidates reached
a perfect validation score. But perfect accuracy on 20 fixed tickets, by
round 2, is close to inevitable: by that point the optimizer has
effectively seen the specific failure mode of every validation ticket that
was ever going to fail under a reasonable rubric, across two rounds, and
can special case its way to zero errors on exactly that set. The held out
test set is where that stops working. The selected prompt's capacity
severity tiers ended up with a gap: P1 was defined as 95 percent or more
capacity with active write failures, P3 was defined as 75 to 90 percent
with no failure, and there was no explicit P2 tier for capacity at all,
because no validation ticket ever needed one. The held out test set
contains exactly that gap: a ticket reporting tablespace usage crossing 90
percent with a 48 hour projection to fill, which is a real, true P2
(an active trajectory toward an outage, not yet an outage, not just
elevated usage), but falls through the rubric's unintentional gap into
P3. That single ticket is the entire 3.3 point difference between the
optimized prompt and the plain seed prompt on the test set.

### A known limitation of this project's measurement setup

When two candidate prompts are evaluated within the same batched call to
the optimizing/classifying LLM, their classification runs are not
perfectly independent in the way two separate production API calls would
be: the model has a shared context across both runs within that one call,
even when explicitly instructed to treat them independently. This project
treats that as an accepted, documented approximation rather than hiding
it: it is cheaper and faster than issuing dozens of fully isolated API
calls, and the specific finding this project reports (validation accuracy
climbing while test accuracy falls) is the kind of result that, if
anything, batched non-independence would make LESS likely to appear
(correlated runs tend to look more similar to each other, not more
divergent), so the result is unlikely to be an artifact of this
simplification. A production deployment of this loop should issue
separate, isolated calls per candidate per ticket.

## Honest results

All numbers below are reproduced exactly by running
`python3 scripts/run_demo.py`.

### Validation accuracy by round

| round | prompt | exact match | category | severity | errors |
|---|---|---|---|---|---|
| 0 | seed | 85.0% | 100.0% | 85.0% | 3 |
| 1 | candidate_1 | 80.0% | 90.0% | 90.0% | 4 |
| 1 | candidate_2 | 75.0% | 90.0% | 85.0% | 5 |
| 2 | candidate_3 | 100.0% | 100.0% | 100.0% | 0 |
| 2 | candidate_4 (selected) | 100.0% | 100.0% | 100.0% | 0 |

Both round 1 candidates score below the seed prompt, despite each being an
explicit, reasoned attempt to fix the seed's known errors. Round 2, given
the accumulated trajectory of all prior rounds, recovers and reaches a
perfect validation score with both of its candidates. candidate_4 is
selected over the tied candidate_3 by this project's tie break rule
(shorter prompt).

### Held out test accuracy (30 tickets, never used to write either prompt)

| prompt | exact match | errors |
|---|---|---|
| seed (never optimized) | 100.0% (30/30) | 0 |
| selected best, candidate_4 | 96.7% (29/30) | 1 |

The optimized prompt's overfitting gap (its own validation accuracy minus
its own test accuracy) is 3.3 points. More importantly, it loses to the
seed prompt it was built to improve on by the same 3.3 points on the data
that actually matters. The single remaining error is the tablespace
capacity ticket described above.

## Known limitations

- The within-call independence caveat described above.
- The dataset is fully synthetic and template based. Real on-call ticket
  text is messier, which would likely produce a richer and noisier error
  surface than the clean, single cause errors seen here, but the
  structural lesson (detailed rules fix what they target and can regress
  what they do not, and a validation set small enough to special case
  will eventually be special cased) does not depend on the text being
  synthetic.
- This project optimizes a single, fixed validation set across both
  rounds. A stronger design would use a fresh validation subsample per
  round, or k fold cross validation, specifically to make the round 2
  "special case everything" failure mode harder to fall into. That
  stronger design was deliberately not used here, because reproducing the
  simpler and more common mistake, optimizing repeatedly against one fixed
  sample, is the point of this project's honest result.
- Category accuracy never dropped below 90 percent in any round; every
  meaningful swing in this project's numbers is driven by severity
  assignment and by the 2 certificate related category errors in round 1,
  not by a broad category confusion problem.

## Repository layout

```
src/
  tickets.py     deterministic synthetic ticket generator and val/test split
  metrics.py     scoring (exact match, category accuracy, severity accuracy,
                 confusion matrix, error summaries)
  optimizer.py   loads the cached optimization trajectory, evaluates every
                 round, selects the best prompt, compares held out test results
scripts/
  build_dataset.py   regenerates fixtures/dataset.json (no LLM involved)
  run_demo.py        end to end reproducible demo, prints every number above
fixtures/
  dataset.json                  the 20 validation + 30 test tickets
  optimization_trajectory.json  every prompt variant, every prediction, with
                                 provenance (see its "provenance" field)
tests/
  16 automated tests covering ticket generation, scoring, and the
  optimization trajectory's specific claims (including a regression test
  that would fail if the cached held out result ever stopped showing the
  overfitting finding)
```

## Installation and reproduction

Requires Python 3.10 or later.

```bash
git clone https://github.com/julianodutraa/triage-prompt-optimizer.git
cd triage-prompt-optimizer
pip install -r requirements.txt

# run the full test suite (16 tests)
python3 -m pytest tests/ -v

# run the end to end reproducible demo (prints every number in this README)
python3 scripts/run_demo.py

# optional: regenerate the ticket dataset from scratch (no LLM involved)
python3 scripts/build_dataset.py
```

## Further reading

See `ARTICLE.md` in this repository for a narrative walkthrough of the two
optimization rounds and what the capacity rubric gap actually looked like
from the inside.

## Author context

Written by a data engineer working on large scale cloud data pipelines,
Kubernetes based orchestration, and on-call operations, as a focused,
reproducible exploration of automatic prompt optimization applied to a
triage task that recurs constantly in that line of work. No employer
systems, data, or proprietary information are referenced anywhere in this
repository.

## License

MIT, see `LICENSE`.
