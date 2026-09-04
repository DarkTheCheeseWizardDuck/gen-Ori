import hashlib
import json
from pathlib import Path


def _content_hash(obj: dict) -> str:
    payload = json.dumps({"raw_parts": obj["raw_parts"], "ground_truth": obj["ground_truth"]}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_dataset(folder: str = "dataset", warn_on_duplicates: bool = True) -> list[dict]:
    """
    Reads every *.json file in `folder` and returns a list of
    {"name": <filename stem>, "raw_parts": [...], "ground_truth": [...]}
    """
    entries = []
    seen_hashes: dict[str, str] = {}
    for path in sorted(Path(folder).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if "raw_parts" not in data or "ground_truth" not in data:
            raise ValueError(f"{path.name}: missing 'raw_parts' or 'ground_truth' key")
        data["name"] = path.stem
        entries.append(data)

        if warn_on_duplicates:
            h = _content_hash(data)
            if h in seen_hashes:
                print(f"[warning] {path.name} has identical raw_parts+ground_truth to {seen_hashes[h]} -- likely an accidental duplicate, not extra diversity")
            seen_hashes[h] = path.name

    return entries


if __name__ == "__main__":
    ds = load_dataset("dataset")
    for obj in ds:
        print(f"{obj['name']:10s}  {len(obj['raw_parts'])} parts, {len(obj['ground_truth'])} ground-truth entries")

