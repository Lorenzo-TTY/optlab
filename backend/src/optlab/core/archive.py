from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def dominates(left: list[float], right: list[float], eps: float = 1e-12) -> bool:
    return all(a <= b + eps for a, b in zip(left, right)) and any(a < b - eps for a, b in zip(left, right))


@dataclass(slots=True)
class CandidateRecord:
    candidate_id: str
    generation: int
    variables: dict[str, Any]
    objectives: dict[str, float]
    minimized: list[float]
    constraints: dict[str, float]
    feasible: bool
    error: str | None = None
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ParetoArchive:
    def __init__(self) -> None:
        self.records: list[CandidateRecord] = []

    def add(self, record: CandidateRecord) -> None:
        self.records.append(record)

    def rank_zero(self) -> list[CandidateRecord]:
        feasible = [record for record in self.records if record.feasible and record.error is None]
        front: list[CandidateRecord] = []
        for candidate in feasible:
            if not any(
                other is not candidate and dominates(other.minimized, candidate.minimized)
                for other in feasible
            ):
                front.append(candidate)
        return front

    def best_per_objective(self, objective_names: list[str]) -> dict[str, float | None]:
        feasible = [record for record in self.records if record.feasible and record.error is None]
        best: dict[str, float | None] = {}
        for index, name in enumerate(objective_names):
            values = [record.objectives[name] for record in feasible if name in record.objectives]
            best[name] = min(values) if values else None
        return best

    def feasible_count(self) -> int:
        return sum(1 for record in self.records if record.feasible and record.error is None)

    def to_payload(self) -> dict[str, Any]:
        return {
            "evaluations": [record_to_payload(record) for record in self.records],
            "paretoFront": [record_to_payload(record) for record in self.rank_zero()],
        }


def record_to_payload(record: CandidateRecord) -> dict[str, Any]:
    return {
        "candidateId": record.candidate_id,
        "generation": record.generation,
        "variables": record.variables,
        "objectives": record.objectives,
        "minimized": record.minimized,
        "constraints": record.constraints,
        "feasible": record.feasible,
        "error": record.error,
        "elapsedMs": record.elapsed_ms,
        "metadata": record.metadata,
    }

