from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ENTRY_PREFIX = "Primeira vez que entrou na fase "
EXIT_PREFIX = "Última vez que saiu da fase "
DURATION_PREFIX = "Tempo total na fase "
DURATION_SUFFIX = " (dias)"

CASE_ID_COLUMN = "Código"
CURRENT_PHASE_COLUMN = "Fase atual"
CARD_TYPE_COLUMN = "Tipo de card"
PRIMARY_INDUSTRY_COLUMN = "Indústria / Principal"
FALLBACK_INDUSTRY_COLUMN = "Indústria"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Transforma um relatório operacional em um event log "
            "estruturado para análise de fluxo."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Caminho do arquivo Excel de entrada.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/output/event_log.csv"),
        help="Caminho do arquivo CSV de saída.",
    )

    return parser.parse_args()


def normalize_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=True,
    )


def normalize_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    normalized = (
        series.astype("string")
        .str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    return pd.to_numeric(normalized, errors="coerce")


def detect_phases(columns: list[str]) -> list[dict[str, str | None]]:
    column_set = set(columns)

    phases: list[dict[str, str | None]] = []

    for column in columns:
        if not column.startswith(ENTRY_PREFIX):
            continue

        phase_name = column[len(ENTRY_PREFIX):].strip()

        exit_column = f"{EXIT_PREFIX}{phase_name}"
        duration_column = (
            f"{DURATION_PREFIX}{phase_name}{DURATION_SUFFIX}"
        )

        phases.append(
            {
                "activity": phase_name,
                "start_column": column,
                "end_column": (
                    exit_column
                    if exit_column in column_set
                    else None
                ),
                "duration_column": (
                    duration_column
                    if duration_column in column_set
                    else None
                ),
            }
        )

    return phases


def validate_required_columns(df: pd.DataFrame) -> None:
    if CASE_ID_COLUMN not in df.columns:
        raise ValueError(
            f"Coluna obrigatória não encontrada: {CASE_ID_COLUMN}"
        )


def get_optional_column(
    df: pd.DataFrame,
    column_name: str,
) -> pd.Series:
    if column_name in df.columns:
        return df[column_name]

    return pd.Series(
        pd.NA,
        index=df.index,
        dtype="object",
    )


def get_industry_column(df: pd.DataFrame) -> pd.Series:
    if PRIMARY_INDUSTRY_COLUMN in df.columns:
        return df[PRIMARY_INDUSTRY_COLUMN]

    if FALLBACK_INDUSTRY_COLUMN in df.columns:
        return df[FALLBACK_INDUSTRY_COLUMN]

    return pd.Series(
        pd.NA,
        index=df.index,
        dtype="object",
    )


def build_phase_events(
    df: pd.DataFrame,
    phase: dict[str, str | None],
) -> pd.DataFrame:

    start_column = phase["start_column"]
    end_column = phase["end_column"]
    duration_column = phase["duration_column"]

    if start_column is None:
        raise ValueError("Fase sem coluna de entrada.")

    start_time = normalize_datetime(df[start_column])

    if end_column:
        end_time = normalize_datetime(df[end_column])
    else:
        end_time = pd.Series(
            pd.NaT,
            index=df.index,
            dtype="datetime64[ns]",
        )

    if duration_column:
        duration_days = normalize_numeric(
            df[duration_column]
        )
    else:
        duration_days = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Float64",
        )

    phase_events = pd.DataFrame(
        {
            "case_id": df[CASE_ID_COLUMN],
            "activity": phase["activity"],
            "start_time": start_time,
            "end_time": end_time,
            "duration_days": duration_days,
            "current_phase": get_optional_column(
                df,
                CURRENT_PHASE_COLUMN,
            ),
            "card_type": get_optional_column(
                df,
                CARD_TYPE_COLUMN,
            ),
            "industry": get_industry_column(df),
            "source_row": df.index + 2,
        }
    )

    phase_events["duration_hours"] = (
        phase_events["duration_days"] * 24
    )

    phase_events["has_start_time"] = (
        phase_events["start_time"].notna()
    )

    phase_events["has_end_time"] = (
        phase_events["end_time"].notna()
    )

    phase_events["is_current_phase"] = (
        phase_events["current_phase"]
        .astype("string")
        .str.strip()
        .eq(str(phase["activity"]).strip())
    )

    has_any_event_information = (
        phase_events["start_time"].notna()
        | phase_events["end_time"].notna()
        | phase_events["duration_days"].notna()
    )

    return phase_events.loc[
        has_any_event_information
    ].copy()


def build_event_log(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, str | None]]]:

    validate_required_columns(df)

    phases = detect_phases(
        [str(column) for column in df.columns]
    )

    if not phases:
        raise ValueError(
            "Nenhuma fase foi identificada no relatório."
        )

    event_frames = [
        build_phase_events(df, phase)
        for phase in phases
    ]

    event_log = pd.concat(
        event_frames,
        ignore_index=True,
    )

    event_log["event_timestamp"] = (
        event_log["start_time"]
        .fillna(event_log["end_time"])
    )

    event_log = event_log.sort_values(
        by=[
            "case_id",
            "event_timestamp",
            "activity",
        ],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)

    event_log["event_order"] = (
        event_log.groupby(
            "case_id",
            dropna=False,
        ).cumcount()
        + 1
    )

    final_columns = [
        "case_id",
        "event_order",
        "activity",
        "event_timestamp",
        "start_time",
        "end_time",
        "duration_days",
        "duration_hours",
        "current_phase",
        "is_current_phase",
        "card_type",
        "industry",
        "has_start_time",
        "has_end_time",
        "source_row",
    ]

    return event_log[final_columns], phases


def print_summary(
    source_df: pd.DataFrame,
    event_log: pd.DataFrame,
    phases: list[dict[str, str | None]],
    output_path: Path,
) -> None:

    cases_in_source = source_df[CASE_ID_COLUMN].nunique(
        dropna=True
    )

    cases_with_events = event_log["case_id"].nunique(
        dropna=True
    )

    print()
    print("=" * 64)
    print("OPERATIONAL FLOW INTELLIGENCE")
    print("Data-to-Event-Log Engine")
    print("=" * 64)

    print(f"Registros de origem : {len(source_df):,}")
    print(f"Casos únicos         : {cases_in_source:,}")
    print(f"Fases detectadas     : {len(phases):,}")
    print(f"Eventos gerados      : {len(event_log):,}")
    print(f"Casos com eventos    : {cases_with_events:,}")

    print()
    print("Fases encontradas:")

    for index, phase in enumerate(phases, start=1):
        print(
            f"  {index:02d}. {phase['activity']}"
        )

    print()
    print("Arquivo gerado:")
    print(f"  {output_path.resolve()}")

    print("=" * 64)
    print()


def main() -> None:
    args = parse_arguments()

    input_path = args.input_file.resolve()
    output_path = args.output.resolve()

    if not input_path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {input_path}"
        )

    if input_path.suffix.lower() not in {
        ".xlsx",
        ".xlsm",
    }:
        raise ValueError(
            "O arquivo de entrada deve ser .xlsx ou .xlsm."
        )

    print()
    print("Lendo arquivo:")
    print(f"  {input_path}")

    source_df = pd.read_excel(
        input_path,
        sheet_name="Report",
        engine="openpyxl",
    )

    source_df.columns = [
        str(column).strip()
        for column in source_df.columns
    ]

    event_log, phases = build_event_log(
        source_df
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    event_log.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%d %H:%M:%S",
    )

    print_summary(
        source_df=source_df,
        event_log=event_log,
        phases=phases,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()