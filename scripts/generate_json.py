"""
JSON export — dumps the full analysis as structured JSON for downstream use.
"""
from __future__ import annotations

import json
from pathlib import Path


def generate_json_export(data, output_path):
    """Write the analysis data as JSON."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return str(output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(generate_json_export(data, args.output))
