from __future__ import annotations

from collections import deque

from ModelInquisitor.core.models import ProcessModel


def reachable_from(process: ProcessModel, start: str) -> set[str]:
    seen: set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(process.successors(current))
    return seen


def find_join(process: ProcessModel, branch_starts: list[str]) -> str | None:
    if not branch_starts:
        return None
    reach_sets = [reachable_from(process, start) for start in branch_starts]
    candidates = set.intersection(*reach_sets) if reach_sets else set()
    if not candidates:
        return None
    incoming_counts: dict[str, int] = {}
    for source, target in process.graph_edges():
        incoming_counts[target] = incoming_counts.get(target, 0) + 1
    merge_candidates = [
        node_id
        for node_id in candidates
        if incoming_counts.get(node_id, 0) > 1 and node_id not in branch_starts
    ]
    return sorted(merge_candidates or candidates)[0]


def dominators(process: ProcessModel) -> dict[str, set[str]]:
    nodes = set(process.nodes)
    if not nodes:
        return {}

    starts = set(process.starts) or {
        node_id for node_id in nodes if not process.predecessors(node_id)
    }
    dom: dict[str, set[str]] = {
        node_id: ({node_id} if node_id in starts else set(nodes))
        for node_id in nodes
    }

    changed = True
    while changed:
        changed = False
        for node_id in sorted(nodes - starts):
            preds = process.predecessors(node_id)
            if preds:
                pred_doms = [dom[pred] for pred in preds if pred in dom]
                new_dom = set.intersection(*pred_doms) if pred_doms else set()
            else:
                new_dom = set()
            new_dom.add(node_id)
            if new_dom != dom[node_id]:
                dom[node_id] = new_dom
                changed = True
    return dom


def post_dominators(process: ProcessModel) -> dict[str, set[str]]:
    nodes = set(process.nodes)
    if not nodes:
        return {}

    exits = {
        node_id for node_id in nodes
        if not process.successors(node_id)
    }
    reverse_successors: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for source, target in process.graph_edges():
        if source in nodes and target in reverse_successors:
            reverse_successors[target].append(source)

    can_reach_exit: set[str] = set()
    queue: deque[str] = deque(exits)
    while queue:
        current = queue.popleft()
        if current in can_reach_exit:
            continue
        can_reach_exit.add(current)
        queue.extend(reverse_successors.get(current, ()))

    post_dom: dict[str, set[str]] = {
        node_id: (
            {node_id}
            if node_id in exits or node_id not in can_reach_exit
            else set(can_reach_exit)
        )
        for node_id in nodes
    }

    changed = True
    while changed:
        changed = False
        for node_id in sorted(can_reach_exit - exits):
            successors = [
                successor for successor in process.successors(node_id)
                if successor in can_reach_exit
            ]
            if successors:
                successor_post_doms = [
                    post_dom[successor]
                    for successor in successors
                    if successor in post_dom
                ]
                new_post_dom = (
                    set.intersection(*successor_post_doms)
                    if successor_post_doms
                    else set()
                )
            else:
                new_post_dom = set()
            new_post_dom.add(node_id)
            if new_post_dom != post_dom[node_id]:
                post_dom[node_id] = new_post_dom
                changed = True
    return post_dom
