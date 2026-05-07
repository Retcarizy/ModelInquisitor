from __future__ import annotations

import re

from ModelInquisitor.core.graph import find_join
from ModelInquisitor.core.models import BPMNModel, BPMNNode, MessageFlow
from ModelInquisitor.strategies.base import TranslatorNamingStrategy


def clean_name(name: str | None) -> str:
    if not name:
        return "unnamed_action"
    cleaned = re.sub(r"[^a-zA-Z0-9]", "_", name).strip("_").lower()
    return cleaned if cleaned else "action"


def camel_to_snake(name: str) -> str:
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return clean_name(name)


class ThirdPartyBpmn2Mcrl2Strategy(TranslatorNamingStrategy):
    """Naming strategy compatible with third-party/bpmn2mcrl2.

    This class mirrors the translator naming conventions without importing the
    translator itself, keeping the checker extensible.
    """

    forbidden_allow_prefixes = ("s_", "r_", "s_sync")

    def __init__(self) -> None:
        self.model: BPMNModel | None = None
        self.exact_msg_nodes: dict[str, tuple[str, str]] = {}
        self.parallel_gateway_ids: dict[str, int] = {}

    def prepare(self, model: BPMNModel) -> None:
        self.model = model
        self.exact_msg_nodes = {}
        for message_flow in model.message_flows:
            msg_name = clean_name(message_flow.name or "msg")
            if message_flow.source_ref in model.node_to_process:
                self.exact_msg_nodes[message_flow.source_ref] = ("s", msg_name)
            if message_flow.target_ref in model.node_to_process:
                self.exact_msg_nodes[message_flow.target_ref] = ("r", msg_name)
        self.parallel_gateway_ids = self._assign_parallel_gateway_ids(model)

    def action_for_node(self, node: BPMNNode) -> str | None:
        if self.model is None:
            raise RuntimeError("strategy.prepare(model) must be called first")

        if node.type == "endEvent":
            return clean_name(node.name or "end_event")

        if node.id in self.exact_msg_nodes:
            role, msg_name = self.exact_msg_nodes[node.id]
            return f"{role}_{msg_name}"

        if node.type in {"boundaryEvent", "intermediateCatchEvent", "intermediateThrowEvent"}:
            prefix = "boundary" if node.type == "boundaryEvent" else "event"
            return self._event_action(node, prefix)

        if node.type == "startEvent":
            return self._event_action(node, "start") if node.event_definitions else None

        if node.is_task:
            return clean_name(node.name or node.id)

        return None

    def message_actions(self, message_flow: MessageFlow) -> tuple[str, str, str]:
        msg_name = clean_name(message_flow.name or "msg")
        return f"s_{msg_name}", f"r_{msg_name}", f"c_{msg_name}"

    def observable_actions_for_node(self, node: BPMNNode) -> tuple[str, ...]:
        action = self.action_for_node(node)
        if action is None:
            return ()
        if action.startswith(self.forbidden_allow_prefixes):
            c_action = self._communicated_action_for_exact_message(node.id)
            return (c_action,) if c_action else ()
        return (action,)

    def auxiliary_actions_for_node(self, node: BPMNNode) -> tuple[str, ...]:
        action = self.action_for_node(node)
        if action is None:
            return ()
        if action.startswith(self.forbidden_allow_prefixes):
            return (action,)
        return ()

    def all_claim_actions(self, model: BPMNModel) -> set[str]:
        actions: set[str] = set()
        for process in model.processes.values():
            for node in process.nodes.values():
                actions.update(self.observable_actions_for_node(node))
        for message_flow in model.message_flows:
            actions.add(self.message_actions(message_flow)[2])
        return actions

    def sync_actions_for_parallel_gateway(self, gateway_node_id: str, branch_count: int) -> dict[str, object]:
        gateway_id = self.parallel_gateway_ids[gateway_node_id]
        return {
            "branch_processes": tuple(f"gw_{gateway_id}_branch_{i}" for i in range(branch_count)),
            "handler_process": f"gw_{gateway_id}_handler",
            "start": (f"s_start_gw_{gateway_id}", f"r_start_gw_{gateway_id}", f"c_start_gw_{gateway_id}"),
            "joins": (
                tuple(f"s_sync_{gateway_id}_{i}" for i in range(branch_count)),
                f"r_sync_join_{gateway_id}",
                f"c_sync_join_{gateway_id}",
            ),
        }

    def _event_action(self, node: BPMNNode, prefix: str) -> str:
        base_source = node.name if node.name and node.name != node.id else "_".join(node.event_definitions) or node.id
        base = clean_name(base_source)
        return base if base.startswith(prefix + "_") else f"{prefix}_{base}"

    def _communicated_action_for_exact_message(self, node_id: str) -> str | None:
        if node_id not in self.exact_msg_nodes:
            return None
        _, msg_name = self.exact_msg_nodes[node_id]
        return f"c_{msg_name}"

    def _assign_parallel_gateway_ids(self, model: BPMNModel) -> dict[str, int]:
        gateway_ids: dict[str, int] = {}
        counter = 0
        for process in model.processes.values():
            visited: set[str] = set()
            stack = list(reversed(process.starts)) or list(reversed(list(process.nodes)))
            while stack:
                node_id = stack.pop()
                if node_id in visited:
                    continue
                visited.add(node_id)
                node = process.nodes.get(node_id)
                successors = process.successors(node_id)
                if node and node.type == "parallelGateway" and len(successors) > 1:
                    counter += 1
                    gateway_ids[node_id] = counter
                    join = find_join(process, successors)
                    for branch_start in reversed(successors):
                        branch_seen = set()
                        branch_stack = [branch_start]
                        while branch_stack:
                            current = branch_stack.pop()
                            if current == join or current in branch_seen:
                                continue
                            branch_seen.add(current)
                            stack.append(current)
                            branch_stack.extend(reversed(process.successors(current)))
                    if join:
                        stack.append(join)
                    continue
                stack.extend(reversed(successors))
        return gateway_ids
