# Genori

Genori is a Windows-first research pipeline that turns an origami request into:

1. a user-reviewed semantic structure,
2. a deterministic weighted flap tree,
3. deterministic TreeMaker jobs and boundary seeds,
4. a headless TreeMaker result, and
5. a crease-pattern SVG and FOLD file when the native result is complete.

The current production path is intentionally split between model-authored
semantics and code-owned geometry. Groq is used for the reviewable plan and
genori.structure.v2 extraction. Pydantic validates that response. Numeric
lengths, topology, seed layouts, feasibility reports, TreeMaker execution,
SVG rendering, and FOLD conversion are deterministic.

This repository also contains an older experimental TAN directory. TAN is not
the default path and does not currently have a saved-checkpoint interface
connected to the Genori pipeline.

## System at a glance

~~~text
Natural-language request
        |
        v
LLM: reviewable Markdown structure plan
        |
        v
User approval or feedback
        |
        v
LLM: strict genori.structure.v2 JSON
        |
        v
Pydantic validation and bounded JSON retry
        |
        v
Deterministic semantic feasibility
        |
        v
Deterministic size_class -> numeric length_weight
        |
        v
Deterministic topology.v2
        |
        v
Deterministic TreeMaker job candidates and seeds
        |
        v
Headless native TreeMaker
        |
        +--> full_cp + valid square perimeter -> SVG + FOLD
        |
        +--> partial/invalid/infrastructure result -> diagnostics or preview
~~~

The LLM does not generate parent IDs, graph edges, coordinates, crease
assignments, or TreeMaker geometry. If a downstream semantic failure is
repairable, Genori can ask the LLM for a complete replacement plan, but the
user must approve it. Replay from a saved structure does not call the LLM or
perform semantic repair.

## Repository map

| Path | Responsibility |
| --- | --- |
| structure/ | Groq extraction, review planning, Pydantic contracts, feasibility, and the main pipeline |
| topology/ | Deterministic structure.v2 -> topology.v2 compilation |
| treemaker_job/ | Deterministic TreeMaker job contracts, square-boundary supports, and seed candidates |
| treemaker_runtime/ | Native runner execution, result validation, square-perimeter validation, SVG, and FOLD export |
| native/treemaker_runner/ | Headless C++ bridge around the TreeMaker model |
| scripts/build_treemaker_runner.ps1 | Builds the native runner |
| tools/svg_to_fold/ | Local Node.js wrapper around tofold, fold, and svg-segmentize |
| tree graph generator/ | Experimental TAN code and dataset utilities; not the current production path |
| tests/ | Python and Node regression tests |
| docs/ | More detailed intent, topology, and system contracts |

## Requirements

For the complete pipeline on Windows, install:

- Python 3.11 or 3.12
- Node.js and npm
- CMake 3.20 or newer
- Visual Studio 2022 with the Desktop development with C++ workload
- A local TreeMaker source checkout
- A Groq API key and a Groq model enabled for the account

The native build script uses the Visual Studio 17 2022 x64 CMake generator.
During configuration, CMake fetches the nlohmann_json dependency, so the
first native build needs network access.

## Setup

Run the following from the repository root: the directory containing this
README.md, structure/, topology/, and treemaker_runtime/.

### 1. Create a Python environment

~~~powershell
# Run this terminal from the repository root.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
~~~

If PowerShell blocks activation, use a process-scoped policy change for the
current terminal:

~~~powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
~~~

The Python requirements are listed in requirements.txt.

### 2. Install the SVG-to-FOLD dependencies

The converter is a local Node package under tools/svg_to_fold; it is not a
separate executable that must be downloaded.

~~~powershell
npm.cmd --prefix tools/svg_to_fold install
~~~

The package uses the dependencies declared in
tools/svg_to_fold/package.json. The full pipeline invokes
tools/svg_to_fold/convert.cjs automatically after a certified SVG is written.

### 3. Create the Groq environment file

The extractor loads .env from the repository root. This file is ignored by
Git; keep the API key private and do not commit it.

~~~powershell
notepad .env
~~~

Use a model name that is enabled for your Groq account. For example:

~~~env
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_REASONING_EFFORT=low
GROQ_MAX_COMPLETION_TOKENS=4096
~~~

The variables are:

| Variable | Required | Meaning |
| --- | --- | --- |
| GROQ_API_KEY | yes for natural-language mode | Groq authentication |
| GROQ_MODEL | yes for natural-language mode | Model passed to Groq |
| GROQ_REASONING_EFFORT | no | Groq reasoning effort; defaults to high in code |
| GROQ_MAX_COMPLETION_TOKENS | no | Maximum completion size; defaults to 4096 in code |

The completion limit applies to both the planning and structure-extraction
calls. A larger value also increases the request size and can trigger Groq's
TPM limit. If Groq returns HTTP 413 for a request that is over the account
limit, reduce this value and/or use a lower reasoning effort; increasing it is
not a reliable fix.

### 4. Prepare the TreeMaker source

By default, the build script looks for a sibling checkout at ..\treemaker,
meaning a treemaker directory next to the Genori repository. The source must
contain Source\tmModel\tmModel.h and must be at the pinned commit:

~~~text
b100fe0f164dec276cac1744a8f75ae55674e175
~~~

Check it before building:

~~~powershell
Test-Path ..\treemaker\Source\tmModel\tmModel.h
git -C ..\treemaker rev-parse HEAD
~~~

If the checkout is elsewhere, pass its path explicitly:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_treemaker_runner.ps1 -TreeMakerSource "C:\path\to\treemaker"
~~~

The script rejects an unpinned checkout by default. Only use
-AllowUnpinnedSource when deliberately testing another revision:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_treemaker_runner.ps1 -TreeMakerSource "C:\path\to\treemaker" -AllowUnpinnedSource
~~~

### 5. Build the headless runner

~~~powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_treemaker_runner.ps1
~~~

The expected main executable is:

~~~text
build\treemaker_runner\Release\genori_treemaker_runner.exe
~~~

The runtime also accepts an explicit runner path through the process
environment:

~~~powershell
$env:GENORI_TREEMAKER_RUNNER = (Resolve-Path ".\build\treemaker_runner\Release\genori_treemaker_runner.exe").Path
~~~

The command-line --runner option takes precedence and is easier to audit.

The build also creates
build\treemaker_runner\Release\genori_treemaker_reference_probe.exe for
diagnosing native TreeMaker reference files. CMake patches a copied source
tree under build\treemaker_runner\treemaker_source; the external TreeMaker
checkout is not modified. The linked TreeMaker code is GPLv2, so retain its
license and source obligations when distributing the runner.

## Run the complete Genori pipeline

Run these commands from the repository root.

### Interactive natural-language run

~~~powershell
py -m structure.pipeline
~~~

The program asks for the origami request, prints a proposed Markdown plan,
and asks:

~~~text
Do you want to adjust the plan? Enter your feedback, or type 'yes' to approve:
~~~

Type yes to approve. Otherwise enter feedback; the planner returns another
complete plan. After approval, Genori extracts the final structure JSON,
validates it, compiles the deterministic stages, runs TreeMaker, and prints
the final result as JSON.

To choose an explicit artifact root:

~~~powershell
py -m structure.pipeline --output-root .\results\treemaker
~~~

The default is already .\results\treemaker when run from the repository root.
No object name or special flag is required for the normal interactive path.

### Important Windows module-path rule

py -m structure.pipeline must be run from the repository root, because
structure is a package relative to that directory.

If the current directory is the repository's structure directory, run:

~~~powershell
py pipeline.py
~~~

Do not use py -m pipeline.py, py -m pipeline..py, or py pipeline..py. Python
module names do not include .py.

### Compile without running native TreeMaker

This is useful for inspecting the structure, topology, job, and seed
contracts:

~~~powershell
py -m structure.pipeline --job-only
~~~

The job-only run still uses Groq in interactive mode. It stops after
treemaker-job.v2 compilation and does not require the native executable.

### Replay a saved structure without Groq

Replay accepts both genori.structure.v1 and genori.structure.v2. A valid v1
file is upgraded deterministically to v2.

~~~powershell
py -m structure.pipeline --from-structure ".\results\treemaker\<object>-<timestamp>\structure.json"
~~~

Replay and compile only:

~~~powershell
py -m structure.pipeline --from-structure ".\path\to\structure.json" --job-only
~~~

Replay does not show the plan-review loop, call Groq, or draft a semantic
repair. This makes it the reproducible path for testing saved structure
inputs.

### Use an explicit runner path or timeout

The default runner path is
build\treemaker_runner\Release\genori_treemaker_runner.exe. Override it when
testing another build:

~~~powershell
py -m structure.pipeline --runner ".\build\treemaker_runner\Release\genori_treemaker_runner.exe" --timeout 120
~~~

The timeout is a shared deadline for the ranked candidate jobs, not an
independent unlimited timeout for every candidate.

### Square-paper mode

Square-boundary mode is enabled by default. The explicit form is:

~~~powershell
py -m structure.pipeline --square-boundary
~~~

In this mode:

- the job asks TreeMaker to place four usable leaves at the four physical
  paper corners;
- if the semantic tree has too few usable leaves, the deterministic compiler
  adds the minimum number of declared sacrificial support branches;
- support branches are real TreeMaker job edges in scaffold candidates, not
  fake lines added only to the SVG;
- the original structure.json and topology.json are not changed;
- up to 24 deterministic candidates are ranked and executed under one
  timeout;
- the zero-support semantic job is preferred when it already produces a
  valid result;
- a native result is exportable in square mode only when black border creases
  cover all four physical paper sides and no interior black border is present.

The support scaffold makes a simple semantic model feasible on square paper;
it does not add recognizable model anatomy. It is a boundary and
triangulation aid owned by the compiler.

To deliberately bypass the square-paper requirement for diagnosis:

~~~powershell
py -m structure.pipeline --no-square-boundary
~~~

This may produce a non-square boundary result. It is not the correct option
when square paper is non-negotiable.

### Preview partial native geometry

~~~powershell
py -m structure.pipeline --preview-partial
~~~

If TreeMaker returns partial geometry, this writes
crease-pattern-preview.svg. It is an inspection drawing only. It is not a
certified crease pattern and is not converted to FOLD.

### Add a visual reference grid

~~~powershell
py -m structure.pipeline --grid-spacing 0.1
~~~

The grid is visual-only and is not part of the TreeMaker result. Do not use
this option when you want a clean SVG for an importer. The FOLD converter also
removes its reference-grid group.

### Limit semantic repair

The default maximum is two approved repair rounds:

~~~powershell
py -m structure.pipeline --max-repair-rounds 2
~~~

Disable semantic repair completely:

~~~powershell
py -m structure.pipeline --max-repair-rounds 0
~~~

Only repairable semantic or native-domain diagnostics can trigger this loop.
Missing runners, timeouts, malformed native output, and other infrastructure
failures are not sent back to the LLM as if they were design problems.

## What each stage does

### 1. Reviewable plan and structure extraction

The planner proposes only physical branches or flaps needed for a
recognizable silhouette. It records:

- intent.object
- descriptive intent.pose
- intent.complexity: simple, balanced, or detailed
- one to three body segments
- physical parts
- bilateral symmetry groups
- size_class
- importance
- attachment_region
- optional merge_group

The final JSON contract is in structure/models.py. It is strict: unknown
fields, duplicate IDs, invalid body segmentation, incomplete bilateral pairs,
and mismatched mirrored metadata are rejected. The extractor retries a
malformed response up to three total attempts with the validation error in
the retry conversation. Reasoning is requested in hidden format so it does
not become part of the JSON payload.

Pydantic proves that the document follows the semantic schema. It cannot prove
that the resulting tree is geometrically packable or physically foldable;
those are later checks.

### 2. Deterministic length assignment

The model chooses a relative size class, not a numeric TreeMaker length.
Missing numeric weights are assigned by this fixed mapping:

| size_class | Weight | Intended use |
| --- | ---: | --- |
| tiny | 0.08 | minor short flap |
| short | 0.15 | secondary flap |
| medium | 0.25 | normal structural flap |
| long | 0.40 | major silhouette flap |
| dominant | 0.60 | visually dominant flap |

On replay, an already validated numeric weight is preserved. The
length-assignment.json artifact records whether each value was size_class
derived or preserved.

### 3. Deterministic topology

topology/compiler.py converts semantic parts into a connected tree:

- body segments form the central body axis;
- head attachments target the head when one exists;
- front_body, mid_body, and rear_body select stable body-axis slots;
- mirrored parts receive matching parents and endpoints;
- v2 records the attachment source for diagnostics.

The current topology compiler does not call an LLM. It does not use the old
TAN model, predict coordinates, or assign crease colors.

### 4. TreeMaker job and seed candidates

treemaker_job/compiler.py converts the weighted topology into a strict
genori.treemaker-job.v2 document. The default paper is 1 by 1 units with a
0.05 margin. It creates deterministic boundary layouts, validates symmetry
and edge lengths, and ranks up to 24 candidate jobs.

TreeMaker seed coordinates are starting positions. TreeMaker remains
responsible for optimization, native feasibility, polygon construction, and
crease generation.

### 5. Native TreeMaker

The C++ runner reads one TreeMaker job JSON document from stdin and writes one
genori.treemaker-result.v2 JSON document to stdout. The Python runtime may run
multiple seeds and candidates, retaining diagnostics for each attempt.

The native result is the sole authority for full_cp and its crease segments.
Genori never turns a visually plausible partial tree preview into a
certified crease pattern.

### 6. SVG and FOLD export

For a native full_cp, Genori writes crease-pattern.svg and then invokes the
local Node converter to write crease-pattern.fold.

The display SVG uses data-fold metadata and these default display styles:

- mountain: red-toned dashed line
- valley: blue-toned solid line
- border: black line
- flat or unknown facet edges: gray dotted line
- optional --grid-spacing grid: pale dotted reference lines

The default pipeline call uses display mode. The gray facet edges are not
random hallucinated creases: TreeMaker can expose flat/unknown facet
boundaries, and the converter preserves flat edges as FOLD F edges so the
simulator mesh remains partitioned. Reference-grid lines are removed by the
converter.

Before conversion, the bundled wrapper normalizes assignments to:

| SVG meaning | FOLD assignment |
| --- | --- |
| mountain / exact red | M |
| valley / exact blue | V |
| flat facet edge | F |
| boundary / exact black | B |
| unknown | U |

The converter removes the white canvas rectangle and visual reference grid,
fragments crossings, derives planar faces, adds fold angles, and validates
the resulting graph before writing the file. It is a local package wrapper,
not a separate Rabbit Ear command-line program.

If an external SVG importer requires exact red/blue/black strokes directly in
the SVG, the lower-level Python API supports
write_svg(..., importer_compatible=True). The current command-line pipeline
uses the display-oriented SVG and relies on the FOLD conversion normalization.

Neither full_cp nor a structurally valid .fold file proves that the semantic
model is recognizable or that a physical sheet will fold as intended. Inspect
the SVG, load the FOLD file in a simulator such as Origami Simulator or ORIPA,
and physically test the result before calling it a usable model.

## Generated artifacts

Each run creates a timestamped directory under results\treemaker\, for
example:

~~~text
results\treemaker\butterfly-20260827T120000000000Z\
~~~

The directory can contain:

| Artifact | Meaning |
| --- | --- |
| approved-plan.txt | The plan approved during an interactive run |
| structure.json | Canonical weighted genori.structure.v2 |
| length-assignment.json | Deterministic weight assignments |
| feasibility-report.json | Stage, metrics, diagnostic codes, and repairability |
| topology.json | Deterministic genori.topology.v2 |
| treemaker-job.json | Selected job after execution, or top-ranked job in job-only mode |
| treemaker-job-candidates.json | All compiled candidate jobs |
| square-boundary-scaffold.json | Support candidates and native candidate outcomes |
| treemaker-result.json | Native TreeMaker result and per-seed diagnostics |
| crease-pattern.svg | Written only for a native full crease pattern |
| crease-pattern.fold | Validated FOLD output paired with the certified SVG |
| crease-pattern-preview.svg | Optional partial native preview from --preview-partial |
| crease-pattern-unavailable.txt | Explanation when no certified SVG/FOLD was produced |
| revisions\01\, revisions\02\ | User-approved semantic repair attempts |

partial_cp, polygon_invalid, tree_infeasible, optimizer_failed, timeout, and
runner_error are diagnostic outcomes, not successful crease-pattern exports.

## Direct stage commands

The main pipeline is the recommended command. These entry points are useful
when debugging individual contracts.

Compile a structure file to topology:

~~~powershell
py -m topology.cli ".\path\to\structure.json" > ".\topology.json"
~~~

The topology CLI accepts v1 or v2 structure JSON. Use the default
deterministic strategy. The learned strategy is intentionally unavailable
until a real saved TAN checkpoint interface is implemented.

Compile a combined weighted structure/topology document to a TreeMaker job:

~~~powershell
py -m treemaker_job.cli ".\path\to\compiled.json" > ".\treemaker-job.json"
~~~

The input must be one JSON object with top-level structure and topology
fields. The structure must already contain validated numeric length_weight
values. The CLI also accepts --square-boundary (default),
--no-square-boundary, --paper-width, --paper-height, and --margin.

Run the bundled SVG converter directly:

~~~powershell
node tools/svg_to_fold/convert.cjs ".\path\to\crease-pattern.svg" ".\path\to\crease-pattern.fold"
~~~

The converter requires the dependencies installed in
tools/svg_to_fold\node_modules.

The native executable can also be used as a diagnostic boundary:

~~~powershell
Get-Content ".\path\to\treemaker-job.json" -Raw | & ".\build\treemaker_runner\Release\genori_treemaker_runner.exe"
~~~

The Python runtime is preferred because it handles candidates, shared
timeouts, validation, ranking, and artifact persistence.

## Python API

The deterministic compiler can be called without Groq when a structure
document is already available:

~~~python
from structure.pipeline import compile_structure_pipeline

compiled = compile_structure_pipeline(
    structure,
    force_square_boundary=True,
)

# compiled contains:
# structure, length_assignment, topology, treemaker_job,
# treemaker_job_candidates, square_boundary_scaffold, feasibility_report
~~~

The end-to-end Python helper is:

~~~python
from structure.pipeline import run_treemaker_pipeline

result = run_treemaker_pipeline(
    "a butterfly",
    output_root="results/treemaker",
    force_square_boundary=True,
)
~~~

This helper uses Groq for the natural-language stages. Use
compile_structure_pipeline or the CLI --from-structure path for deterministic
replay.

## Benchmark evaluation

The structure benchmark evaluates only the natural-language extraction stage;
it does not run topology or TreeMaker. It requires the Groq environment and
writes results under results\structure\.

From the structure directory:

~~~powershell
Set-Location .\structure
py evaluate.py
~~~

The script presents the available JSON benchmarks in benchmark\structure\,
processes every case, and writes a file such as
results\structure\easy_outputs.json. The scoring rubric is in
evaluation\structure\rubric.md.

## Testing

Run the Python tests from the repository root:

~~~powershell
py -m pytest -q
~~~

Run the SVG-to-FOLD package tests:

~~~powershell
npm.cmd --prefix tools/svg_to_fold test
~~~

The native integration tests use the built runner when it is available.
Tests involving the native executable are therefore not a substitute for
opening the resulting FOLD file in a simulator or physically folding it.

## Troubleshooting

### ModuleNotFoundError: No module named 'structure'

You ran the module command from inside the structure directory. Return to the
repository root and use:

~~~powershell
py -m structure.pipeline
~~~

Or stay inside structure and use:

~~~powershell
py pipeline.py
~~~

### GROQ_API_KEY or GROQ_MODEL is missing

Create .env at the repository root, not inside structure, and ensure the
variable names are exact. Replay with --from-structure does not need Groq.

### Groq HTTP 413 / TPM limit

The request is larger than the account's tokens-per-minute allowance. Set a
smaller value, for example:

~~~env
GROQ_REASONING_EFFORT=low
GROQ_MAX_COMPLETION_TOKENS=4096
~~~

If the account limit is lower, reduce the completion cap further. Do not
assume an empty or invalid JSON response means the plan was empty; the model
may have been cut off before producing its JSON response.

### No SVG or FOLD file

Open treemaker-result.json and feasibility-report.json. Genori writes
certified exports only after native TreeMaker returns a non-empty full_cp
and, in square mode, the black border passes all-four-sides perimeter
validation. A partial preview is intentionally not converted to FOLD.

### seed_generation_failed or square-boundary errors

Inspect square-boundary-scaffold.json and the seed rejection metrics in
feasibility-report.json. The candidate compiler tries deterministic layouts
and real support branches before asking for semantic repair. A simple model
can still fail if TreeMaker cannot build a valid polygon network; use
--preview-partial for diagnosis, or use --no-square-boundary only to separate
square-boundary failure from general TreeMaker failure.

### Gray dotted lines in the SVG

There are two possible sources:

- --grid-spacing adds a pale dotted visual reference grid.
- TreeMaker flat or unknown facet edges are rendered gray/dotted in display
  SVG mode.

The converter removes the reference grid but preserves flat facet edges in
the FOLD mesh. These are different from mountain and valley assignments.

### The FOLD file loads but does not fold

FOLD conversion validates graph structure, edge assignments, and face
references. It does not prove flat-foldability, correct mountain/valley
parity, or physical feasibility of the generated design. Check the
per-candidate native diagnostics and test the file in a simulator.

### Native runner build failure

Check all of the following:

1. ..\treemaker\Source\tmModel\tmModel.h exists.
2. The TreeMaker checkout is at the pinned commit.
3. CMake is installed or passed with -CMakePath.
4. Visual Studio 2022 C++ tools are installed.
5. The first configuration can access GitHub to fetch nlohmann_json.

## Current limitations and non-goals

- The pose field is descriptive. It affects geometry only when the approved
  plan expresses the pose through different parts, attachment regions, or
  size classes. Text such as “curved tail” does not create a curved crease.
- complexity is recorded semantic metadata; it is not currently a numeric
  TreeMaker complexity control.
- The current deterministic compiler makes a useful flap tree, not a polished
  species-specific origami base.
- Square-boundary supports preserve a usable square paper boundary but are not
  model anatomy.
- A native full_cp proves the TreeMaker result contract and the square
  perimeter gate, not recognizable output or physical foldability.
- Step-by-step folding instructions, automatic physical validation, and
  general pose-specific geometric optimization are not implemented.
- The experimental tree graph generator/ TAN code is not connected to the
  current pipeline. Its adapter targets an external SEARCH-22.5-style server,
  and topology --strategy learned intentionally reports that a saved
  checkpoint interface is missing.

## Further documentation

- [System overview](docs/system_overview.md)
- [Deterministic tree compiler](docs/gen_tree_model.md)
- [Intent and structure model](docs/intent_model.md)
- [Native TreeMaker runner](native/treemaker_runner/README.md)
- [SVG-to-FOLD converter](tools/svg_to_fold/README.md)
- [Intent benchmark](benchmark/structure/README.md)
- [TreeMaker integration plan](TREEMAKER_INTEGRATION_PLAN.md)
