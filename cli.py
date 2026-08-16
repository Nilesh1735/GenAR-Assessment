from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.data.schema import DatasetError
from src.llm.client import LLMError
from src.pipeline import generate_report
from src.report.assemble import render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an evidence-grounded PADER report.")
    parser.add_argument("--config", default="config/pader.yaml")
    parser.add_argument("--data", default="Bisoprolol_icsr_sample_1068rows.xlsx")
    parser.add_argument("--out", default="output/bisoprolol_pader.md")
    args = parser.parse_args(argv)

    try:
        report = generate_report(args.config, args.data)
    except (LLMError, DatasetError) as error:
        parser.exit(2, f"error: {error}\n")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(report), encoding="utf-8")
    manifest_path = out.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(report.manifest, indent=2), encoding="utf-8")

    failed = [section for section in report.sections if section.grounding and section.grounding.status == "fail"]
    print(f"wrote {out} ({report.manifest['n_cases']} cases)")
    print(f"wrote {manifest_path}")
    if failed:
        names = ", ".join(section.id for section in failed)
        print(f"WARNING: {len(failed)} section(s) failed grounding: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
