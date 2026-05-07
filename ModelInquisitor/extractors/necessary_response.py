from __future__ import annotations

from ModelInquisitor.core.graph import post_dominators
from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind


class NecessaryResponseExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for process in model.processes.values():
            post_dom = post_dominators(process)
            observable_nodes = [
                node
                for node in process.nodes.values()
                if node.is_observable
            ]
            for source in observable_nodes:
                for target_id in sorted(post_dom.get(source.id, set()) - {source.id}):
                    target = process.nodes[target_id]
                    if not target.is_observable:
                        continue
                    claims.append(
                        Claim(
                            kind=ClaimKind.NECESSARY_RESPONSE,
                            process_id=process.id,
                            source_node_id=source.id,
                            target_node_id=target.id,
                            description=(
                                f"{target.id} must eventually occur after {source.id}."
                            ),
                        )
                    )
        return claims
