"""Small, explicit economics calculations (P8D).

Every function here is a transparent formula. Two conventions hold throughout:

* Missing inputs produce ``None``, never a fabricated zero or estimate.
* Token counts are never converted into dollars.

Functions come in two flavors: scalar helpers that take explicit numbers (useful
for aggregate/probabilistic reasoning) and ``run_*`` helpers that read the
optional fields of an :class:`~deep_agents_foundry.economics.models.EconomicsRun`.
The ``run_*`` helpers are duck-typed and only require the relevant attributes.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import cycle with models.py
    from .models import EconomicsRun


def average(values: Iterable[float | None]) -> float | None:
    """Mean of the supplied values, ignoring ``None``.

    Returns ``None`` when no non-``None`` value is present so that an absent
    metric never appears as ``0.0``.
    """
    present = [float(value) for value in values if value is not None]
    return sum(present) / len(present) if present else None


# --------------------------------------------------------------------------- #
# Scalar formulas
# --------------------------------------------------------------------------- #
def total_tokens(
    input_tokens: int | None,
    output_tokens: int | None,
    total: int | None = None,
) -> int | None:
    """``total`` when given, else ``input + output`` when both are present."""
    if total is not None:
        return int(total)
    if input_tokens is not None and output_tokens is not None:
        return int(input_tokens) + int(output_tokens)
    return None


def labor_cost(minutes: float | None, hourly_cost: float | None) -> float | None:
    """Convert ``minutes`` of human effort into a dollar cost.

    ``minutes / 60 * hourly_cost``. Returns ``None`` unless both inputs exist.
    """
    if minutes is None or hourly_cost is None:
        return None
    return (float(minutes) / 60.0) * float(hourly_cost)


def expected_failure_cost(
    failure_probability: float | None,
    failure_cost: float | None,
) -> float | None:
    """``P(failure) * failure_cost``. ``None`` if either input is missing."""
    if failure_probability is None or failure_cost is None:
        return None
    return float(failure_probability) * float(failure_cost)


def effective_task_cost(
    agent_cost: float | None,
    human_review_cost: float | None = None,
    human_rework_cost: float | None = None,
    failure_cost_component: float | None = None,
) -> float | None:
    """Sum agent cost with any supplied human and expected-failure costs.

    Anchored on ``agent_cost``: returns ``None`` when the agent cost is unknown.
    Missing human or failure components are *excluded* from the sum (they add
    nothing) rather than being invented — the caller decides which components to
    supply, and reporting shows which were available.

        effective = agent_cost + human_review + human_rework + expected_failure
    """
    if agent_cost is None:
        return None
    total = float(agent_cost)
    for component in (human_review_cost, human_rework_cost, failure_cost_component):
        if component is not None:
            total += float(component)
    return total


def success_rate(successes: int | None, total: int | None) -> float | None:
    """``successes / total``. Returns ``None`` when total is 0 or unknown."""
    if successes is None or total is None or total == 0:
        return None
    return float(successes) / float(total)


def cost_per_successful_task(
    total_cost: float | None, successes: int | None
) -> float | None:
    """``total_cost / successes``. ``None`` when cost is missing or no successes."""
    if total_cost is None or successes is None or successes == 0:
        return None
    return float(total_cost) / float(successes)


def per_successful_task(
    total_amount: float | None, successes: int | None
) -> float | None:
    """Generic amount-per-successful-task (tokens, searches, effective cost)."""
    if total_amount is None or successes is None or successes == 0:
        return None
    return float(total_amount) / float(successes)


def expected_business_value(
    success_probability: float | None,
    value_if_success: float | None,
) -> float | None:
    """``P(success) * value_if_success``. ``None`` if either input is missing."""
    if success_probability is None or value_if_success is None:
        return None
    return float(success_probability) * float(value_if_success)


def expected_net_value(
    business_value: float | None,
    failure_cost_component: float | None = None,
    agent_cost: float | None = None,
    human_cost: float | None = None,
) -> float | None:
    """Expected business value minus expected failure, agent, and human costs.

    Anchored on ``business_value``: returns ``None`` when no business value is
    supplied (P8D never fabricates business value). Missing cost components are
    excluded rather than assumed zero.
    """
    if business_value is None:
        return None
    net = float(business_value)
    for component in (failure_cost_component, agent_cost, human_cost):
        if component is not None:
            net -= float(component)
    return net


# --------------------------------------------------------------------------- #
# Run-level helpers
# --------------------------------------------------------------------------- #
def run_total_tokens(run: EconomicsRun) -> int | None:
    return run.resolved_total_tokens()


def run_human_review_cost(run: EconomicsRun) -> float | None:
    return labor_cost(run.human_review_minutes, run.hourly_human_cost)


def run_human_rework_cost(run: EconomicsRun) -> float | None:
    return labor_cost(run.human_rework_minutes, run.hourly_human_cost)


def run_human_cost(run: EconomicsRun) -> float | None:
    """Combined review + rework labor cost, or ``None`` if neither is known."""
    parts = [
        cost
        for cost in (run_human_review_cost(run), run_human_rework_cost(run))
        if cost is not None
    ]
    return sum(parts) if parts else None


def run_realized_failure_cost(run: EconomicsRun) -> float | None:
    """Realized failure cost for a single run: ``failure_cost`` if it failed.

    Returns ``0.0`` on a known success, the ``failure_cost`` on a known failure,
    and ``None`` when the outcome or failure cost is unknown.
    """
    if run.task_success is None or run.failure_cost is None:
        return None
    return 0.0 if run.task_success else float(run.failure_cost)


def run_effective_task_cost(run: EconomicsRun) -> float | None:
    """Effective cost of a single run using its realized outcome.

    Averaged across many runs this equals ``agent + human + P(failure)*failure``
    when the failure cost is constant.
    """
    return effective_task_cost(
        run.agent_cost,
        human_review_cost=run_human_review_cost(run),
        human_rework_cost=run_human_rework_cost(run),
        failure_cost_component=run_realized_failure_cost(run),
    )


def run_realized_business_value(run: EconomicsRun) -> float | None:
    """Realized business value for a single run: value on success, else 0.0."""
    if run.task_success is None or run.business_value_if_success is None:
        return None
    return float(run.business_value_if_success) if run.task_success else 0.0


def run_expected_net_value(run: EconomicsRun) -> float | None:
    """Net value of a single run using realized outcome and supplied costs."""
    return expected_net_value(
        run_realized_business_value(run),
        failure_cost_component=run_realized_failure_cost(run),
        agent_cost=run.agent_cost,
        human_cost=run_human_cost(run),
    )
