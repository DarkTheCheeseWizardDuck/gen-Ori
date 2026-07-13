# Intent Benchmark

## Purpose

This benchmark evaluates the ability of an Intent Model to extract semantic information from natural language origami requests.

It is intended to compare different prompt and schema designs under the same set of input requests.

---

## Directory Structure

```
benchmark/
└── intent/
    ├── easy.json
    ├── medium.json
    └── README.md
```

- **easy.json**
  - Simple, explicit requests.

- **medium.json**
  - More descriptive requests.
  - May contain poses, attributes, or richer/vaguer natural language.


## Benchmark Format

Each benchmark file contains a list of test cases.

Example:

```json
[
    {
        "id": "E001",
        "description": "Single explicit animal.",
        "input": "I want an intermediate cat."
    },
    {
        "id": "E002",
        "description": "Single object with explicit pose.",
        "input": "I want a rabbit sitting on its hind legs."
    }
]
```

Only the natural language request is provided.


## Evaluation

Each implementation should process every benchmark request using its own:

- prompt
- schema

The resulting outputs are then evaluated using a common evaluation rubric.

Possible evaluation criteria include:

- Valid JSON
- Follows its own schema
- Correct object extraction
- Correct difficulty extraction
- Correct semantic decomposition
- No hallucinated information
- Consistent naming
- Suitable for downstream processing

Because of differently designed schemas, the benchmark does not prescribe a single expected JSON output.

---

## Design Principles

The benchmark should:

- Cover a wide variety of natural language expressions.
- Gradually increase linguistic complexity.
- Remain independent of any specific schema.
- Remain independent of any particular LLM.
- Focus on semantic understanding rather than origami knowledge.

The benchmark is intended to remain stable while prompts and schemas evolve over time.