"""Claim extractors."""

from ModelInquisitor.core.models import BPMNModel, Claim
from ModelInquisitor.extractors.causality import CausalityExtractor
from ModelInquisitor.extractors.deadlock import DeadlockFreedomExtractor
from ModelInquisitor.extractors.message_synchronization import MessageSynchronizationExtractor
from ModelInquisitor.extractors.mutex import MutexExtractor
from ModelInquisitor.extractors.necessary_response import NecessaryResponseExtractor


def extract_claims(model: BPMNModel) -> list[Claim]:
    claims: list[Claim] = []
    for extractor in (
        DeadlockFreedomExtractor(),
        CausalityExtractor(),
        MessageSynchronizationExtractor(),
        MutexExtractor(),
        NecessaryResponseExtractor(),
    ):
        claims.extend(extractor.extract(model))
    return claims


__all__ = [
    "CausalityExtractor",
    "DeadlockFreedomExtractor",
    "MessageSynchronizationExtractor",
    "MutexExtractor",
    "NecessaryResponseExtractor",
    "extract_claims",
]
