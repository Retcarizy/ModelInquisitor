"""Claim extractors."""

from ModelInquisitor.core.models import BPMNModel, Claim
from ModelInquisitor.extractors.action_preservation import ActionPreservationExtractor
from ModelInquisitor.extractors.causality import CausalityExtractor
from ModelInquisitor.extractors.concurrency_semantics import ConcurrencySemanticsExtractor
from ModelInquisitor.extractors.deadlock import DeadlockFreedomExtractor
from ModelInquisitor.extractors.mutex import MutexExtractor
from ModelInquisitor.extractors.necessary_response import NecessaryResponseExtractor
from ModelInquisitor.extractors.subprocess_boundary import (
    BoundaryEventLifecycleExtractor,
    SubprocessExpansionExtractor,
)


def extract_claims(model: BPMNModel) -> list[Claim]:
    claims: list[Claim] = []
    for extractor in (
        DeadlockFreedomExtractor(),
        ActionPreservationExtractor(),
        CausalityExtractor(),
        MutexExtractor(),
        BoundaryEventLifecycleExtractor(),
        SubprocessExpansionExtractor(),
        NecessaryResponseExtractor(),
        ConcurrencySemanticsExtractor(),
    ):
        claims.extend(extractor.extract(model))
    return claims


__all__ = [
    "ActionPreservationExtractor",
    "BoundaryEventLifecycleExtractor",
    "CausalityExtractor",
    "ConcurrencySemanticsExtractor",
    "DeadlockFreedomExtractor",
    "MutexExtractor",
    "NecessaryResponseExtractor",
    "SubprocessExpansionExtractor",
    "extract_claims",
]
