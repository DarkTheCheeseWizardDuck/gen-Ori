import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from structure import extractor
from structure import length_assign


def response_with(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def valid_structure_json() -> str:
    return json.dumps(valid_structure())


def valid_structure() -> dict:
    return {
        "schema_version": "genori.structure.v1",
        "intent": {"object": "cat"},
        "structure": {
            "parts": [
                {
                    "id": "body_1",
                    "name": "body",
                    "length_weight": None,
                    "segment_index": 1,
                    "symmetry": None,
                }
            ]
        },
    }


class ExtractorRetryTests(unittest.TestCase):
    def test_retries_once_after_invalid_json(self) -> None:
        invalid = response_with('{"schema_version": "genori.structure.v1"')
        valid = response_with(valid_structure_json())

        with patch.object(extractor.client.chat.completions, "create", side_effect=[invalid, valid]) as create:
            result = extractor.extract_structure("a cat")

        self.assertEqual(result["intent"]["object"], "cat")
        self.assertEqual(create.call_count, 2)
        repair_messages = create.call_args_list[1].kwargs["messages"]
        self.assertIn("Your previous response was rejected", repair_messages[-1]["content"])
        self.assertIn("invalid JSON", repair_messages[-1]["content"])

    def test_stops_after_three_invalid_responses(self) -> None:
        invalid = response_with("not json")

        with patch.object(extractor.client.chat.completions, "create", side_effect=[invalid, invalid, invalid]) as create:
            with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
                extractor.extract_structure("a cat")

        self.assertEqual(create.call_count, 3)

    def test_does_not_retry_api_failures(self) -> None:
        with patch.object(extractor.client.chat.completions, "create", side_effect=Exception("connection failed")) as create:
            with self.assertRaisesRegex(RuntimeError, "attempt 1"):
                extractor.extract_structure("a cat")

        self.assertEqual(create.call_count, 1)

    def test_length_assignment_retries_once_after_invalid_json(self) -> None:
        weighted = valid_structure()
        weighted["structure"]["parts"][0]["length_weight"] = 0.5

        with patch.object(
            length_assign.client.chat.completions,
            "create",
            side_effect=[response_with("not json"), response_with(json.dumps(weighted))],
        ) as create:
            result = length_assign.assign_length_weights(valid_structure())

        self.assertEqual(result["structure"]["parts"][0]["length_weight"], 0.5)
        self.assertEqual(create.call_count, 2)
        self.assertIn("change only length_weight", create.call_args_list[1].kwargs["messages"][-1]["content"])

    def test_length_assignment_stops_after_three_invalid_responses(self) -> None:
        invalid = response_with("not json")

        with patch.object(
            length_assign.client.chat.completions,
            "create",
            side_effect=[invalid, invalid, invalid],
        ) as create:
            with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
                length_assign.assign_length_weights(valid_structure())

        self.assertEqual(create.call_count, 3)


if __name__ == "__main__":
    unittest.main()
