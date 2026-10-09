# ruff: noqa: E402
# Standalone script resolves the backend import path before importing app modules.
"""Populate a separate preview database with recorded fictional cases only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.campus_demo import advance, start
from app.services.profiles import ProfileStore


def seed(directory):
    directory = Path(directory)
    store = ProfileStore(directory)
    manifest = directory / "preview-index.json"
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8"))
    ids = {}
    for case_id in ["V5-S01", "V5-L20", "V5-O02", "V5-I01", "V5-E01", "V5-W01"]:
        result = start(store, case_id)
        while result["step"] < result["count"]:
            result = advance(store, result["profile"]["id"], result["profile"]["revision"])
        ids[case_id] = result["profile"]["id"]
    ids["R01"] = ids["V5-S01"]  # Stable entry point for the preview launcher.
    manifest.write_text(json.dumps(ids, indent=2), encoding="utf-8")
    return ids


if __name__ == "__main__":
    print(json.dumps(seed(sys.argv[1])))
