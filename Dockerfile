# gen-Ori -- single image containing all three project folders
# (structure/, "tree graph generator/", search-25/), preserving the exact
# sibling-folder layout that interface/server.py's path resolution depends
# on (GEN_ORI_TGG = SEARCH25_ROOT.parent / "tree graph generator").
#
# Databases (*.db), FAISS caches (*.index/*.pkl), and .env are intentionally
# NOT baked into this image -- see docker-compose.yml for how they get
# mounted in at `docker run` / `docker compose up` time instead.

FROM python:3.12-slim

# build-essential: needed to compile search-25's math225_core.cpp (pybind11
# C++ extension) via `pip install -e .` below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/gen-Ori

# ---------------------------------------------------------------------------
# Python dependencies (layered separately from source code so `docker build`
# can cache this step and skip reinstalling everything on every code change)
# ---------------------------------------------------------------------------
COPY requirements.txt ./requirements.txt
COPY search-25/pyproject.toml ./search-25/pyproject.toml
COPY search-25/setup.py ./search-25/setup.py

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# ---------------------------------------------------------------------------
# Project source (structure/, tree graph generator/, search-25/)
# ---------------------------------------------------------------------------
COPY structure/ ./structure/
COPY ["tree graph generator/", "./tree graph generator/"]
COPY search-25/ ./search-25/

# Build the compiled C++ extension (math225_core) now that its source is present.
RUN pip install --no-cache-dir -e ./search-25

WORKDIR /app/gen-Ori/search-25

EXPOSE 8000

CMD ["python", "-m", "interface.server"]
