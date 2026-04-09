"""
Multiverse Engine
=================
Runs the same scenario across multiple decision branches in parallel,
then uses the Observer Agent to score each branch.

Usage
-----
from backend.simulation.multiverse import run_multiverse

results = run_multiverse(
    personas=[rahul, arjun],
    scenario="...",
    decision_branches=[
        "Arjun is honest and direct.",
        "Arjun is evasive and avoids the topic.",
        "Arjun brings a third party mediator.",
    ],
    max_turns=6,
)

Each entry in `results` is:
{
    "decision_point": str,
    "dialogue_log": list[dict],
    "analysis": dict,          # from Observer Agent
}
"""

import concurrent.futures
from backend.agents.persona import Persona
from backend.agents.observer import analyse_dialogue
from backend.simulation.engine import run_simulation


def _run_branch(args: tuple) -> dict:
    personas, scenario, decision_point, max_turns = args
    dialogue_log = run_simulation(
        personas=personas,
        scenario=scenario,
        decision_point=decision_point,
        max_turns=max_turns,
    )
    analysis = analyse_dialogue(
        dialogue_log=dialogue_log,
        scenario=scenario,
        decision_point=decision_point,
        personas=[p.model_dump() for p in personas],
    )
    return {
        "decision_point": decision_point,
        "dialogue_log": dialogue_log,
        "analysis": analysis,
    }


def run_multiverse(
    personas: list[Persona],
    scenario: str,
    decision_branches: list[str],
    max_turns: int = 6,
    max_workers: int = 3,
) -> list[dict]:
    """
    Run each decision branch concurrently and return all results ranked by
    average persona goal success probability (descending).
    """
    args_list = [
        (personas, scenario, branch, max_turns)
        for branch in decision_branches
    ]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run_branch, args): args for args in args_list}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover
                branch = futures[future][2]
                results.append({
                    "decision_point": branch,
                    "dialogue_log": [],
                    "analysis": {"error": str(exc)},
                })

    # Sort: best average goal-success first
    def _avg_success(r: dict) -> float:
        pgs = r.get("analysis", {}).get("persona_goal_success", [])
        if not pgs:
            return 0.0
        return sum(p.get("success_probability", 0.0) for p in pgs) / len(pgs)

    results.sort(key=_avg_success, reverse=True)
    return results


def generate_comparison_report(multiverse_results: list[dict]) -> dict:
    """
    Produce a high-level comparison report across all branches.
    Returns Best Case, Worst Case, and Most Likely branches.
    """
    if not multiverse_results:
        return {}

    def _avg(r):
        pgs = r.get("analysis", {}).get("persona_goal_success", [])
        if not pgs:
            return 0.0
        return sum(p.get("success_probability", 0.0) for p in pgs) / len(pgs)

    scored = [(r, _avg(r)) for r in multiverse_results]
    scored.sort(key=lambda x: x[1])

    worst = scored[0][0]
    best = scored[-1][0]
    most_likely_idx = len(scored) // 2
    most_likely = scored[most_likely_idx][0]

    return {
        "best_case": {
            "decision_point": best["decision_point"],
            "outcome_category": best["analysis"].get("outcome_category"),
            "outcome_summary": best["analysis"].get("outcome_summary"),
            "avg_success_probability": round(scored[-1][1], 2),
        },
        "worst_case": {
            "decision_point": worst["decision_point"],
            "outcome_category": worst["analysis"].get("outcome_category"),
            "outcome_summary": worst["analysis"].get("outcome_summary"),
            "avg_success_probability": round(scored[0][1], 2),
        },
        "most_likely": {
            "decision_point": most_likely["decision_point"],
            "outcome_category": most_likely["analysis"].get("outcome_category"),
            "outcome_summary": most_likely["analysis"].get("outcome_summary"),
            "avg_success_probability": round(scored[most_likely_idx][1], 2),
        },
        "all_branches_ranked": [
            {
                "decision_point": r["decision_point"],
                "outcome_category": r["analysis"].get("outcome_category"),
                "avg_success_probability": round(s, 2),
            }
            for r, s in scored[::-1]
        ],
    }
