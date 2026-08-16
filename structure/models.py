"""Canonical, validated contract for Genori's structure-extraction stage."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, model_validator


MAX_LENGTH_WEIGHT = math.sqrt(2)
LengthWeight = Annotated[float, Field(gt=0, le=MAX_LENGTH_WEIGHT)]


class StructureValidationError(ValueError):
    """Raised when a payload is not a valid Genori structure.v1 document."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IntentV1(StrictModel):
    object: Annotated[str, Field(min_length=1, max_length=160)]


class SymmetryV1(StrictModel):
    group: Annotated[str, Field(min_length=1, max_length=80)]
    side: Literal["left", "right", "center"]
    order_index: Annotated[int, Field(ge=1, le=8)]


class PartV1(StrictModel):
    id: Annotated[str, Field(min_length=1, max_length=80)]
    name: Annotated[str, Field(min_length=1, max_length=80)]
    length_weight: LengthWeight | None
    segment_index: Annotated[int, Field(ge=1, le=3)] | None
    symmetry: SymmetryV1 | None


class StructureBodyV1(StrictModel):
    parts: Annotated[list[PartV1], Field(min_length=1, max_length=32)]


class StructureV1(StrictModel):
    """The LLM-facing semantic contract. Topology deliberately does not live here."""

    schema_version: Literal["genori.structure.v1"]
    intent: IntentV1
    structure: StructureBodyV1

    @model_validator(mode="after")
    def validate_part_relationships(self, info: ValidationInfo) -> "StructureV1":
        parts = self.structure.parts
        ids = [part.id for part in parts]
        duplicate_ids = sorted({part_id for part_id in ids if ids.count(part_id) > 1})
        if duplicate_ids:
            raise ValueError(f"part ids must be unique; duplicates: {', '.join(duplicate_ids)}")

        body_parts = [part for part in parts if part.name == "body"]
        non_body_segmented = [part.id for part in parts if part.name != "body" and part.segment_index is not None]
        if non_body_segmented:
            raise ValueError(
                "segment_index is reserved for body parts; found it on: " + ", ".join(non_body_segmented)
            )

        body_with_symmetry = [part.id for part in body_parts if part.symmetry is not None]
        if body_with_symmetry:
            raise ValueError("body parts cannot belong to a symmetry group: " + ", ".join(body_with_symmetry))

        if len(body_parts) > 1:
            indexes = [part.segment_index for part in body_parts]
            if any(index is None for index in indexes):
                raise ValueError("segmented bodies require segment_index on every body part")
            if sorted(indexes) != list(range(1, len(body_parts) + 1)):
                raise ValueError("body segment_index values must be consecutive, starting at 1")
        elif len(body_parts) == 1 and body_parts[0].segment_index not in (None, 1):
            raise ValueError("a single body part may have segment_index null or 1 only")

        groups: dict[tuple[str, int], list[PartV1]] = {}
        for part in parts:
            if part.symmetry is not None:
                key = (part.symmetry.group, part.symmetry.order_index)
                groups.setdefault(key, []).append(part)

        require_length_weights = bool((info.context or {}).get("require_length_weights"))
        if require_length_weights and any(part.length_weight is None for part in parts):
            raise ValueError("length_weight is required after the length-assignment stage")

        for (group, order_index), members in groups.items():
            left = [part for part in members if part.symmetry and part.symmetry.side == "left"]
            right = [part for part in members if part.symmetry and part.symmetry.side == "right"]
            center = [part for part in members if part.symmetry and part.symmetry.side == "center"]

            if left or right:
                if len(left) != 1 or len(right) != 1 or center:
                    raise ValueError(
                        f"symmetry group '{group}' at order_index {order_index} must contain exactly one left and one right part"
                    )
                if require_length_weights and not math.isclose(
                    left[0].length_weight or 0.0,
                    right[0].length_weight or 0.0,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ):
                    raise ValueError(
                        f"symmetric parts '{left[0].id}' and '{right[0].id}' must have identical length_weight"
                    )

        return self


def _validation_message(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(item) for item in entry['loc'])}: {entry['msg']}" for entry in error.errors()
    )


def validate_structure(payload: object, *, require_length_weights: bool = False) -> dict:
    """Validate and return a JSON-safe canonical structure.v1 dictionary."""

    try:
        model = StructureV1.model_validate(payload, context={"require_length_weights": require_length_weights})
    except ValidationError as error:
        raise StructureValidationError(_validation_message(error)) from error
    return model.model_dump(mode="json")


def validate_length_assignment(original: object, candidate: object) -> dict:
    """Allow the length model to change only length_weight values."""

    try:
        original_model = StructureV1.model_validate(original)
        candidate_model = StructureV1.model_validate(candidate, context={"require_length_weights": True})
    except ValidationError as error:
        raise StructureValidationError(_validation_message(error)) from error

    if candidate_model.intent != original_model.intent:
        raise StructureValidationError("length assignment must not modify intent")

    original_parts = original_model.structure.parts
    candidate_parts = candidate_model.structure.parts
    if len(candidate_parts) != len(original_parts):
        raise StructureValidationError("length assignment must not add or remove parts")

    for before, after in zip(original_parts, candidate_parts):
        if (
            before.id,
            before.name,
            before.segment_index,
            before.symmetry,
        ) != (
            after.id,
            after.name,
            after.segment_index,
            after.symmetry,
        ):
            raise StructureValidationError(
                f"length assignment may only modify length_weight; changed part '{before.id}'"
            )

    return candidate_model.model_dump(mode="json")
