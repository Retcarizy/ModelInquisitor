from __future__ import annotations

from ModelInquisitor.core.models import BPMNModel, Claim, ClaimKind


class MessageSynchronizationExtractor:
    def extract(self, model: BPMNModel) -> list[Claim]:
        claims: list[Claim] = []
        for message_flow in model.message_flows:
            if (
                message_flow.source_ref not in model.node_to_process
                or message_flow.target_ref not in model.node_to_process
            ):
                continue
            claims.append(
                Claim(
                    kind=ClaimKind.MESSAGE_SYNCHRONIZATION,
                    node_id=message_flow.id,
                    source_node_id=message_flow.source_ref,
                    target_node_id=message_flow.target_ref,
                    description=(
                        f"Message flow {message_flow.id} must synchronize "
                        f"{message_flow.source_ref} with {message_flow.target_ref}."
                    ),
                    metadata={
                        "message_flow_id": message_flow.id,
                        "message_name": message_flow.name,
                        "source_process_id": message_flow.source_process_id,
                        "target_process_id": message_flow.target_process_id,
                    },
                )
            )
        return claims
