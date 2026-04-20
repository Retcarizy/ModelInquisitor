from __future__ import annotations

from itertools import combinations

from ModelInquisitor.core.graph import find_join
from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind, ProcessModel


class MutexExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for process in model.processes.values():
            for node in process.nodes.values():
                successors = process.successors(node.id)
                if node.type != "exclusiveGateway" or len(successors) < 2:
                    continue
                join = find_join(process, successors)
                branch_actions = [
                    self._first_observable_in_branch(process, start, stop_at=join)
                    for start in successors
                ]
                branch_actions = [node_id for node_id in branch_actions if node_id]
                for left, right in combinations(branch_actions, 2):
                    claims.append(
                        Claim(
                            kind=ClaimKind.MUTEX,
                            process_id=process.id,
                            node_id=node.id,
                            branch_node_ids=(left, right),
                            description=f"Exclusive branches {left} and {right} should not both occur.",
                        )
                    )
        return claims

    def _first_observable_in_branch(
        self,
        process: ProcessModel,
        start: str,
        stop_at: str | None,
    ) -> str | None:
        stack = [start]
        seen: set[str] = set()
        while stack:
            node_id = stack.pop()
            if node_id == stop_at or node_id in seen:
                continue
            seen.add(node_id)
            node = process.nodes[node_id]
            if node.is_observable:
                return node_id
            stack.extend(reversed(process.successors(node_id)))
        return None

