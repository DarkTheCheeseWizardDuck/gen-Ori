# gen-Ori

Turn a plain-English origami request into matched, foldable crease patterns.

```
"a reindeer with antlers and four legs"
        │
        ▼
 structure/            NL request  ->  structured JSON (object, parts, symmetry, lengths)
        │
        ▼
 tree graph generator/  structured JSON  ->  rendered tree graph (TAN model)
        │
        ▼
 search-25/             tree graph  ->  nearest-match crease patterns (FAISS/HKT search
        │                              over a database of pre-computed tilings)
        ▼
   top-N matched crease patterns (PNG / interactive web viewer)
```

Three nested loops, smallest to largest:

| Loop | Entry point | Does |
|---|---|---|
| Smallest | `structure/pipeline.py` | NL request → parts JSON (via Groq) |
| Middle | `tree graph generator/run_from_prompt.py` | NL request → rendered tree graph (calls the smallest loop, then TAN) |
| Biggest | `run_full_loop.py` | NL request → matched, renderable crease patterns (calls the middle loop, then queries `search-25`) |

There's also a full interactive **web app** (`search-25/interface/`) that wraps the same pipeline behind a browser UI with a tree editor, live search, and a crease-pattern/fold-guide viewer.

---

## Repo layout

```
gen-Ori/
├── structure/                 Smallest loop: NL -> structured parts JSON
│   ├── extractor.py           Calls Groq to extract object/parts/symmetry
│   ├── length_assign.py       Calls Groq again to fill in relative part lengths
│   ├── pipeline.py            extractor -> length_assign, in one call
│   ├── evaluate.py            Runs pipeline.py against benchmark/structure/*.json
│   ├── prompt.txt             System prompt for extraction
│   ├── length_prompt.txt      System prompt for length assignment
│   └── schema.json            Output JSON schema
│
├── tree graph generator/      Middle loop: parts JSON -> rendered tree graph
│   ├── run_from_prompt.py     NL -> tree payload (wraps structure/ + TAN)
│   ├── run_pipeline.py        Trains/loads TAN, renders dataset/ -> renders/
│   ├── tan_model.py / tan_train.py / tan_decode.py   The TAN model itself
│   ├── tree_adapter.py        TAN output -> {"tree": {"nodes": [...], "edges": [...]}}
│   ├── dataset/                Ground-truth tree graphs used to train TAN
│   └── renders/{png,html}/     Rendered output per dataset object
│
├── search-25/                 Crease-pattern search + web interface
│   ├── database/tilings/      Offline-built tiling databases + FAISS caches, query.py
│   ├── database/refs/         Fold-guide ("crease pattern reference") database
│   ├── src/engine/            Core origami math (C++ extension + Python wrappers)
│   └── interface/             The web app
│       ├── server.py          Stdlib HTTP server (no framework), see Routes below
│       └── static/            HTML/CSS/JS front end
│
├── run_full_loop.py           Biggest loop, CLI: NL request -> matched CPs (PNG output)
├── benchmark/structure/       Test prompts for structure/evaluate.py
├── results/structure/         Saved outputs from structure/evaluate.py
├── Dockerfile / docker-compose.yml   Containerized web app + offline-build tooling
└── requirements.txt
```

---

## 1. Setup

### Prerequisites
- Python 3.11 or 3.12
- A C/C++ toolchain (needed to build `search-25`'s `math225_core` pybind11 extension)
- A [Groq API key](https://console.groq.com/keys) — used by `structure/` for the NL→JSON step

### Install
```bash
pip install -r requirements.txt
pip install -e ./search-25          # builds the math225_core C++ extension
```

### Configure your Groq key
Only needed for **CLI** use (`run_full_loop.py`, `run_pipeline.py`, `structure/evaluate.py`, etc). Create a `.env` file in the repo root:
```env
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=openai/gpt-oss-120b
```
The **web app** does *not* use this `.env` — see below.

### Build the search databases (one-time, offline)
`search-25`'s crease-pattern search needs its tiling databases and FAISS caches built before anything can be queried:
```bash
cd search-25
python -m database.tilings.build_topologies
python -m database.tilings.build_tilings
python -m database.tilings.faiss_cache
python -m database.refs.cp_tree 4 database/refs/storage/cp_pruned.db   # fold-guide references
```
These are large generated artifacts (multi-GB `.db`/`.index`/`.pkl` files) and are intentionally **not** committed to the repo — build them locally, or mount a pre-built copy (see `docker-compose.yml`).

---

## 2. Usage

### A. Command line — one request in, matched crease patterns out
```bash
python run_full_loop.py "a reindeer with antlers and four legs"
python run_full_loop.py "a reindeer with antlers and four legs" --n 8 --dbs 4:none 4:diag 3:none
```
Requires `tree graph generator/tan_checkpoint.pt` to already exist (run `tree graph generator/run_pipeline.py` once first to train/produce it). Results are saved as PNGs under `renders_full_loop/`.

### B. Web app — interactive tree editor + live search
```bash
cd search-25
python -m interface.server
```
Then open **http://127.0.0.1:8000**.

On first load you'll be asked for your own Groq API key and a model (defaults to `openai/gpt-oss-120b`, recommended) — this is entered directly in the browser, kept only in that browser's `localStorage`, and sent from the browser to the server on each request. It is **not** read from `.env` and never stored server-side, so the app is safe to deploy publicly without shipping a key with it — each visitor supplies their own.

**Routes** (`interface/server.py`):
| Route | Method | Purpose |
|---|---|---|
| `/` | GET | `static/index.html` |
| `/static/<path>` | GET | JS / CSS / assets |
| `/api/generate` | POST | NL prompt + api_key + model → tree payload |
| `/api/search` | POST | tree payload → matched crease patterns |
| `/api/fetch_refs` | POST | tiling_id/N/symmetry → fold-guide references |
| `/api/validate_key` | POST | api_key + model → `{valid: bool}` (used by the key modal) |

By default the server binds `127.0.0.1` (local only). Set `GENORI_INTERFACE_HOST=0.0.0.0` (and optionally `GENORI_INTERFACE_PORT`) to expose it, e.g. inside Docker.

### C. Docker
```bash
docker compose up          # builds + runs the web app on :8000
```
Offline build scripts run in a separate on-demand container (same image, not started by `up`):
```bash
docker compose run --rm builder python -m database.tilings.build_topologies
docker compose run --rm builder python -m database.tilings.build_tilings
docker compose run --rm builder python -m database.tilings.faiss_cache
docker compose run --rm builder python -m database.refs.cp_tree 4 database/refs/storage/cp_pruned.db
```
Both share `search-25/database/` as a mounted volume, so anything the `builder` produces is immediately visible to `app` without a rebuild.

---

## 3. Customization

| What | Where |
|---|---|
| How NL requests are decomposed into parts | `structure/prompt.txt` |
| How relative part lengths are assigned | `structure/length_prompt.txt` |
| Output JSON schema for the structure step | `structure/schema.json` |
| Recommended/default Groq model | `openai/gpt-oss-120b` — set via `GROQ_MODEL` in `.env` (CLI) or the web app's key modal |
| TAN training data | `tree graph generator/dataset/*.json` |
| Which databases the search step queries | `--dbs` flag on `run_full_loop.py`, e.g. `4:none 4:diag 3:none` (N:symmetry pairs) |

---

## 4. Evaluating the structure-extraction step
```bash
python structure/evaluate.py
```
Runs `structure/pipeline.py` against every benchmark file in `benchmark/structure/` and writes results to `results/structure/`.

---

## Notes
- `structure/` and `tree graph generator/run_from_prompt.py` are imported as-is by both `run_full_loop.py` and the web app's `server.py` — neither wrapper modifies them.
- The web app intentionally ships without logging, auth, or an "about" page — it's meant to run behind whatever access control you put in front of it.