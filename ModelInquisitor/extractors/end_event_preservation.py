from __future__ import annotations

from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind


class EndEventPreservationExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for process in model.processes.values():
            for node in process.nodes.values():
                if node.type != "endEvent":
                    continue
                claims.append(
                    Claim(
                        kind=ClaimKind.END_EVENT_PRESERVATION,
                        process_id=process.id,
                        node_id=node.id,
                        description=(
                            f"End event {node.id} should be preserved as a reachable "
                            "termination action."
                        ),
                    )
                )
        return claims
