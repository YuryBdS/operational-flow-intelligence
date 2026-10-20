from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Executa o pipeline completo do "
            "Operational Flow Intelligence."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Arquivo operacional de entrada.",
    )

    parser.add_argument(
        "--mapping",
        type=Path,
        required=True,
        help="Source mapping JSON.",
    )

    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Flow profile JSON.",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path(
            "data/output/pipeline"
        ),
        help=(
            "Diretório base para os outputs "
            "do pipeline."
        ),
    )

    return parser.parse_args()


def run_step(
    step_name: str,
    command: list[str],
) -> None:
    print()
    print("=" * 72)
    print(f"STEP: {step_name}")
    print("=" * 72)

    subprocess.run(
        command,
        check=True,
        cwd=PROJECT_ROOT,
    )


def main() -> None:
    args = parse_arguments()

    input_file = (
        args.input_file.resolve()
    )

    mapping_file = (
        args.mapping.resolve()
    )

    profile_file = (
        args.profile.resolve()
    )

    output_dir = (
        args.output_dir.resolve()
    )

    event_log_file = (
        output_dir
        / "event_log.csv"
    )

    discovery_dir = (
        output_dir
        / "discovery"
    )

    intelligence_dir = (
        output_dir
        / "intelligence"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    python_executable = (
        sys.executable
    )

    run_step(
        "DATA TO EVENT LOG",
        [
            python_executable,
            str(
                SRC_DIR
                / "event_log.py"
            ),
            str(input_file),
            "--mapping",
            str(mapping_file),
            "-o",
            str(event_log_file),
        ],
    )

    run_step(
        "PROCESS DISCOVERY",
        [
            python_executable,
            str(
                SRC_DIR
                / "process_discovery.py"
            ),
            str(event_log_file),
            "-o",
            str(discovery_dir),
        ],
    )

    run_step(
        "FLOW INTELLIGENCE",
        [
            python_executable,
            str(
                SRC_DIR
                / "flow_intelligence.py"
            ),
            str(discovery_dir),
            "--profile",
            str(profile_file),
            "-o",
            str(intelligence_dir),
        ],
    )

    print()
    print("=" * 72)
    print(
        "OPERATIONAL FLOW INTELLIGENCE"
    )
    print(
        "PIPELINE COMPLETED SUCCESSFULLY"
    )
    print("=" * 72)

    print(
        f"Event log     : "
        f"{event_log_file}"
    )

    print(
        f"Discovery     : "
        f"{discovery_dir}"
    )

    print(
        f"Intelligence  : "
        f"{intelligence_dir}"
    )

    print("=" * 72)
    print()


if __name__ == "__main__":
    main()