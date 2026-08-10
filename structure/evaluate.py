import json
from pathlib import Path

from pipeline import run_pipeline

# ==========================================================
# Paths
# ==========================================================
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent

BENCHMARK_DIR = ROOT_DIR / "benchmark" / "structure"
RESULT_DIR = ROOT_DIR / "results" / "structure"

# ==========================================================
# Discover available benchmark files
# ==========================================================
# Automatically scans benchmark/structure/ for every .json file.
# This means adding/removing/renaming benchmark files requires
# NO modification to this script.
benchmark_files = sorted(BENCHMARK_DIR.glob("*.json"))

if not benchmark_files:
    raise RuntimeError(
        f"No benchmark files found in:\n{BENCHMARK_DIR}"
    )

# ==========================================================
# Display benchmark menu
# ==========================================================
print("Available benchmarks:\n")

for i, file in enumerate(benchmark_files, start=1):
    print(f"[{i}] {file.stem}")

# ==========================================================
# User selects which benchmark to evaluate
# ==========================================================
while True:

    choice = input("\nSelect benchmark: ")

    # User enters a number
    if choice.isdigit():

        index = int(choice) - 1

        if 0 <= index < len(benchmark_files):
            benchmark_path = benchmark_files[index]
            break

    # User enters the benchmark name
    else:

        for file in benchmark_files:
            if file.stem.lower() == choice.lower():
                benchmark_path = file
                break
        else:
            benchmark_path = None

        if benchmark_path:
            break

    print("Invalid selection. Please try again.")

# ==========================================================
# Load selected benchmark
# ==========================================================
try:
    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark = json.load(f)

except Exception as e:
    raise RuntimeError(
        f"Failed to load benchmark:\n{e}"
    )

print(f"\nRunning benchmark: {benchmark_path.stem}")
print(f"Total test cases: {len(benchmark)}\n")

# ==========================================================
# Run every test case through the Extract Structure Model
# ==========================================================
results = []

for i, test_case in enumerate(benchmark, start=1):

    print(f"[{i}/{len(benchmark)}] {test_case['id']}")

    try:
        output = run_pipeline(test_case["input"])

    except Exception as e:
        # Don't stop the whole benchmark if one request fails.
        output = {
            "error": str(e)
        }

    results.append({
        "id": test_case["id"],
        "input": test_case["input"],
        "output": output
    })

# ==========================================================
# Save results
# ==========================================================
# Each benchmark gets its own output file.
#
# Example:
# easy.json        -> easy_outputs.json
# medium.json      -> medium_outputs.json
#
RESULT_DIR.mkdir(parents=True, exist_ok=True)

result_path = RESULT_DIR / f"{benchmark_path.stem}_outputs.json"

with open(result_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4, ensure_ascii=False)

# ==========================================================
# Finished
# ==========================================================
print("\n========================================")
print("Benchmark completed successfully!")
print(f"Results saved to:\n{result_path}")
print("========================================")