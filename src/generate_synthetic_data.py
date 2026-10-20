from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


# =========================================================
# Synthetic process definition
# =========================================================

PHASES = [
    "Prioritization",
    "Intake",
    "Cancelled / Rejected",
    "Data Preparation",
    "Requester Pending",
    "Platform Validation",
    "System Upload",
    "Scheduled / Waiting Start",
    "Quality Review",
    "Validated / Active",
    "Completed",
    "Pending Return",
]

ENTRY_PREFIX = "Primeira vez que entrou na fase "
EXIT_PREFIX = "Última vez que saiu da fase "
DURATION_PREFIX = "Tempo total na fase "
DURATION_SUFFIX = " (dias)"

CASE_ID_COLUMN = "Código"
CURRENT_PHASE_COLUMN = "Fase atual"
CARD_TYPE_COLUMN = "Tipo de card"

DEFAULT_OUTPUT = Path(
    "examples/synthetic_operational_report.xlsx"
)


# =========================================================
# Synthetic scenarios
# =========================================================

PATH_PATTERNS = {
    "core_flow": [
        "Intake",
        "Data Preparation",
        "System Upload",
        "Scheduled / Waiting Start",
        "Quality Review",
        "Validated / Active",
        "Completed",
    ],
    "early_exit": [
        "Intake",
        "Cancelled / Rejected",
    ],
    "late_exit": [
        "Intake",
        "Data Preparation",
        "System Upload",
        "Scheduled / Waiting Start",
        "Cancelled / Rejected",
    ],
    "exception_before_processing": [
        "Intake",
        "Requester Pending",
        "Pending Return",
        "Data Preparation",
        "System Upload",
        "Scheduled / Waiting Start",
        "Quality Review",
        "Validated / Active",
        "Completed",
    ],
    "exception_after_processing": [
        "Intake",
        "Data Preparation",
        "Requester Pending",
        "Pending Return",
        "System Upload",
        "Scheduled / Waiting Start",
        "Quality Review",
        "Validated / Active",
        "Completed",
    ],
    "bypass_waiting": [
        "Intake",
        "Data Preparation",
        "System Upload",
        "Quality Review",
        "Validated / Active",
        "Completed",
    ],
    "bypass_quality": [
        "Intake",
        "Data Preparation",
        "System Upload",
        "Scheduled / Waiting Start",
        "Validated / Active",
        "Completed",
    ],
    "prioritization_flow": [
        "Intake",
        "Prioritization",
        "Data Preparation",
        "System Upload",
        "Scheduled / Waiting Start",
        "Quality Review",
        "Validated / Active",
        "Completed",
    ],
    "platform_validation_flow": [
        "Intake",
        "Data Preparation",
        "System Upload",
        "Platform Validation",
        "Scheduled / Waiting Start",
        "Quality Review",
        "Validated / Active",
        "Completed",
    ],
    "open_quality_review": [
        "Intake",
        "Data Preparation",
        "System Upload",
        "Scheduled / Waiting Start",
        "Quality Review",
    ],
    "open_waiting_start": [
        "Intake",
        "Data Preparation",
        "System Upload",
        "Scheduled / Waiting Start",
    ],
}

PATTERN_WEIGHTS = {
    "core_flow": 0.34,
    "early_exit": 0.10,
    "late_exit": 0.06,
    "exception_before_processing": 0.12,
    "exception_after_processing": 0.08,
    "bypass_waiting": 0.10,
    "bypass_quality": 0.03,
    "prioritization_flow": 0.06,
    "platform_validation_flow": 0.05,
    "open_quality_review": 0.03,
    "open_waiting_start": 0.03,
}


# =========================================================
# Duration configuration
#
# These values are intentionally synthetic.
# They are not calibrated from any real operation.
# =========================================================

DURATION_CONFIG = {
    "Intake": {
        "median": 16.0,
        "sigma": 0.75,
        "minimum": 0.25,
        "maximum": 96.0,
    },
    "Prioritization": {
        "median": 2.0,
        "sigma": 0.65,
        "minimum": 0.10,
        "maximum": 24.0,
    },
    "Data Preparation": {
        "median": 1.0,
        "sigma": 0.70,
        "minimum": 0.05,
        "maximum": 24.0,
    },
    "Requester Pending": {
        "median": 20.0,
        "sigma": 0.90,
        "minimum": 1.0,
        "maximum": 168.0,
    },
    "Pending Return": {
        "median": 1.5,
        "sigma": 0.60,
        "minimum": 0.10,
        "maximum": 24.0,
    },
    "Platform Validation": {
        "median": 2.5,
        "sigma": 0.70,
        "minimum": 0.10,
        "maximum": 36.0,
    },
    "System Upload": {
        "median": 1.25,
        "sigma": 0.65,
        "minimum": 0.05,
        "maximum": 18.0,
    },
    "Scheduled / Waiting Start": {
        "median": 72.0,
        "sigma": 0.55,
        "minimum": 6.0,
        "maximum": 240.0,
    },
    "Quality Review": {
        "median": 12.0,
        "sigma": 0.75,
        "minimum": 0.25,
        "maximum": 96.0,
    },
    "Validated / Active": {
        "median": 240.0,
        "sigma": 0.50,
        "minimum": 24.0,
        "maximum": 720.0,
    },
}

TERMINAL_PHASES = {
    "Completed",
    "Cancelled / Rejected",
}


# =========================================================
# CLI
# =========================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generates a fully synthetic operational report "
            "for the Operational Flow Intelligence demo."
        )
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Output Excel file. "
            "Default: examples/synthetic_operational_report.xlsx"
        ),
    )

    parser.add_argument(
        "--cases",
        type=int,
        default=2500,
        help="Number of synthetic cases. Default: 2500.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed. Default: 42.",
    )

    parser.add_argument(
        "--start-date",
        type=str,
        default="2026-01-01",
        help="Beginning of synthetic case creation window.",
    )

    parser.add_argument(
        "--window-days",
        type=int,
        default=270,
        help=(
            "Number of days in the synthetic creation window. "
            "Default: 270."
        ),
    )

    return parser.parse_args()


# =========================================================
# Synthetic generation helpers
# =========================================================

def validate_arguments(
    cases: int,
    window_days: int,
) -> None:
    if cases <= 0:
        raise ValueError(
            "--cases must be greater than zero."
        )

    if window_days <= 0:
        raise ValueError(
            "--window-days must be greater than zero."
        )


def parse_start_date(value: str) -> datetime:
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        )

    except ValueError as error:
        raise ValueError(
            "--start-date must use YYYY-MM-DD format."
        ) from error


def sample_duration_hours(
    phase: str,
    rng: random.Random,
) -> float | None:
    config = DURATION_CONFIG.get(phase)

    if config is None:
        return None

    median = config["median"]
    sigma = config["sigma"]
    minimum = config["minimum"]
    maximum = config["maximum"]

    value = rng.lognormvariate(
        math.log(median),
        sigma,
    )

    value = max(
        minimum,
        min(
            value,
            maximum,
        ),
    )

    return round(
        value,
        6,
    )


def sample_handoff_hours(
    rng: random.Random,
) -> float:
    return round(
        rng.uniform(
            0.0,
            3.0,
        ),
        6,
    )


def choose_pattern(
    rng: random.Random,
) -> str:
    names = list(
        PATTERN_WEIGHTS.keys()
    )

    weights = [
        PATTERN_WEIGHTS[name]
        for name in names
    ]

    return rng.choices(
        population=names,
        weights=weights,
        k=1,
    )[0]


def choose_case_type(
    pattern_name: str,
    rng: random.Random,
) -> str:
    if pattern_name == "prioritization_flow":
        return rng.choices(
            population=[
                "Priority Request",
                "Standard Request",
            ],
            weights=[
                0.80,
                0.20,
            ],
            k=1,
        )[0]

    if "exception" in pattern_name:
        return rng.choices(
            population=[
                "Standard Request",
                "Review Request",
                "Priority Request",
            ],
            weights=[
                0.55,
                0.35,
                0.10,
            ],
            k=1,
        )[0]

    return rng.choices(
        population=[
            "Standard Request",
            "Priority Request",
            "Review Request",
        ],
        weights=[
            0.70,
            0.20,
            0.10,
        ],
        k=1,
    )[0]


def initialize_case_row(
    case_id: str,
    current_phase: str,
    card_type: str,
    scenario: str,
) -> dict[str, object]:
    row: dict[str, object] = {
        CASE_ID_COLUMN: case_id,
        CURRENT_PHASE_COLUMN: current_phase,
        CARD_TYPE_COLUMN: card_type,
        "Synthetic Scenario": scenario,
    }

    for phase in PHASES:
        row[
            f"{ENTRY_PREFIX}{phase}"
        ] = pd.NaT

        row[
            f"{EXIT_PREFIX}{phase}"
        ] = pd.NaT

        row[
            (
                f"{DURATION_PREFIX}"
                f"{phase}"
                f"{DURATION_SUFFIX}"
            )
        ] = pd.NA

    return row


def populate_case_history(
    row: dict[str, object],
    path: list[str],
    case_start: datetime,
    rng: random.Random,
) -> None:
    cursor = case_start

    for index, phase in enumerate(path):
        entry_column = (
            f"{ENTRY_PREFIX}{phase}"
        )

        exit_column = (
            f"{EXIT_PREFIX}{phase}"
        )

        duration_column = (
            f"{DURATION_PREFIX}"
            f"{phase}"
            f"{DURATION_SUFFIX}"
        )

        row[entry_column] = cursor

        is_last_activity = (
            index == len(path) - 1
        )

        if is_last_activity:
            # Last activity represents the current/terminal state.
            # No artificial exit timestamp is created.
            continue

        duration_hours = (
            sample_duration_hours(
                phase,
                rng,
            )
        )

        if duration_hours is None:
            continue

        exit_time = (
            cursor
            + timedelta(
                hours=duration_hours
            )
        )

        row[exit_column] = exit_time

        row[duration_column] = (
            duration_hours / 24
        )

        handoff_hours = (
            sample_handoff_hours(
                rng
            )
        )

        cursor = (
            exit_time
            + timedelta(
                hours=handoff_hours
            )
        )


def generate_dataset(
    cases: int,
    seed: int,
    start_date: datetime,
    window_days: int,
) -> pd.DataFrame:
    rng = random.Random(seed)

    rows: list[
        dict[str, object]
    ] = []

    for case_number in range(
        1,
        cases + 1,
    ):
        pattern_name = (
            choose_pattern(rng)
        )

        path = PATH_PATTERNS[
            pattern_name
        ]

        case_id = (
            f"SYN-{case_number:06d}"
        )

        card_type = choose_case_type(
            pattern_name,
            rng,
        )

        case_day_offset = (
            rng.randint(
                0,
                window_days - 1,
            )
        )

        case_hour_offset = (
            rng.uniform(
                0,
                23.99,
            )
        )

        case_start = (
            start_date
            + timedelta(
                days=case_day_offset,
                hours=case_hour_offset,
            )
        )

        current_phase = (
            path[-1]
        )

        row = initialize_case_row(
            case_id=case_id,
            current_phase=current_phase,
            card_type=card_type,
            scenario=pattern_name,
        )

        populate_case_history(
            row=row,
            path=path,
            case_start=case_start,
            rng=rng,
        )

        rows.append(row)

    dataframe = pd.DataFrame(
        rows
    )

    dataframe = dataframe.sample(
        frac=1,
        random_state=seed,
    ).reset_index(
        drop=True
    )

    return dataframe


# =========================================================
# Workbook creation
# =========================================================

def build_about_sheet(
    cases: int,
    seed: int,
    start_date: datetime,
    window_days: int,
) -> pd.DataFrame:
    records = [
        {
            "Field": "Dataset",
            "Value": (
                "Synthetic Operational Report"
            ),
        },
        {
            "Field": "Purpose",
            "Value": (
                "Public demo dataset for "
                "Operational Flow Intelligence"
            ),
        },
        {
            "Field": "Data classification",
            "Value": (
                "100% synthetic / no real operational data"
            ),
        },
        {
            "Field": "Cases",
            "Value": str(cases),
        },
        {
            "Field": "Seed",
            "Value": str(seed),
        },
        {
            "Field": "Start date",
            "Value": start_date.strftime(
                "%Y-%m-%d"
            ),
        },
        {
            "Field": "Window days",
            "Value": str(window_days),
        },
        {
            "Field": "Important",
            "Value": (
                "Scenario weights and durations are "
                "artificial and are not calibrated "
                "from a real operation."
            ),
        },
    ]

    return pd.DataFrame(
        records
    )


def build_scenario_sheet() -> pd.DataFrame:
    rows = []

    for scenario, weight in (
        PATTERN_WEIGHTS.items()
    ):
        rows.append(
            {
                "Scenario": scenario,
                "Synthetic Weight": weight,
                "Path": " → ".join(
                    PATH_PATTERNS[
                        scenario
                    ]
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


def format_workbook(
    writer: pd.ExcelWriter,
    report_df: pd.DataFrame,
) -> None:
    workbook = writer.book

    report_sheet = workbook[
        "Report"
    ]

    report_sheet.freeze_panes = (
        "A2"
    )

    report_sheet.auto_filter.ref = (
        report_sheet.dimensions
    )

    for column_index, column in enumerate(
        report_df.columns,
        start=1,
    ):
        width = max(
            12,
            min(
                len(str(column)) + 2,
                42,
            ),
        )

        report_sheet.column_dimensions[
            report_sheet.cell(
                row=1,
                column=column_index,
            ).column_letter
        ].width = width

    about_sheet = workbook[
        "About"
    ]

    about_sheet.column_dimensions[
        "A"
    ].width = 24

    about_sheet.column_dimensions[
        "B"
    ].width = 75

    scenario_sheet = workbook[
        "Synthetic Scenarios"
    ]

    scenario_sheet.column_dimensions[
        "A"
    ].width = 32

    scenario_sheet.column_dimensions[
        "B"
    ].width = 18

    scenario_sheet.column_dimensions[
        "C"
    ].width = 100


def save_workbook(
    dataframe: pd.DataFrame,
    output_path: Path,
    cases: int,
    seed: int,
    start_date: datetime,
    window_days: int,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    about_df = build_about_sheet(
        cases=cases,
        seed=seed,
        start_date=start_date,
        window_days=window_days,
    )

    scenario_df = (
        build_scenario_sheet()
    )

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
        datetime_format=(
            "yyyy-mm-dd hh:mm:ss"
        ),
    ) as writer:
        dataframe.to_excel(
            writer,
            sheet_name="Report",
            index=False,
        )

        about_df.to_excel(
            writer,
            sheet_name="About",
            index=False,
        )

        scenario_df.to_excel(
            writer,
            sheet_name=(
                "Synthetic Scenarios"
            ),
            index=False,
        )

        format_workbook(
            writer,
            dataframe,
        )


# =========================================================
# Console summary
# =========================================================

def print_summary(
    dataframe: pd.DataFrame,
    output_path: Path,
    seed: int,
) -> None:
    scenario_counts = (
        dataframe[
            "Synthetic Scenario"
        ]
        .value_counts()
    )

    print()
    print("=" * 72)
    print(
        "OPERATIONAL FLOW INTELLIGENCE"
    )
    print(
        "Synthetic Demo Data Generator"
    )
    print("=" * 72)

    print(
        f"Casos sintéticos gerados : "
        f"{len(dataframe):,}"
    )

    print(
        f"Fases disponíveis        : "
        f"{len(PHASES):,}"
    )

    print(
        f"Cenários sintéticos      : "
        f"{len(PATH_PATTERNS):,}"
    )

    print(
        f"Seed                     : "
        f"{seed}"
    )

    print()
    print(
        "Distribuição dos cenários:"
    )

    for scenario, count in (
        scenario_counts.items()
    ):
        share = (
            count
            / len(dataframe)
            * 100
        )

        print(
            f"  {scenario:<32} "
            f"{count:>6,} | "
            f"{share:>6.2f}%"
        )

    print()
    print(
        "Segurança:"
    )

    print(
        "  Dataset 100% sintético."
    )

    print(
        "  Nenhum registro operacional "
        "real foi utilizado."
    )

    print(
        "  Pesos e durações são artificiais."
    )

    print()
    print(
        "Arquivo gerado:"
    )

    print(
        f"  {output_path.resolve()}"
    )

    print("=" * 72)
    print()


# =========================================================
# Main
# =========================================================

def main() -> None:
    args = parse_arguments()

    validate_arguments(
        cases=args.cases,
        window_days=args.window_days,
    )

    start_date = parse_start_date(
        args.start_date
    )

    dataframe = generate_dataset(
        cases=args.cases,
        seed=args.seed,
        start_date=start_date,
        window_days=args.window_days,
    )

    save_workbook(
        dataframe=dataframe,
        output_path=args.output,
        cases=args.cases,
        seed=args.seed,
        start_date=start_date,
        window_days=args.window_days,
    )

    print_summary(
        dataframe=dataframe,
        output_path=args.output,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()