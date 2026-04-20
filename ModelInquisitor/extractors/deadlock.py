from __future__ import annotations

from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind


class DeadlockFreedomExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for process in model.processes.values():
            end_nodes = tuple(
                node.id for node in process.nodes.values() if node.type == "endEvent"
            )
            claims.append(
                Claim(
                    kind=ClaimKind.DEADLOCK_FREEDOM,
                    process_id=process.id,
                    branch_node_ids=end_nodes,
                    description=f"Process {process.id} should be able to reach an end event.",
                )
            )
        return claims

