from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "case_id",
    "event_order",
    "activity",
    "event_timestamp",
    "start_time",
    "end_time",
    "duration_hours",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analisa um event log e identifica variantes, "
            "transições e caminhos reais do processo."
        )
    )

    parser.add_argument(
        "event_log",
        type=Path,
        help="Caminho do event_log.csv.",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("data/output/discovery"),
        help=(
            "Diretório onde os resultados serão gerados. "
            "Padrão: data/output/discovery"
        ),
    )

    return parser.parse_args()


def validate_event_log(df: pd.DataFrame) -> None:
    missing_columns = (
        REQUIRED_COLUMNS
        - set(df.columns)
    )

    if missing_columns:
        missing = ", ".join(
            sorted(missing_columns)
        )

        raise ValueError(
            "O event log não possui todas as colunas "
            f"necessárias. Ausentes: {missing}"
        )


def load_event_log(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Event log não encontrado: {path}"
        )

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
    )

    validate_event_log(df)

    datetime_columns = [
        "event_timestamp",
        "start_time",
        "end_time",
    ]

    for column in datetime_columns:
        df[column] = pd.to_datetime(
            df[column],
            errors="coerce",
        )

    df["activity"] = (
        df["activity"]
        .astype("string")
        .str.strip()
    )

    df = df.dropna(
        subset=[
            "case_id",
            "activity",
        ]
    ).copy()

    df = df.sort_values(
        by=[
            "case_id",
            "event_order",
            "event_timestamp",
        ],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)

    return df


def build_case_paths(
    event_log: pd.DataFrame,
) -> pd.DataFrame:
    grouped = event_log.groupby(
        "case_id",
        sort=False,
        dropna=False,
    )

    rows: list[dict[str, object]] = []

    for case_id, case_df in grouped:
        activities = (
            case_df["activity"]
            .dropna()
            .astype(str)
            .tolist()
        )

        if not activities:
            continue

        start_candidates = (
            case_df["start_time"]
            .dropna()
        )

        end_candidates = (
            case_df["end_time"]
            .dropna()
        )

        event_candidates = (
            case_df["event_timestamp"]
            .dropna()
        )

        if not start_candidates.empty:
            case_start = start_candidates.min()
        elif not event_candidates.empty:
            case_start = event_candidates.min()
        else:
            case_start = pd.NaT

        if not end_candidates.empty:
            case_end = end_candidates.max()
        elif not event_candidates.empty:
            case_end = event_candidates.max()
        else:
            case_end = pd.NaT

        if (
            pd.notna(case_start)
            and pd.notna(case_end)
        ):
            lead_time_hours = (
                case_end - case_start
            ).total_seconds() / 3600
        else:
            lead_time_hours = pd.NA

        duration_hours = pd.to_numeric(
            case_df["duration_hours"],
            errors="coerce",
        ).sum(
            min_count=1
        )

        rows.append(
            {
                "case_id": case_id,
                "activity_count": len(
                    activities
                ),
                "first_activity": (
                    activities[0]
                ),
                "last_activity": (
                    activities[-1]
                ),
                "case_start": case_start,
                "case_end": case_end,
                "lead_time_hours": (
                    lead_time_hours
                ),
                "recorded_duration_hours": (
                    duration_hours
                ),
                "path": " → ".join(
                    activities
                ),
            }
        )

    case_paths = pd.DataFrame(rows)

    return case_paths


def build_variants(
    case_paths: pd.DataFrame,
) -> pd.DataFrame:
    variants = (
        case_paths
        .groupby(
            "path",
            dropna=False,
        )
        .agg(
            case_count=(
                "case_id",
                "nunique",
            ),
            avg_activity_count=(
                "activity_count",
                "mean",
            ),
            avg_lead_time_hours=(
                "lead_time_hours",
                "mean",
            ),
            avg_recorded_duration_hours=(
                "recorded_duration_hours",
                "mean",
            ),
        )
        .reset_index()
    )

    variants = variants.sort_values(
        by=[
            "case_count",
            "path",
        ],
        ascending=[
            False,
            True,
        ],
        kind="stable",
    ).reset_index(drop=True)

    total_cases = (
        variants["case_count"].sum()
    )

    variants["share_pct"] = (
        variants["case_count"]
        / total_cases
        * 100
    )

    variants["cumulative_share_pct"] = (
        variants["share_pct"]
        .cumsum()
    )

    variants.insert(
        0,
        "variant_id",
        range(
            1,
            len(variants) + 1,
        ),
    )

    return variants


def build_transitions(
    event_log: pd.DataFrame,
) -> pd.DataFrame:
    transitions = event_log[
        [
            "case_id",
            "event_order",
            "activity",
        ]
    ].copy()

    transitions["next_activity"] = (
        transitions
        .groupby(
            "case_id",
            dropna=False,
        )["activity"]
        .shift(-1)
    )

    transitions = transitions.dropna(
        subset=["next_activity"]
    ).copy()

    transition_summary = (
        transitions
        .groupby(
            [
                "activity",
                "next_activity",
            ],
            dropna=False,
        )
        .agg(
            case_count=(
                "case_id",
                "nunique",
            )
        )
        .reset_index()
        .rename(
            columns={
                "activity": (
                    "source_activity"
                ),
                "next_activity": (
                    "target_activity"
                ),
            }
        )
    )

    outgoing_totals = (
        transition_summary
        .groupby(
            "source_activity"
        )["case_count"]
        .transform("sum")
    )

    transition_summary[
        "outgoing_share_pct"
    ] = (
        transition_summary[
            "case_count"
        ]
        / outgoing_totals
        * 100
    )

    transition_summary = (
        transition_summary
        .sort_values(
            by=[
                "case_count",
                "source_activity",
                "target_activity",
            ],
            ascending=[
                False,
                True,
                True,
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    return transition_summary


def build_activity_summary(
    event_log: pd.DataFrame,
) -> pd.DataFrame:
    event_log = event_log.copy()

    event_log["duration_hours"] = (
        pd.to_numeric(
            event_log[
                "duration_hours"
            ],
            errors="coerce",
        )
    )

    activity_summary = (
        event_log
        .groupby(
            "activity",
            dropna=False,
        )
        .agg(
            cases=(
                "case_id",
                "nunique",
            ),
            events=(
                "case_id",
                "size",
            ),
            avg_duration_hours=(
                "duration_hours",
                "mean",
            ),
            median_duration_hours=(
                "duration_hours",
                "median",
            ),
        )
        .reset_index()
    )

    total_cases = (
        event_log["case_id"]
        .nunique(
            dropna=True
        )
    )

    activity_summary[
        "case_coverage_pct"
    ] = (
        activity_summary["cases"]
        / total_cases
        * 100
    )

    activity_summary = (
        activity_summary
        .sort_values(
            by="cases",
            ascending=False,
            kind="stable",
        )
        .reset_index(drop=True)
    )

    return activity_summary


def print_summary(
    event_log: pd.DataFrame,
    case_paths: pd.DataFrame,
    variants: pd.DataFrame,
    transitions: pd.DataFrame,
    output_dir: Path,
) -> None:
    total_cases = (
        case_paths["case_id"]
        .nunique(
            dropna=True
        )
    )

    total_variants = len(
        variants
    )

    total_transitions = len(
        transitions
    )

    top_variant = (
        variants.iloc[0]
        if not variants.empty
        else None
    )

    print()
    print("=" * 72)
    print(
        "OPERATIONAL FLOW INTELLIGENCE"
    )
    print(
        "Process Discovery Engine"
    )
    print("=" * 72)

    print(
        f"Eventos analisados       : "
        f"{len(event_log):,}"
    )

    print(
        f"Casos analisados         : "
        f"{total_cases:,}"
    )

    print(
        f"Variantes identificadas  : "
        f"{total_variants:,}"
    )

    print(
        f"Transições identificadas : "
        f"{total_transitions:,}"
    )

    if top_variant is not None:
        print()
        print(
            "Variante mais frequente:"
        )

        print(
            f"  Casos       : "
            f"{int(top_variant['case_count']):,}"
        )

        print(
            f"  Participação: "
            f"{top_variant['share_pct']:.2f}%"
        )

        print(
            f"  Caminho     : "
            f"{top_variant['path']}"
        )

    print()
    print("Top 10 variantes:")

    for _, row in (
        variants
        .head(10)
        .iterrows()
    ):
        print(
            f"  V{int(row['variant_id']):03d} | "
            f"{int(row['case_count']):>6,} casos | "
            f"{row['share_pct']:>6.2f}% | "
            f"{row['path']}"
        )

    print()
    print("Arquivos gerados:")
    print(
        f"  {output_dir.resolve()}"
    )
    print("=" * 72)
    print()


def save_results(
    case_paths: pd.DataFrame,
    variants: pd.DataFrame,
    transitions: pd.DataFrame,
    activity_summary: pd.DataFrame,
    output_dir: Path,
) -> None:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    case_paths.to_csv(
        output_dir
        / "case_paths.csv",
        index=False,
        encoding="utf-8-sig",
        date_format=(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    variants.to_csv(
        output_dir
        / "variants.csv",
        index=False,
        encoding="utf-8-sig",
    )

    transitions.to_csv(
        output_dir
        / "transitions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    activity_summary.to_csv(
        output_dir
        / "activity_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> None:
    args = parse_arguments()

    event_log_path = (
        args.event_log.resolve()
    )

    output_dir = (
        args.output_dir.resolve()
    )

    print()
    print("Lendo event log:")
    print(
        f"  {event_log_path}"
    )

    event_log = load_event_log(
        event_log_path
    )

    case_paths = build_case_paths(
        event_log
    )

    variants = build_variants(
        case_paths
    )

    transitions = build_transitions(
        event_log
    )

    activity_summary = (
        build_activity_summary(
            event_log
        )
    )

    save_results(
        case_paths=case_paths,
        variants=variants,
        transitions=transitions,
        activity_summary=activity_summary,
        output_dir=output_dir,
    )

    print_summary(
        event_log=event_log,
        case_paths=case_paths,
        variants=variants,
        transitions=transitions,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()