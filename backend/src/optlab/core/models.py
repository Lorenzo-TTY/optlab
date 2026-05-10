from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VariableType = Literal["float", "int", "categorical", "bool"]
ScaleType = Literal["linear", "log"]
ObjectiveDirection = Literal["min", "max"]
ConstraintKind = Literal["ineq", "eq"]
ConstraintSeverity = Literal["hard", "soft"]
EvaluatorType = Literal["builtin", "python", "http"]
AlgorithmName = Literal["auto", "random", "ga", "nsga2", "nsga3", "rvea"]


class VariableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: VariableType
    lower: float | int | None = None
    upper: float | int | None = None
    choices: list[Any] | None = None
    scale: ScaleType = "linear"
    default: Any | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("variable name must not be empty")
        return value

    @model_validator(mode="after")
    def validate_bounds_or_choices(self) -> "VariableSpec":
        if self.type in {"float", "int"}:
            if self.lower is None or self.upper is None:
                raise ValueError(f"{self.type} variable '{self.name}' requires lower and upper")
            if float(self.lower) >= float(self.upper):
                raise ValueError(f"variable '{self.name}' lower must be less than upper")
            if self.scale == "log" and (float(self.lower) <= 0 or float(self.upper) <= 0):
                raise ValueError(f"log variable '{self.name}' requires positive bounds")
        if self.type == "categorical":
            if not self.choices:
                raise ValueError(f"categorical variable '{self.name}' requires choices")
            if len(set(map(str, self.choices))) != len(self.choices):
                raise ValueError(f"categorical variable '{self.name}' choices must be unique")
        return self


class ObjectiveSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    direction: ObjectiveDirection = "min"
    unit: str | None = None
    weight: float | None = None
    threshold: float | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("objective name must not be empty")
        return value


class ConstraintSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: ConstraintKind = "ineq"
    severity: ConstraintSeverity = "hard"
    tolerance: float = 0.0

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("constraint name must not be empty")
        return value


class EvaluatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: EvaluatorType
    name: str | None = None
    module_path: str | None = None
    function_name: str = "evaluate"
    url: str | None = None
    timeout_seconds: float = Field(default=10.0, gt=0.0)
    max_retries: int = Field(default=0, ge=0, le=5)

    @model_validator(mode="after")
    def validate_evaluator_fields(self) -> "EvaluatorSpec":
        if self.type == "builtin" and not self.name:
            raise ValueError("builtin evaluator requires name")
        if self.type == "python" and not self.module_path:
            raise ValueError("python evaluator requires module_path")
        if self.type == "http" and not self.url:
            raise ValueError("http evaluator requires url")
        return self


class BudgetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_evals: int = Field(default=200, ge=1, le=5000)
    seed: int = Field(default=1, ge=0)
    max_generations: int | None = Field(default=None, ge=1)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    objectives: dict[str, float]
    constraints: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("objectives", "constraints")
    @classmethod
    def values_must_be_finite(cls, value: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for key, raw in value.items():
            number = float(raw)
            if number != number or number in {float("inf"), float("-inf")}:
                raise ValueError(f"{key} must be finite")
            normalized[key] = number
        return normalized


class ProblemSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variables: list[VariableSpec]
    objectives: list[ObjectiveSpec]
    constraints: list[ConstraintSpec] = Field(default_factory=list)
    evaluator: EvaluatorSpec
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    algorithm: AlgorithmName = "auto"

    @model_validator(mode="after")
    def validate_problem_shape(self) -> "ProblemSpec":
        if not self.variables:
            raise ValueError("problem requires at least one variable")
        if len(self.variables) > 30:
            raise ValueError("problem supports at most 30 variables in v1")
        if not self.objectives:
            raise ValueError("problem requires at least one objective")
        if len(self.objectives) > 6:
            raise ValueError("problem supports at most 6 objectives in v1")
        self._validate_unique([item.name for item in self.variables], "variable")
        self._validate_unique([item.name for item in self.objectives], "objective")
        self._validate_unique([item.name for item in self.constraints], "constraint")
        if self.algorithm == "nsga3" and len(self.objectives) < 4:
            raise ValueError("nsga3 is reserved for 4 to 6 objectives")
        if self.algorithm == "rvea" and len(self.objectives) < 4:
            raise ValueError("rvea is reserved for 4 to 6 objectives")
        if self.algorithm == "nsga2" and len(self.objectives) > 3:
            raise ValueError("nsga2 is reserved for up to 3 objectives")
        return self

    @staticmethod
    def _validate_unique(values: list[str], label: str) -> None:
        if len(set(values)) != len(values):
            raise ValueError(f"{label} names must be unique")

    @property
    def objective_names(self) -> list[str]:
        return [objective.name for objective in self.objectives]

    @property
    def variable_names(self) -> list[str]:
        return [variable.name for variable in self.variables]

    def selected_algorithm(self) -> str:
        if self.algorithm != "auto":
            return self.algorithm
        if len(self.objectives) == 1:
            return "ga"
        if len(self.objectives) <= 3:
            return "nsga2"
        return "nsga3"

    def to_minimized_objectives(self, objectives: dict[str, float]) -> list[float]:
        minimized: list[float] = []
        for objective in self.objectives:
            if objective.name not in objectives:
                raise ValueError(f"missing objective '{objective.name}'")
            value = float(objectives[objective.name])
            minimized.append(value if objective.direction == "min" else -value)
        return minimized

    def hard_constraint_values(self, constraints: dict[str, float]) -> list[float]:
        values: list[float] = []
        for constraint in self.constraints:
            if constraint.severity != "hard":
                continue
            raw = float(constraints.get(constraint.name, 0.0))
            if constraint.kind == "eq":
                values.append(abs(raw) - constraint.tolerance)
            else:
                values.append(raw - constraint.tolerance)
        return values

    def is_feasible(self, constraints: dict[str, float]) -> bool:
        return all(value <= 0.0 for value in self.hard_constraint_values(constraints))
