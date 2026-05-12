from __future__ import annotations

from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind


class ActionPreservationExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for process in model.processes.values():
            for node in process.nodes.values():
                if not node.is_observable:
                    continue
                claims.append(
                    Claim(
                        kind=ClaimKind.ACTION_PRESERVATION,
                        process_id=process.id,
                        node_id=node.id,
                        description=f"Observable node {node.id} should be preserved as a reachable action.",
                    )
                )
        return claims
