"""Deterministic synthetic generator for on-call incident ticket text.

Every ticket is produced from a fixed template keyed by (category,
severity), with randomized filler slots (service names, regions, hosts,
percentages, durations). Because the label is baked into which template
was chosen, not assigned independently of the text, the extraction task
has genuine textual signal to learn from rather than being an arbitrary
labeling exercise, while remaining fully synthetic and reproducible from a
fixed seed.
"""

from __future__ import annotations

import dataclasses
import random
from typing import List

CATEGORIES = [
    "db_capacity",
    "pipeline_failure",
    "network_connectivity",
    "deployment_regression",
    "security_alert",
]

SEVERITIES = ["P1", "P2", "P3", "P4"]

_SERVICES = ["checkout-api", "billing-worker", "ingest-gateway", "auth-service", "reporting-api"]
_DATABASES = ["orders_db", "events_db", "billing_db", "analytics_db", "sessions_db"]
_REGIONS = ["us-east-1", "sa-east-1", "eu-west-1", "us-west-2"]
_PIPELINES = ["daily_sales_etl", "clickstream_agg", "inventory_sync", "fraud_features_dag"]
_HOSTS = ["db-node-03", "db-node-07", "db-node-11", "db-node-14"]

_TEMPLATES = {
    ("db_capacity", "P1"): "The {database} database on {host} has exceeded 98 percent of allocated storage and write operations are now failing.",
    ("db_capacity", "P2"): "Tablespace usage on {database} crossed 90 percent and is projected to fill within 48 hours at the current growth rate.",
    ("db_capacity", "P3"): "Storage utilization on {database} reached 80 percent during last night's batch load, above the usual range.",
    ("db_capacity", "P4"): "Routine capacity check shows {database} storage at 65 percent, trending up slowly with no action needed yet.",
    ("pipeline_failure", "P1"): "The {pipeline} DAG has failed for the third consecutive run, no downstream tables have been refreshed in over 18 hours.",
    ("pipeline_failure", "P2"): "The {pipeline} DAG failed on its scheduled run tonight, the last successful run was 26 hours ago.",
    ("pipeline_failure", "P3"): "A single task in the {pipeline} DAG retried twice before succeeding, adding about 40 minutes of delay to the run.",
    ("pipeline_failure", "P4"): "The {pipeline} DAG completed successfully but logged a deprecation warning about an upcoming API change.",
    ("network_connectivity", "P1"): "All pods in the {service} namespace are unreachable after a networking change in {region}, full outage in progress.",
    ("network_connectivity", "P2"): "Intermittent connection timeouts between {service} and {database} are causing elevated error rates in {region}.",
    ("network_connectivity", "P3"): "Latency between {service} and its upstream dependency increased by 35 percent after a routing change in {region}.",
    ("network_connectivity", "P4"): "A brief, one minute network blip was observed in {region} with no customer impact reported.",
    ("deployment_regression", "P1"): "The deployment of {service} version 4.2 is causing 100 percent of requests to return errors in production.",
    ("deployment_regression", "P2"): "After deploying {service} version 3.9, the error rate climbed to 22 percent and a rollback is in progress.",
    ("deployment_regression", "P3"): "The {service} deployment introduced a minor regression, increasing p99 latency by 15 percent.",
    ("deployment_regression", "P4"): "The {service} deployment to staging completed with no issues, promoting to production next cycle.",
    ("security_alert", "P1"): "An unauthorized access attempt was detected against {database} using credentials that match no known service account.",
    ("security_alert", "P2"): "A certificate used by {service} expired unexpectedly, blocking authenticated requests in {region}.",
    ("security_alert", "P3"): "A routine security scan flagged an outdated dependency in {service} with a medium severity CVE.",
    ("security_alert", "P4"): "Access review for {service} completed with no findings, next review scheduled in three months.",
}


@dataclasses.dataclass
class Ticket:
    ticket_id: str
    text: str
    true_category: str
    true_severity: str


def _fill(template: str, rng: random.Random) -> str:
    return template.format(
        service=rng.choice(_SERVICES),
        database=rng.choice(_DATABASES),
        region=rng.choice(_REGIONS),
        pipeline=rng.choice(_PIPELINES),
        host=rng.choice(_HOSTS),
    )


def generate_tickets(n_per_combo: int, seed: int) -> List[Ticket]:
    """Generate `n_per_combo` tickets for every (category, severity) combo
    (20 combos), in a fixed, deterministic order.
    """
    rng = random.Random(seed)
    tickets: List[Ticket] = []
    counter = 0
    for category in CATEGORIES:
        for severity in SEVERITIES:
            template = _TEMPLATES[(category, severity)]
            for _ in range(n_per_combo):
                text = _fill(template, rng)
                tickets.append(
                    Ticket(
                        ticket_id=f"T{counter:03d}",
                        text=text,
                        true_category=category,
                        true_severity=severity,
                    )
                )
                counter += 1
    return tickets


def split_tickets(tickets: List[Ticket], seed: int, n_val: int, n_test: int):
    """Shuffle (deterministically) and split into (validation, test),
    stratified implicitly by generating from a combo-major order before
    shuffling with a fixed seed.
    """
    rng = random.Random(seed)
    shuffled = tickets[:]
    rng.shuffle(shuffled)
    val = shuffled[:n_val]
    test = shuffled[n_val : n_val + n_test]
    return val, test
