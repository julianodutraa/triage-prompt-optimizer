# The Prompt That Got Worse by Getting Better

There is a specific, seductive moment in prompt engineering that this
project exists to pick apart. You have a prompt. You run it against a
handful of examples. Three of them come back wrong. You look at the three,
you see the pattern, you add a sentence that fixes exactly that pattern,
you run it again, and now it is right. It feels like debugging, because it
has the same shape as debugging: observe a failure, diagnose a cause, patch
it, confirm the patch worked. The problem is that it is not quite
debugging. A bug fix changes behavior on an input space you understand. A
prompt edit written from three examples changes behavior on an input space
you do not fully control, and the only evidence you have that it worked is
that it worked on the three examples you were looking at when you wrote it.

This project builds the smallest honest version of that loop, automates
the "look at the errors, write a fix" step with an LLM acting as its own
optimizer, and then does the one thing that loop almost never does on its
own: checks the result against data nobody looked at while writing the fix.

## The setup

The task is on-call incident triage: read a short ticket description, such
as "the fraud_features_dag DAG has failed for the third consecutive run,
no downstream tables have been refreshed in over 18 hours," and assign it
a category (pipeline_failure, db_capacity, network_connectivity,
deployment_regression, or security_alert) and a severity (P1 through P4).
Sixty tickets were generated from fixed templates, so every label is known
exactly, and split into 20 for validation and 30 held out for a final test
that would not be touched until the very end.

The seed prompt is deliberately plain: define the five categories and four
severities in one line each, and ask for an answer. No rubric, no
examples, no disambiguation rules. It is the prompt a reasonably careful
engineer writes in five minutes before deciding whether to invest more
time. On the validation set, it scored 85 percent, with exactly three
errors, and all three had the same shape: a pipeline failure ticket graded
one severity notch too lenient, as if the model were hedging downward in
the absence of explicit guidance about how bad "bad" is.

## Round one: a reasonable fix that broke something else

Three consistent errors is exactly the kind of signal an automatic
optimizer should be good at acting on. Given those three errors, an LLM
acting as the optimizer wrote two different candidate prompts, each adding
an explicit severity rubric with concrete thresholds (a job failing on two
or more consecutive runs is P1, a single failed run is P2, a retry that
still succeeded is P3, and so on), and some guidance for the handful of
"clean, nothing is wrong" tickets the category list had no good home for.
Scored again on the same 20 tickets, both candidates fixed all three
original errors. And both scored lower overall than the seed: 80 percent
and 75 percent, against the seed's 85.

The reason was not a mistake in the rubric's severity logic, it was a side
effect of describing the categories more precisely in order to write that
rubric at all. One candidate's description of network_connectivity
mentioned "certificate and TLS issues" as an example of what belongs
there. Two validation tickets describe an expired certificate blocking
authenticated requests, and their true category is security_alert, not
network_connectivity. The plain seed prompt, with no category description
beyond a bare name, had gotten both right, apparently by relying on
whatever prior association the model already has between "certificate"
and "security" with no competing cue to override it. The improved prompt
introduced a competing cue, in service of a completely different goal,
and lost two tickets it had not been failing before. This is the generic
risk of writing a rule from a small number of observed failures: the rule
solves what it names and is silent, at best, about everything adjacent to
what it names.

## Round two: given the full trajectory, and the trap underneath 100 percent

The second round was handed everything: the seed prompt and its three
errors, both round one candidates and their prompts and their five
combined distinct errors, with an explicit diagnosis of the certificate
regression. Told to keep the rubric's severity logic while removing the
competing cue, both new candidates did exactly that, stripping any mention
of certificates from the network category and adding an explicit exclusion
rule instead. Both reached a perfect 100 percent on the validation set.

A perfect score on a fixed 20 item set, after two rounds of
targeted repair, deserves suspicion rather than celebration, and the held
out test set is where that suspicion paid off. The better of the two
candidates was selected (an arbitrary tie break, since both tied at 100
percent) and run, alongside the never touched seed prompt, on the 30 test
tickets. The seed prompt scored 100 percent. The optimized prompt, fresh
off its perfect validation score, scored 96.7 percent: one error, on a
ticket the validation set had never needed to cover.

That ticket reports tablespace usage on a database crossing 90 percent,
projected to fill within 48 hours. The true severity is P2: a trajectory
toward real trouble, not yet an outage, but past the point of "elevated
and worth watching." The optimized prompt's severity rubric, built and
rebuilt entirely in response to validation set errors that never happened
to include this exact shape of ticket, ended up with a gap: P1 required 95
percent capacity with active write failures, P3 covered 75 to 90 percent
with no failure, and nothing in between was ever written down, because
nothing in the validation set ever forced the question. The optimized
prompt did not get this ticket wrong because it is a worse classifier in
general. It got it wrong because two rounds of fixing exactly what was in
front of it had quietly produced a rubric with a hole shaped precisely
like whatever the validation set happened not to contain.

## What this is actually evidence of

This is not an argument against prompt optimization, automatic or manual.
It is evidence for a narrower and more useful claim: a validation set that
is small enough, and reused across enough rounds, is a validation set an
optimizer can eventually special case its way around, and a perfect score
on it stops being informative right around the point it starts looking
most impressive. The seed prompt's plain, under specified honesty, the
thing that made it score only 85 percent to start with, is also exactly
why it had no rubric gap to fall into. Every rule the optimization process
added was a rule that could be wrong somewhere the validation set was not
looking, and after two rounds, the accumulated rules were wrong in exactly
one place the validation set had never visited.

The practical takeaway for anyone wiring an LLM into a triage queue is
unglamorous but concrete: never ship on validation accuracy alone, keep a
held out set that genuinely never informs a single word of prompt text,
and treat a sudden jump to a perfect score as a question to investigate,
not a result to deploy.

The full dataset, every prompt variant, every prediction, and the 16
automated tests that check these specific claims are reproducible at
https://github.com/julianodutraa/triage-prompt-optimizer.
