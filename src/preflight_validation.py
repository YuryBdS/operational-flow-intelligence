from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from event_log import (
    detect_phases,
    load_source_mapping,
    resolve_source_columns,
)
from flow_intelligence import load_profile


SUPPORTED_EXTENSIONS = {
    ".xlsx",
    ".xlsm",
}


@dataclass(frozen=True)
class ValidationResult:
    level: str
    check: str
    message: str


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Executa validações de pré-execução para o "
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

    return parser.parse_args()


def add_result(
    results: list[ValidationResult],
    level: str,
    check: str,
    message: str,
) -> None:
    results.append(
        ValidationResult(
            level=level,
            check=check,
            message=message,
        )
    )


def validate_files(
    input_file: Path,
    mapping_file: Path,
    profile_file: Path,
    results: list[ValidationResult],
) -> bool:
    valid = True

    if input_file.exists():
        add_result(
            results,
            "PASS",
            "Input file",
            f"Arquivo encontrado: {input_file.name}",
        )
    else:
        add_result(
            results,
            "FAIL",
            "Input file",
            f"Arquivo não encontrado: {input_file}",
        )
        valid = False

    if mapping_file.exists():
        add_result(
            results,
            "PASS",
            "Source mapping",
            f"Mapping encontrado: {mapping_file.name}",
        )
    else:
        add_result(
            results,
            "FAIL",
            "Source mapping",
            f"Mapping não encontrado: {mapping_file}",
        )
        valid = False

    if profile_file.exists():
        add_result(
            results,
            "PASS",
            "Flow profile",
            f"Profile encontrado: {profile_file.name}",
        )
    else:
        add_result(
            results,
            "FAIL",
            "Flow profile",
            f"Profile não encontrado: {profile_file}",
        )
        valid = False

    if input_file.exists():
        extension = input_file.suffix.lower()

        if extension in SUPPORTED_EXTENSIONS:
            add_result(
                results,
                "PASS",
                "File format",
                f"Formato suportado: {extension}",
            )
        else:
            add_result(
                results,
                "FAIL",
                "File format",
                (
                    f"Formato não suportado: {extension}. "
                    "Use .xlsx ou .xlsm."
                ),
            )
            valid = False

    return valid


def validate_workbook(
    input_file: Path,
    mapping_file: Path,
    profile_file: Path,
    results: list[ValidationResult],
) -> None:
    try:
        mapping = load_source_mapping(
            mapping_file
        )

        add_result(
            results,
            "PASS",
            "Mapping syntax",
            (
                "Source mapping carregado: "
                f"{mapping.mapping_name}"
            ),
        )

    except Exception as error:
        add_result(
            results,
            "FAIL",
            "Mapping syntax",
            str(error),
        )
        return

    try:
        profile = load_profile(
            profile_file
        )

        add_result(
            results,
            "PASS",
            "Profile syntax",
            (
                "Flow profile carregado: "
                f"{profile.profile_name}"
            ),
        )

    except Exception as error:
        add_result(
            results,
            "FAIL",
            "Profile syntax",
            str(error),
        )
        return

    try:
        excel_file = pd.ExcelFile(
            input_file,
            engine="openpyxl",
        )

        sheet_names = excel_file.sheet_names

        excel_file.close()

    except Exception as error:
        add_result(
            results,
            "FAIL",
            "Workbook",
            (
                "Não foi possível abrir o workbook: "
                f"{error}"
            ),
        )
        return

    if mapping.sheet_name not in sheet_names:
        add_result(
            results,
            "FAIL",
            "Worksheet",
            (
                f"Worksheet '{mapping.sheet_name}' "
                "não encontrada. "
                f"Disponíveis: {', '.join(sheet_names)}"
            ),
        )
        return

    add_result(
        results,
        "PASS",
        "Worksheet",
        (
            f"Worksheet encontrada: "
            f"{mapping.sheet_name}"
        ),
    )

    try:
        header_df = pd.read_excel(
            input_file,
            sheet_name=mapping.sheet_name,
            engine="openpyxl",
            nrows=0,
        )

    except Exception as error:
        add_result(
            results,
            "FAIL",
            "Header",
            (
                "Não foi possível ler o cabeçalho: "
                f"{error}"
            ),
        )
        return

    header_df.columns = [
        str(column).strip()
        for column in header_df.columns
    ]

    try:
        resolved = resolve_source_columns(
            header_df,
            mapping,
        )

        add_result(
            results,
            "PASS",
            "Case ID mapping",
            (
                "Coluna de case_id resolvida: "
                f"{resolved.case_id}"
            ),
        )

    except Exception as error:
        add_result(
            results,
            "FAIL",
            "Case ID mapping",
            str(error),
        )
        return

    optional_columns = {
        "current_phase": (
            resolved.current_phase
        ),
        "card_type": (
            resolved.card_type
        ),
        "industry": (
            resolved.industry
        ),
    }

    for field_name, column_name in (
        optional_columns.items()
    ):
        if column_name:
            add_result(
                results,
                "PASS",
                f"Optional field: {field_name}",
                (
                    "Coluna resolvida: "
                    f"{column_name}"
                ),
            )
        else:
            add_result(
                results,
                "WARN",
                f"Optional field: {field_name}",
                (
                    "Nenhuma coluna configurada "
                    "foi encontrada."
                ),
            )

    phases = detect_phases(
        [
            str(column)
            for column in header_df.columns
        ],
        mapping,
    )

    if not phases:
        add_result(
            results,
            "FAIL",
            "Phase discovery",
            (
                "Nenhuma fase foi detectada "
                "usando o mapping configurado."
            ),
        )
        return

    add_result(
        results,
        "PASS",
        "Phase discovery",
        (
            f"{len(phases)} fases detectadas."
        ),
    )

    phases_without_end = [
        str(phase["activity"])
        for phase in phases
        if phase["end_column"] is None
    ]

    phases_without_duration = [
        str(phase["activity"])
        for phase in phases
        if phase["duration_column"] is None
    ]

    if phases_without_end:
        add_result(
            results,
            "WARN",
            "Phase exit columns",
            (
                f"{len(phases_without_end)} fase(s) "
                "sem coluna de saída: "
                + ", ".join(
                    phases_without_end
                )
            ),
        )
    else:
        add_result(
            results,
            "PASS",
            "Phase exit columns",
            (
                "Todas as fases detectadas possuem "
                "coluna de saída."
            ),
        )

    if phases_without_duration:
        add_result(
            results,
            "WARN",
            "Phase duration columns",
            (
                f"{len(phases_without_duration)} fase(s) "
                "sem coluna de duração: "
                + ", ".join(
                    phases_without_duration
                )
            ),
        )
    else:
        add_result(
            results,
            "PASS",
            "Phase duration columns",
            (
                "Todas as fases detectadas possuem "
                "coluna de duração."
            ),
        )

    detected_activities = {
        str(phase["activity"])
        for phase in phases
    }

    missing_core_activities = [
        activity
        for activity in profile.core_path
        if activity
        not in detected_activities
    ]

    if missing_core_activities:
        add_result(
            results,
            "FAIL",
            "Core path compatibility",
            (
                "Atividades do core_path não foram "
                "encontradas na fonte: "
                + ", ".join(
                    missing_core_activities
                )
            ),
        )
    else:
        add_result(
            results,
            "PASS",
            "Core path compatibility",
            (
                "Todas as atividades do core_path "
                "existem na estrutura da fonte."
            ),
        )

    configured_behavior = (
        set(profile.core_path)
        | set(
            profile.exception_activities
        )
        | set(
            profile.exit_activities
        )
        | set(
            profile.optional_rule_activities
        )
    )

    behavior_not_in_source = sorted(
        configured_behavior
        - detected_activities
    )

    if behavior_not_in_source:
        add_result(
            results,
            "WARN",
            "Behavior profile coverage",
            (
                "Atividades configuradas no profile "
                "não detectadas na fonte: "
                + ", ".join(
                    behavior_not_in_source
                )
            ),
        )
    else:
        add_result(
            results,
            "PASS",
            "Behavior profile coverage",
            (
                "As atividades comportamentais "
                "configuradas estão presentes "
                "na fonte."
            ),
        )

    typed_activities = (
        set(
            profile.operational_activities
        )
        | set(
            profile.waiting_activities
        )
        | set(
            profile.terminal_activities
        )
    )

    untyped_activities = sorted(
        detected_activities
        - typed_activities
    )

    if untyped_activities:
        add_result(
            results,
            "WARN",
            "Activity type coverage",
            (
                "Atividades detectadas sem tipo "
                "analítico configurado: "
                + ", ".join(
                    untyped_activities
                )
            ),
        )
    else:
        add_result(
            results,
            "PASS",
            "Activity type coverage",
            (
                "Todas as atividades detectadas "
                "possuem tipo analítico."
            ),
        )

    validate_case_ids(
        input_file=input_file,
        sheet_name=mapping.sheet_name,
        case_id_column=resolved.case_id,
        results=results,
    )


def validate_case_ids(
    input_file: Path,
    sheet_name: str,
    case_id_column: str,
    results: list[ValidationResult],
) -> None:
    try:
        case_df = pd.read_excel(
            input_file,
            sheet_name=sheet_name,
            engine="openpyxl",
            usecols=[
                case_id_column
            ],
        )

    except Exception as error:
        add_result(
            results,
            "FAIL",
            "Case ID data",
            (
                "Não foi possível analisar os "
                f"case IDs: {error}"
            ),
        )
        return

    case_ids = (
        case_df[
            case_id_column
        ]
        .astype("string")
        .str.strip()
    )

    valid_mask = (
        case_ids.notna()
        & case_ids.ne("")
    )

    valid_case_ids = (
        case_ids[
            valid_mask
        ]
    )

    valid_count = len(
        valid_case_ids
    )

    missing_count = (
        len(case_df)
        - valid_count
    )

    unique_count = (
        valid_case_ids.nunique()
    )

    duplicate_rows = (
        valid_count
        - unique_count
    )

    if valid_count == 0:
        add_result(
            results,
            "FAIL",
            "Case ID data",
            (
                "Nenhum case_id válido foi "
                "encontrado."
            ),
        )
        return

    add_result(
        results,
        "PASS",
        "Case ID data",
        (
            f"{valid_count:,} registros com "
            f"case_id válido e "
            f"{unique_count:,} casos únicos."
        ),
    )

    if missing_count > 0:
        add_result(
            results,
            "WARN",
            "Missing Case IDs",
            (
                f"{missing_count:,} linha(s) "
                "sem case_id válido."
            ),
        )
    else:
        add_result(
            results,
            "PASS",
            "Missing Case IDs",
            "Nenhum case_id vazio encontrado.",
        )

    if duplicate_rows > 0:
        add_result(
            results,
            "WARN",
            "Duplicate Case IDs",
            (
                f"{duplicate_rows:,} registro(s) "
                "adicional(is) compartilham "
                "case_id já existente."
            ),
        )
    else:
        add_result(
            results,
            "PASS",
            "Duplicate Case IDs",
            (
                "Nenhum case_id duplicado "
                "encontrado."
            ),
        )


def print_report(
    input_file: Path,
    mapping_file: Path,
    profile_file: Path,
    results: list[ValidationResult],
) -> None:
    print()
    print("=" * 78)
    print(
        "OPERATIONAL FLOW INTELLIGENCE"
    )
    print(
        "PRE-FLIGHT VALIDATION"
    )
    print("=" * 78)

    print(
        f"Input   : {input_file}"
    )
    print(
        f"Mapping : {mapping_file}"
    )
    print(
        f"Profile : {profile_file}"
    )

    print()
    print("Validation results:")
    print()

    for result in results:
        print(
            f"[{result.level:<4}] "
            f"{result.check}: "
            f"{result.message}"
        )

    pass_count = sum(
        result.level == "PASS"
        for result in results
    )

    warning_count = sum(
        result.level == "WARN"
        for result in results
    )

    failure_count = sum(
        result.level == "FAIL"
        for result in results
    )

    print()
    print("-" * 78)

    print(
        f"PASS : {pass_count}"
    )
    print(
        f"WARN : {warning_count}"
    )
    print(
        f"FAIL : {failure_count}"
    )

    print()

    if failure_count > 0:
        status = "FAILED"

    elif warning_count > 0:
        status = (
            "PASSED WITH WARNINGS"
        )

    else:
        status = "PASSED"

    print(
        f"PRE-FLIGHT STATUS: {status}"
    )

    print("=" * 78)
    print()


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

    results: list[
        ValidationResult
    ] = []

    files_valid = validate_files(
        input_file=input_file,
        mapping_file=mapping_file,
        profile_file=profile_file,
        results=results,
    )

    if files_valid:
        validate_workbook(
            input_file=input_file,
            mapping_file=mapping_file,
            profile_file=profile_file,
            results=results,
        )

    print_report(
        input_file=input_file,
        mapping_file=mapping_file,
        profile_file=profile_file,
        results=results,
    )

    has_failures = any(
        result.level == "FAIL"
        for result in results
    )

    if has_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()