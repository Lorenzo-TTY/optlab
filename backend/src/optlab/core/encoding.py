from __future__ import annotations

import math
from typing import Any

from .models import VariableSpec


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def encode_variables(variables: list[VariableSpec], raw: dict[str, Any]) -> list[float]:
    encoded: list[float] = []
    for variable in variables:
        if variable.name not in raw:
            if variable.default is None:
                raise ValueError(f"missing variable '{variable.name}'")
            value = variable.default
        else:
            value = raw[variable.name]

        if variable.type in {"float", "int"}:
            lower = float(variable.lower)
            upper = float(variable.upper)
            number = float(value)
            if variable.scale == "log":
                number = math.log(number)
                lower = math.log(lower)
                upper = math.log(upper)
            encoded.append(_clamp((number - lower) / (upper - lower)))
        elif variable.type == "categorical":
            choices = list(variable.choices or [])
            if value not in choices:
                raise ValueError(f"invalid choice for '{variable.name}'")
            denominator = max(1, len(choices) - 1)
            encoded.append(choices.index(value) / denominator)
        elif variable.type == "bool":
            encoded.append(1.0 if bool(value) else 0.0)
        else:  # pragma: no cover - guarded by pydantic literals
            raise ValueError(f"unsupported variable type '{variable.type}'")
    return encoded


def decode_vector(variables: list[VariableSpec], vector: list[float] | tuple[float, ...]) -> dict[str, Any]:
    if len(vector) != len(variables):
        raise ValueError("encoded vector length does not match variables")

    decoded: dict[str, Any] = {}
    for variable, encoded_value in zip(variables, vector):
        value = _clamp(float(encoded_value))
        if variable.type == "float":
            lower = float(variable.lower)
            upper = float(variable.upper)
            if variable.scale == "log":
                decoded[variable.name] = math.exp(math.log(lower) + value * (math.log(upper) - math.log(lower)))
            else:
                decoded[variable.name] = lower + value * (upper - lower)
        elif variable.type == "int":
            lower = int(variable.lower)
            upper = int(variable.upper)
            decoded[variable.name] = int(round(lower + value * (upper - lower)))
            decoded[variable.name] = max(lower, min(upper, decoded[variable.name]))
        elif variable.type == "categorical":
            choices = list(variable.choices or [])
            index = int(round(value * max(1, len(choices) - 1)))
            decoded[variable.name] = choices[max(0, min(len(choices) - 1, index))]
        elif variable.type == "bool":
            decoded[variable.name] = value >= 0.5
    return decoded

