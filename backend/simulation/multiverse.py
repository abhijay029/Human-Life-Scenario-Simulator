import concurrent.futures
from backend.agents.persona import Persona
from backend.agents.observer import analyse_dialogue
from backend.simulation.engine import run_simulation


def _run_branch(args: tuple, on_event=None, branch_id: str = "") -> dict:
    personas, scenario, decision_point, max_turns = args

    def emit(event: dict):
        if on_event:
            on_event({
                **event,
                "branch_id": branch_id,
                "branch_label": decision_point,
            })

    dialogue_log = run_simulation(
        personas=personas,
        scenario=scenario,
        decision_point=decision_point,
        max_turns=max_turns,
        on_event=emit,
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
    on_event=None,
) -> list[dict]:
    """
    Run each decision branch sequentially (safe for free-tier rate limits
    and local ChromaDB), then return results ranked by average persona
    goal success probability (descending).
    """
    results = []
    for branch_index, branch in enumerate(decision_branches):
        branch_id = f"branch-{branch_index}"
        print(f"\n[Multiverse] Running branch: {branch[:60]}...")
        if on_event:
            on_event({
                "type": "branch_started",
                "branch_id": branch_id,
                "branch_label": branch,
            })
        try:
            result = _run_branch(
                (personas, scenario, branch, max_turns),
                on_event=on_event,
                branch_id=branch_id,
            )
            results.append(result)
            if on_event:
                on_event({
                    "type": "branch_completed",
                    "branch_id": branch_id,
                    "branch_label": branch,
                })
        except Exception as exc:
            print(f"[Multiverse] Branch failed: {exc}")
            if on_event:
                on_event({
                    "type": "branch_failed",
                    "branch_id": branch_id,
                    "branch_label": branch,
                    "message": str(exc),
                })
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

    worse = scored[0][0]
    better = scored[-1][0]
    most_likely_idx = len(scored) // 2
    most_likely = scored[most_likely_idx][0]

    return {
        "better_case": {
            "decision_point": better["decision_point"],
            "outcome_category": better["analysis"].get("outcome_category"),
            "outcome_summary": better["analysis"].get("outcome_summary"),
            "avg_success_probability": round(scored[-1][1], 2),
        },
        "worse_case": {
            "decision_point": worse["decision_point"],
            "outcome_category": worse["analysis"].get("outcome_category"),
            "outcome_summary": worse["analysis"].get("outcome_summary"),
            "avg_success_probability": round(scored[0][1], 2),
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
