# Intent Model Evaluation Rubric

## Purpose

This rubric is used to evaluate the quality of the Intent Model's output.

The evaluation focuses on semantic extraction rather than origami knowledge.

Each benchmark case is evaluated independently.

---

## Scoring

Each criterion is scored using the following scale:

| Score | Meaning |
|-------:|---------|
| 2 | Fully satisfies the criterion |
| 1 | Partially satisfies the criterion |
| 0 | Does not satisfy the criterion |

---

# Evaluation Criteria

## 1. JSON Validity

Does the model produce valid JSON?

Score:

- 2 = Valid JSON
- 0 = Invalid JSON

---

## 2. Schema Compliance

Does the output follow its own schema?

Examples:

- required fields exist
- correct data types
- no unexpected structure

Score:

- 2 = Fully compliant
- 1 = Minor violations
- 0 = Major violations

---

## 3. Intent Extraction

Does the model correctly extract the user's requested intent?

Examples:

- object
- difficulty
- constraints

Score:

- 2 = All extracted correctly
- 1 = Minor mistakes
- 0 = Incorrect

---

## 4. Structure Completeness

Does the structure include all major semantic parts naturally implied by the object?

Example:

Cat

✓ body
✓ head
✓ ears
✓ legs
✓ tail

Score:

- 2 = Complete
- 1 = Missing minor parts
- 0 = Missing major parts

---

## 5. Hallucination

Did the model invent information that was not implied by the request?

Examples:

Bad:

- adds wings to a cat
- invents accessories
- invents origami hierarchy

Good:

- infers four legs for a cat
- infers ears for a rabbit

Score:

- 2 = No hallucination
- 1 = Minor unnecessary inference
- 0 = Significant hallucination

---
# Overall Score

Maximum Score

14

Suggested Interpretation

| Score | Interpretation |
|--------:|----------------|
| 9-10 | Good |
| 5–8 | Acceptable |
| <5 | Needs Improvement |

---

# Notes

Record any recurring observations that are not captured by the numeric score.

Examples:

- Frequently misses hind legs.
- Sometimes assigns incorrect symmetry groups.
- Overuses generic part names.
- Difficulty extraction is unreliable.