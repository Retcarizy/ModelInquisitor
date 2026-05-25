from __future__ import annotations

from ModelInquisitor.core.graph import find_join
from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind, ProcessModel


class ExclusiveBranchReachabilityExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for process in model.processes.values():
            for gateway in process.nodes.values():
                successors = process.successors(gateway.id)
                if gateway.type != "exclusiveGateway" or len(successors) < 2:
                    continue

                join = find_join(process, successors)
                branch_actions = self._unique(
                    node_id
                    for start in successors
                    if (node_id := self._first_observable_in_branch(process, start, join))
                )
                for branch_action in branch_actions:
                    claims.append(
                        Claim(
                            kind=ClaimKind.EXCLUSIVE_BRANCH_REACHABILITY,
                            process_id=process.id,
                            node_id=gateway.id,
                            branch_node_ids=(branch_action,),
                            description=(
                                f"Exclusive branch {branch_action} under {gateway.id} "
                                "should remain reachable."
                            ),
                            metadata={
                                "choice_gateway_id": gateway.id,
                                "join_node_id": join,
                            },
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

    def _unique(self, values) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))
