import unittest
import json
from pathlib import Path

from structure.models import StructureV1, StructureValidationError, validate_length_assignment, validate_structure


def valid_structure() -> dict:
    return {
        "schema_version": "genori.structure.v1",
        "intent": {"object": "cat"},
        "structure": {
            "parts": [
                {"id": "body_1", "name": "body", "length_weight": None, "segment_index": 1, "symmetry": None},
                {"id": "head", "name": "head", "length_weight": None, "segment_index": None, "symmetry": None},
                {
                    "id": "leg_1_L",
                    "name": "leg",
                    "length_weight": None,
                    "segment_index": None,
                    "symmetry": {"group": "leg", "side": "left", "order_index": 1},
                },
                {
                    "id": "leg_1_R",
                    "name": "leg",
                    "length_weight": None,
                    "segment_index": None,
                    "symmetry": {"group": "leg", "side": "right", "order_index": 1},
                },
            ]
        },
    }


class StructureModelTests(unittest.TestCase):
    def test_committed_json_schema_matches_pydantic_model(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "structure" / "schema.json"
        self.assertEqual(json.loads(schema_path.read_text(encoding="utf-8")), StructureV1.model_json_schema())

    def test_valid_unweighted_structure(self) -> None:
        payload = validate_structure(valid_structure())
        self.assertEqual(payload["schema_version"], "genori.structure.v1")
        self.assertEqual(len(payload["structure"]["parts"]), 4)

    def test_rejects_missing_schema_version(self) -> None:
        payload = valid_structure()
        del payload["schema_version"]
        with self.assertRaises(StructureValidationError):
            validate_structure(payload)

    def test_rejects_duplicate_part_ids(self) -> None:
        payload = valid_structure()
        payload["structure"]["parts"][1]["id"] = "body_1"
        with self.assertRaises(StructureValidationError):
            validate_structure(payload)

    def test_rejects_unpaired_bilateral_part(self) -> None:
        payload = valid_structure()
        payload["structure"]["parts"].pop()
        with self.assertRaises(StructureValidationError):
            validate_structure(payload)

    def test_rejects_non_body_segment_index(self) -> None:
        payload = valid_structure()
        payload["structure"]["parts"][1]["segment_index"] = 1
        with self.assertRaises(StructureValidationError):
            validate_structure(payload)

    def test_weighted_structure_requires_all_lengths_and_equal_pairs(self) -> None:
        payload = valid_structure()
        for part in payload["structure"]["parts"]:
            part["length_weight"] = 0.4 if part["name"] == "body" else 0.2
        validated = validate_structure(payload, require_length_weights=True)
        self.assertEqual(validated["structure"]["parts"][2]["length_weight"], 0.2)

        payload["structure"]["parts"][3]["length_weight"] = 0.3
        with self.assertRaises(StructureValidationError):
            validate_structure(payload, require_length_weights=True)

    def test_length_assignment_cannot_mutate_topology_fields(self) -> None:
        original = valid_structure()
        candidate = valid_structure()
        for part in candidate["structure"]["parts"]:
            part["length_weight"] = 0.4 if part["name"] == "body" else 0.2
        candidate["structure"]["parts"][1]["name"] = "tail"
        with self.assertRaises(StructureValidationError):
            validate_length_assignment(original, candidate)


if __name__ == "__main__":
    unittest.main()
