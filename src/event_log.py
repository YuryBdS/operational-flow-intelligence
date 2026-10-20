from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


# =========================================================
# Configuration models
# =========================================================


@dataclass(frozen=True)
class SourceMapping:
    mapping_name: str
    sheet_name: str

    case_id_columns: tuple[str, ...]
    current_phase_columns: tuple[str, ...]
    card_type_columns: tuple[str, ...]
    industry_columns: tuple[str, ...]

    entry_prefix: str
    exit_prefix: str
    duration_prefix: str
    duration_suffix: str
    duration_unit: str


@dataclass(frozen=True)
class ResolvedColumns:
    case_id: str
    current_phase: str | None
    card_type: str | None
    industry: str | None


# =========================================================
# CLI
# =========================================================


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Transforma um relatório operacional em um event log "
            "estruturado usando um source mapping configurável."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Caminho do arquivo Excel de entrada.",
    )

    parser.add_argument(
        "-m",
        "--mapping",
        type=Path,
        required=True,
        help="Arquivo JSON com o mapeamento da fonte.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/output/event_log.csv"),
        help="Caminho do arquivo CSV de saída.",
    )

    return parser.parse_args()


# =========================================================
# Mapping loader
# =========================================================


def normalize_candidates(
    value: Any,
    field_name: str,
    *,
    required: bool,
) -> tuple[str, ...]:
    if value is None:
        if required:
            raise ValueError(
                f"Campo obrigatório ausente no mapping: {field_name}"
            )
        return ()

    if isinstance(value, str):
        candidates = [value]

    elif isinstance(value, list):
        candidates = [
            str(item)
            for item in value
            if str(item).strip()
        ]

    else:
        raise ValueError(
            f"O campo '{field_name}' deve ser string ou lista."
        )

    normalized = tuple(
        candidate.strip()
        for candidate in candidates
        if candidate.strip()
    )

    if required and not normalized:
        raise ValueError(
            f"O campo '{field_name}' não pode estar vazio."
        )

    return normalized


def require_mapping_text(
    payload: dict[str, Any],
    field_name: str,
) -> str:
    value = payload.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Campo obrigatório inválido no mapping: {field_name}"
        )

    return value


def load_source_mapping(
    mapping_path: Path,
) -> SourceMapping:
    try:
        with mapping_path.open(
            "r",
            encoding="utf-8-sig",
        ) as file:
            payload = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON inválido em {mapping_path}: {error}"
        ) from error

    if not isinstance(payload, dict):
        raise ValueError(
            "O source mapping deve possuir um objeto JSON na raiz."
        )

    columns = payload.get("columns")

    if not isinstance(columns, dict):
        raise ValueError(
            "O mapping deve possuir o objeto 'columns'."
        )

    phase_history = payload.get("phase_history")

    if not isinstance(phase_history, dict):
        raise ValueError(
            "O mapping deve possuir o objeto 'phase_history'."
        )

    mapping_name = str(
        payload.get("mapping_name")
        or mapping_path.stem
    ).strip()

    sheet_name = require_mapping_text(
        payload,
        "sheet_name",
    )

    entry_prefix = require_mapping_text(
        phase_history,
        "entry_prefix",
    )

    exit_prefix = require_mapping_text(
        phase_history,
        "exit_prefix",
    )

    duration_prefix = require_mapping_text(
        phase_history,
        "duration_prefix",
    )

    duration_suffix = str(
        phase_history.get("duration_suffix", "")
    )

    duration_unit = str(
        phase_history.get("duration_unit", "days")
    ).strip().lower()

    supported_duration_units = {
        "days",
        "hours",
        "minutes",
        "seconds",
    }

    if duration_unit not in supported_duration_units:
        raise ValueError(
            "duration_unit não suportado. "
            "Use: days, hours, minutes ou seconds."
        )

    return SourceMapping(
        mapping_name=mapping_name,
        sheet_name=sheet_name,
        case_id_columns=normalize_candidates(
            columns.get("case_id"),
            "columns.case_id",
            required=True,
        ),
        current_phase_columns=normalize_candidates(
            columns.get("current_phase"),
            "columns.current_phase",
            required=False,
        ),
        card_type_columns=normalize_candidates(
            columns.get("card_type"),
            "columns.card_type",
            required=False,
        ),
        industry_columns=normalize_candidates(
            columns.get("industry"),
            "columns.industry",
            required=False,
        ),
        entry_prefix=entry_prefix,
        exit_prefix=exit_prefix,
        duration_prefix=duration_prefix,
        duration_suffix=duration_suffix,
        duration_unit=duration_unit,
    )


# =========================================================
# Source-column resolution
# =========================================================


def resolve_column(
    available_columns: list[str],
    candidates: tuple[str, ...],
) -> str | None:
    available = set(available_columns)

    for candidate in candidates:
        if candidate in available:
            return candidate

    return None


def resolve_source_columns(
    df: pd.DataFrame,
    mapping: SourceMapping,
) -> ResolvedColumns:
    available_columns = [
        str(column)
        for column in df.columns
    ]

    case_id = resolve_column(
        available_columns,
        mapping.case_id_columns,
    )

    if case_id is None:
        expected = ", ".join(
            mapping.case_id_columns
        )

        raise ValueError(
            "Nenhuma coluna configurada para case_id "
            f"foi encontrada. Esperado: {expected}"
        )

    return ResolvedColumns(
        case_id=case_id,
        current_phase=resolve_column(
            available_columns,
            mapping.current_phase_columns,
        ),
        card_type=resolve_column(
            available_columns,
            mapping.card_type_columns,
        ),
        industry=resolve_column(
            available_columns,
            mapping.industry_columns,
        ),
    )


# =========================================================
# Data normalization
# =========================================================


def normalize_datetime(
    series: pd.Series,
) -> pd.Series:
    return pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=True,
    )


def normalize_numeric(
    series: pd.Series,
) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(
            series,
            errors="coerce",
        )

    normalized = (
        series.astype("string")
        .str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    return pd.to_numeric(
        normalized,
        errors="coerce",
    )


def convert_duration_to_days(
    series: pd.Series,
    unit: str,
) -> pd.Series:
    numeric = normalize_numeric(series)

    conversion_factors = {
        "days": 1.0,
        "hours": 1 / 24,
        "minutes": 1 / (24 * 60),
        "seconds": 1 / (24 * 60 * 60),
    }

    return numeric * conversion_factors[unit]


def empty_series(
    df: pd.DataFrame,
) -> pd.Series:
    return pd.Series(
        pd.NA,
        index=df.index,
        dtype="object",
    )


def get_resolved_column(
    df: pd.DataFrame,
    column_name: str | None,
) -> pd.Series:
    if column_name is None:
        return empty_series(df)

    return df[column_name]


# =========================================================
# Phase discovery
# =========================================================


def detect_phases(
    columns: list[str],
    mapping: SourceMapping,
) -> list[dict[str, str | None]]:
    column_set = set(columns)

    phases: list[
        dict[str, str | None]
    ] = []

    for column in columns:
        if not column.startswith(
            mapping.entry_prefix
        ):
            continue

        phase_name = column[
            len(mapping.entry_prefix):
        ].strip()

        if not phase_name:
            continue

        exit_column = (
            f"{mapping.exit_prefix}"
            f"{phase_name}"
        )

        duration_column = (
            f"{mapping.duration_prefix}"
            f"{phase_name}"
            f"{mapping.duration_suffix}"
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


# =========================================================
# Event-log construction
# =========================================================


def build_phase_events(
    df: pd.DataFrame,
    phase: dict[str, str | None],
    mapping: SourceMapping,
    resolved: ResolvedColumns,
) -> pd.DataFrame:
    start_column = phase["start_column"]
    end_column = phase["end_column"]
    duration_column = phase[
        "duration_column"
    ]

    if start_column is None:
        raise ValueError(
            "Fase sem coluna de entrada."
        )

    start_time = normalize_datetime(
        df[start_column]
    )

    if end_column:
        end_time = normalize_datetime(
            df[end_column]
        )

    else:
        end_time = pd.Series(
            pd.NaT,
            index=df.index,
            dtype="datetime64[ns]",
        )

    if duration_column:
        duration_days = (
            convert_duration_to_days(
                df[duration_column],
                mapping.duration_unit,
            )
        )

    else:
        duration_days = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Float64",
        )

    phase_events = pd.DataFrame(
        {
            "case_id": df[
                resolved.case_id
            ],
            "activity": phase[
                "activity"
            ],
            "start_time": start_time,
            "end_time": end_time,
            "duration_days": (
                duration_days
            ),
            "current_phase": (
                get_resolved_column(
                    df,
                    resolved.current_phase,
                )
            ),
            "card_type": (
                get_resolved_column(
                    df,
                    resolved.card_type,
                )
            ),
            "industry": (
                get_resolved_column(
                    df,
                    resolved.industry,
                )
            ),
            "source_row": (
                df.index + 2
            ),
        }
    )

    phase_events["duration_hours"] = (
        phase_events[
            "duration_days"
        ]
        * 24
    )

    phase_events[
        "has_start_time"
    ] = (
        phase_events[
            "start_time"
        ].notna()
    )

    phase_events[
        "has_end_time"
    ] = (
        phase_events[
            "end_time"
        ].notna()
    )

    phase_events[
        "is_current_phase"
    ] = (
        phase_events[
            "current_phase"
        ]
        .astype("string")
        .str.strip()
        .eq(
            str(
                phase["activity"]
            ).strip()
        )
    )

    has_any_event_information = (
        phase_events[
            "start_time"
        ].notna()
        | phase_events[
            "end_time"
        ].notna()
        | phase_events[
            "duration_days"
        ].notna()
    )

    return phase_events.loc[
        has_any_event_information
    ].copy()


def build_event_log(
    df: pd.DataFrame,
    mapping: SourceMapping,
) -> tuple[
    pd.DataFrame,
    list[dict[str, str | None]],
    ResolvedColumns,
]:
    resolved = resolve_source_columns(
        df,
        mapping,
    )

    phases = detect_phases(
        [
            str(column)
            for column in df.columns
        ],
        mapping,
    )

    if not phases:
        raise ValueError(
            "Nenhuma fase foi identificada "
            "usando o phase_history configurado."
        )

    event_frames = [
        build_phase_events(
            df=df,
            phase=phase,
            mapping=mapping,
            resolved=resolved,
        )
        for phase in phases
    ]

    event_log = pd.concat(
        event_frames,
        ignore_index=True,
    )

    event_log[
        "event_timestamp"
    ] = (
        event_log[
            "start_time"
        ]
        .fillna(
            event_log[
                "end_time"
            ]
        )
    )

    event_log = (
        event_log.sort_values(
            by=[
                "case_id",
                "event_timestamp",
                "activity",
            ],
            kind="stable",
            na_position="last",
        )
        .reset_index(
            drop=True
        )
    )

    event_log[
        "event_order"
    ] = (
        event_log.groupby(
            "case_id",
            dropna=False,
        )
        .cumcount()
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

    return (
        event_log[
            final_columns
        ],
        phases,
        resolved,
    )


# =========================================================
# Summary
# =========================================================


def print_summary(
    source_df: pd.DataFrame,
    event_log: pd.DataFrame,
    phases: list[
        dict[str, str | None]
    ],
    mapping: SourceMapping,
    resolved: ResolvedColumns,
    output_path: Path,
) -> None:
    cases_in_source = (
        source_df[
            resolved.case_id
        ]
        .nunique(
            dropna=True
        )
    )

    cases_with_events = (
        event_log[
            "case_id"
        ]
        .nunique(
            dropna=True
        )
    )

    print()
    print("=" * 72)
    print(
        "OPERATIONAL FLOW INTELLIGENCE"
    )
    print(
        "Data-to-Event-Log Engine"
    )
    print("=" * 72)

    print(
        f"Mapping              : "
        f"{mapping.mapping_name}"
    )

    print(
        f"Worksheet            : "
        f"{mapping.sheet_name}"
    )

    print(
        f"Case ID source       : "
        f"{resolved.case_id}"
    )

    print(
        f"Registros de origem  : "
        f"{len(source_df):,}"
    )

    print(
        f"Casos únicos         : "
        f"{cases_in_source:,}"
    )

    print(
        f"Fases detectadas     : "
        f"{len(phases):,}"
    )

    print(
        f"Eventos gerados      : "
        f"{len(event_log):,}"
    )

    print(
        f"Casos com eventos    : "
        f"{cases_with_events:,}"
    )

    print()
    print(
        "Colunas opcionais resolvidas:"
    )

    print(
        f"  current_phase : "
        f"{resolved.current_phase}"
    )

    print(
        f"  card_type     : "
        f"{resolved.card_type}"
    )

    print(
        f"  industry      : "
        f"{resolved.industry}"
    )

    print()
    print(
        "Fases encontradas:"
    )

    for index, phase in enumerate(
        phases,
        start=1,
    ):
        print(
            f"  {index:02d}. "
            f"{phase['activity']}"
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

    input_path = (
        args.input_file.resolve()
    )

    mapping_path = (
        args.mapping.resolve()
    )

    output_path = (
        args.output.resolve()
    )

    if not input_path.exists():
        raise FileNotFoundError(
            "Arquivo de entrada "
            f"não encontrado: {input_path}"
        )

    if not mapping_path.exists():
        raise FileNotFoundError(
            "Source mapping "
            f"não encontrado: {mapping_path}"
        )

    if input_path.suffix.lower() not in {
        ".xlsx",
        ".xlsm",
    }:
        raise ValueError(
            "O arquivo de entrada deve "
            "ser .xlsx ou .xlsm."
        )

    mapping = load_source_mapping(
        mapping_path
    )

    print()
    print(
        "Lendo arquivo:"
    )
    print(
        f"  {input_path}"
    )

    print(
        "Usando mapping:"
    )
    print(
        f"  {mapping_path}"
    )

    source_df = pd.read_excel(
        input_path,
        sheet_name=mapping.sheet_name,
        engine="openpyxl",
    )

    source_df.columns = [
        str(column).strip()
        for column in source_df.columns
    ]

    (
        event_log,
        phases,
        resolved,
    ) = build_event_log(
        source_df,
        mapping,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    event_log.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
        date_format=(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print_summary(
        source_df=source_df,
        event_log=event_log,
        phases=phases,
        mapping=mapping,
        resolved=resolved,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()