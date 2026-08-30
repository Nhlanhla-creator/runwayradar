"""Stage 6: flag the top issues for human action.

The full recommendation list is long and noisy to act on; this stage picks the
highest-impact items and pairs each with an explicit, one-line reason so a human
can act without re-reading the whole trace.
"""
from __future__ import annotations

from ..trace import Trace

MAX_FLAGGED = 5


def flag_for_action(trace: Trace, recommendations: list[dict]) -> list[dict]:
    action = trace.start("flag_for_action", recommendation_count=len(recommendations))

    flagged = recommendations[:MAX_FLAGGED]
    for f in flagged:
        f["action_reason"] = (
            f"{f['vendor']} — {f['recommendation']} "
            f"(~${f['annual_cost_estimate']:,.2f}/yr impact)"
        )

    action.finish({"flagged_count": len(flagged)})
    return flagged
