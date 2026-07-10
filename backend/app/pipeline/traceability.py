"""Pass 4 — pure-Python traceability graph: observation -> requirement -> task.

No LLM call needed; this is just relational bookkeeping over data we already
produced, which is exactly why it belongs outside the LLM pipeline (free
and instant).
"""


def build_traceability(observations: list, requirements: list, tasks: list) -> list[dict]:
    obs_by_id = {obs["obs_id"]: obs for obs in observations}
    tasks_by_req: dict[str, list] = {}
    for task in tasks:
        tasks_by_req.setdefault(task["req_id"], []).append(task)

    trace = []
    for req in requirements:
        req_observations = [obs_by_id[oid] for oid in req.get("source_obs", []) if oid in obs_by_id]
        trace.append({
            "req_id": req["req_id"],
            "description": req["description"],
            "aep_layer": req["aep_layer"],
            "source_section": req["source_section"],
            "observations": req_observations,
            "tasks": tasks_by_req.get(req["req_id"], []),
        })
    return trace
