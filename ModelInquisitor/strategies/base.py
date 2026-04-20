from __future__ import annotations

from abc import ABC, abstractmethod

from ModelInquisitor.core.models import BPMNModel, BPMNNode, MessageFlow


class TranslatorNamingStrategy(ABC):
    """Map BPMN semantic references to concrete mCRL2 names."""

    @abstractmethod
    def prepare(self, model: BPMNModel) -> None:
        """Index a parsed model before resolving names."""

    @abstractmethod
    def action_for_node(self, node: BPMNNode) -> str | None:
        """Return the mCRL2 action name for a BPMN node, excluding data parameters."""

    @abstractmethod
    def message_actions(self, message_flow: MessageFlow) -> tuple[str, str, str]:
        """Return send, receive, and communicated action names for a message flow."""

    @abstractmethod
    def observable_actions_for_node(self, node: BPMNNode) -> tuple[str, ...]:
        """Return actions that are visible in the translated model."""

    @abstractmethod
    def all_claim_actions(self, model: BPMNModel) -> set[str]:
        """Return action names that generated formulas may mention."""

