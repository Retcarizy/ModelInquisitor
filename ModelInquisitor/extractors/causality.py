from __future__ import annotations

from ModelInquisitor.core.graph import dominators
from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind


class CausalityExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for process in model.processes.values():
            dom = dominators(process)
            observable_nodes = [
                node for node in process.nodes.values()
                if node.is_observable and node.id not in process.starts
            ]
            for target in observable_nodes:
                for source_id in sorted(dom.get(target.id, set()) - {target.id}):
                    source = process.nodes[source_id]
                    if not source.is_observable:
                        continue
                    claims.append(
                        Claim(
                            kind=ClaimKind.CAUSALITY,
                            process_id=process.id,
                            source_node_id=source.id,
                            target_node_id=target.id,
                            description=f"{source.id} must occur before {target.id}.",
                        )
                    )
        return claims

