from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


CORE_PATH = [
    "Caixa de entrada",
    "Tratamento de dados",
    "Upload no Magento",
    "Lançado / Aguardando início",
    "QA Promos vigentes",
    "Promos vigentes validadas",
    "Promos Encerradas",
]

EXCEPTION_ACTIVITIES = {
    "Pendência solicitante",
    "Retorno de Pendência",
}

EXIT_ACTIVITIES = {
    "Canceladas / Rejeitadas",
}

OPTIONAL_RULE_ACTIVITIES = {
    "Priorização",
    "Validação Lançados no Magento",
}

OPERATIONAL_ACTIVITIES = {
    "Caixa de entrada",
    "Priorização",
    "Tratamento de dados",
    "Pendência solicitante",
    "Retorno de Pendência",
    "Validação Lançados no Magento",
    "Upload no Magento",
    "QA Promos vigentes",
}

WAITING_ACTIVITIES = {
    "Lançado / Aguardando início",
    "Promos vigentes validadas",
}

TERMINAL_ACTIVITIES = {
    "Promos Encerradas",
    "Canceladas / Rejeitadas",
}

PATH_SEPARATOR = " → "


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classifica variantes e transições descobertas "
            "em sinais de comportamento operacional."
        )
    )

    parser.add_argument(
        "discovery_dir",
        nargs="?",
        type=Path,
        default=Path("data/output/discovery"),
        help=(
            "Diretório com os arquivos gerados pelo "
            "Process Discovery Engine."
        ),
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("data/output/intelligence"),
        help=(
            "Diretório onde os resultados de inteligência "
            "serão gerados."
        ),
    )

    return parser.parse_args()


def load_csv(
    path: Path,
    required_columns: set[str],
) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {path}"
        )

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
    )

    missing = required_columns - set(df.columns)

    if missing:
        missing_text = ", ".join(
            sorted(missing)
        )

        raise ValueError(
            f"Arquivo {path.name} sem colunas obrigatórias: "
            f"{missing_text}"
        )

    return df


def get_core_transition_set() -> set[tuple[str, str]]:
    return set(
        zip(
            CORE_PATH[:-1],
            CORE_PATH[1:],
        )
    )


def classify_transition(
    source: str,
    target: str,
) -> str:
    source = str(source).strip()
    target = str(target).strip()

    core_transitions = get_core_transition_set()

    if target in EXIT_ACTIVITIES:
        return "Exit Flow"

    if (
        source in EXCEPTION_ACTIVITIES
        or target in EXCEPTION_ACTIVITIES
    ):
        return "Exception Flow"

    if (
        source,
        target,
    ) in core_transitions:
        return "Core Flow"

    if (
        source in OPTIONAL_RULE_ACTIVITIES
        or target in OPTIONAL_RULE_ACTIVITIES
    ):
        return "Optional / Rule Flow"

    core_position = {
        activity: index
        for index, activity in enumerate(
            CORE_PATH
        )
    }

    if (
        source in core_position
        and target in core_position
    ):
        source_position = core_position[source]
        target_position = core_position[target]

        if (
            target_position
            > source_position + 1
        ):
            return "Bypass Flow"

        if (
            target_position
            <= source_position
        ):
            return "Reverse / Deviation Flow"

    return "Other Flow"


def classify_transitions(
    transitions: pd.DataFrame,
) -> pd.DataFrame:
    result = transitions.copy()

    result["case_count"] = pd.to_numeric(
        result["case_count"],
        errors="coerce",
    ).fillna(0)

    result["outgoing_share_pct"] = (
        pd.to_numeric(
            result["outgoing_share_pct"],
            errors="coerce",
        )
    )

    result["flow_class"] = result.apply(
        lambda row: classify_transition(
            row["source_activity"],
            row["target_activity"],
        ),
        axis=1,
    )

    result["transition"] = (
        result["source_activity"]
        .astype(str)
        + PATH_SEPARATOR
        + result["target_activity"]
        .astype(str)
    )

    class_priority = {
        "Core Flow": 1,
        "Exception Flow": 2,
        "Exit Flow": 3,
        "Bypass Flow": 4,
        "Optional / Rule Flow": 5,
        "Reverse / Deviation Flow": 6,
        "Other Flow": 7,
    }

    result["class_order"] = (
        result["flow_class"]
        .map(class_priority)
        .fillna(99)
    )

    result = result.sort_values(
        by=[
            "class_order",
            "case_count",
        ],
        ascending=[
            True,
            False,
        ],
        kind="stable",
    ).reset_index(drop=True)

    return result


def split_path(path: str) -> list[str]:
    if pd.isna(path):
        return []

    return [
        item.strip()
        for item in str(path).split(
            PATH_SEPARATOR
        )
        if item.strip()
    ]


def analyze_variant_path(
    path: str,
) -> dict[str, object]:
    activities = split_path(path)

    transitions = list(
        zip(
            activities[:-1],
            activities[1:],
        )
    )

    transition_classes = [
        classify_transition(
            source,
            target,
        )
        for source, target in transitions
    ]

    has_exception = any(
        activity in EXCEPTION_ACTIVITIES
        for activity in activities
    )

    has_exit = any(
        activity in EXIT_ACTIVITIES
        for activity in activities
    )

    has_optional_rule = any(
        activity in OPTIONAL_RULE_ACTIVITIES
        for activity in activities
    )

    bypass_count = sum(
        flow_class == "Bypass Flow"
        for flow_class in transition_classes
    )

    reverse_deviation_count = sum(
        flow_class
        == "Reverse / Deviation Flow"
        for flow_class in transition_classes
    )

    exact_core_path = (
        activities == CORE_PATH
    )

    if exact_core_path:
        primary_class = "Core Flow"

    elif has_exit:
        primary_class = "Exit Flow"

    elif has_exception:
        primary_class = "Exception Flow"

    elif bypass_count > 0:
        primary_class = "Bypass Flow"

    elif has_optional_rule:
        primary_class = (
            "Optional / Rule Flow"
        )

    elif reverse_deviation_count > 0:
        primary_class = (
            "Reverse / Deviation Flow"
        )

    else:
        primary_class = "Other Flow"

    return {
        "primary_flow_class": primary_class,
        "exact_core_path": exact_core_path,
        "has_exception": has_exception,
        "has_exit": has_exit,
        "has_optional_rule": (
            has_optional_rule
        ),
        "bypass_count": bypass_count,
        "reverse_deviation_count": (
            reverse_deviation_count
        ),
    }


def classify_variants(
    variants: pd.DataFrame,
) -> pd.DataFrame:
    result = variants.copy()

    result["case_count"] = pd.to_numeric(
        result["case_count"],
        errors="coerce",
    ).fillna(0)

    analyses = (
        result["path"]
        .apply(analyze_variant_path)
        .apply(pd.Series)
    )

    result = pd.concat(
        [
            result,
            analyses,
        ],
        axis=1,
    )

    return result


def classify_activity_type(
    activity: str,
) -> str:
    activity = str(activity).strip()

    if activity in TERMINAL_ACTIVITIES:
        return "Terminal State"

    if activity in WAITING_ACTIVITIES:
        return "Business Waiting"

    if activity in OPERATIONAL_ACTIVITIES:
        return "Operational"

    return "Unclassified"


def build_activity_intelligence(
    activity_summary: pd.DataFrame,
) -> pd.DataFrame:
    result = activity_summary.copy()

    numeric_columns = [
        "cases",
        "events",
        "avg_duration_hours",
        "median_duration_hours",
        "case_coverage_pct",
    ]

    for column in numeric_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

    result["activity_type"] = (
        result["activity"]
        .apply(
            classify_activity_type
        )
    )

    interpretation_map = {
        "Operational": (
            "Tempo útil para análise operacional, "
            "com validação de contexto."
        ),
        "Business Waiting": (
            "Tempo de espera ou ciclo de negócio; "
            "não interpretar automaticamente como esforço."
        ),
        "Terminal State": (
            "Estado final do processo; duração não deve "
            "ser tratada como gargalo operacional."
        ),
        "Unclassified": (
            "Atividade ainda sem classificação analítica."
        ),
    }

    result["duration_interpretation"] = (
        result["activity_type"]
        .map(interpretation_map)
    )

    return result


def build_flow_summary(
    classified_variants: pd.DataFrame,
) -> pd.DataFrame:
    total_cases = (
        classified_variants[
            "case_count"
        ].sum()
    )

    summary = (
        classified_variants
        .groupby(
            "primary_flow_class",
            dropna=False,
        )
        .agg(
            cases=(
                "case_count",
                "sum",
            ),
            variants=(
                "variant_id",
                "count",
            ),
        )
        .reset_index()
    )

    summary["share_pct"] = (
        summary["cases"]
        / total_cases
        * 100
    )

    summary = summary.sort_values(
        by="cases",
        ascending=False,
        kind="stable",
    ).reset_index(drop=True)

    return summary


def build_transition_summary(
    classified_transitions: pd.DataFrame,
) -> pd.DataFrame:
    summary = (
        classified_transitions
        .groupby(
            "flow_class",
            dropna=False,
        )
        .agg(
            transition_pairs=(
                "transition",
                "count",
            ),
            transition_case_occurrences=(
                "case_count",
                "sum",
            ),
        )
        .reset_index()
    )

    total_occurrences = (
        summary[
            "transition_case_occurrences"
        ].sum()
    )

    summary[
        "transition_volume_share_pct"
    ] = (
        summary[
            "transition_case_occurrences"
        ]
        / total_occurrences
        * 100
    )

    summary = summary.sort_values(
        by="transition_case_occurrences",
        ascending=False,
        kind="stable",
    ).reset_index(drop=True)

    return summary


def build_insights(
    classified_variants: pd.DataFrame,
    classified_transitions: pd.DataFrame,
    activity_intelligence: pd.DataFrame,
) -> list[str]:
    insights: list[str] = []

    total_cases = (
        classified_variants[
            "case_count"
        ].sum()
    )

    exact_core_cases = (
        classified_variants.loc[
            classified_variants[
                "exact_core_path"
            ],
            "case_count",
        ].sum()
    )

    if total_cases > 0:
        core_share = (
            exact_core_cases
            / total_cases
            * 100
        )

        insights.append(
            "O caminho principal completo representa "
            f"{core_share:.2f}% dos casos analisados."
        )

    exception_cases = (
        classified_variants.loc[
            classified_variants[
                "has_exception"
            ],
            "case_count",
        ].sum()
    )

    if total_cases > 0:
        exception_share = (
            exception_cases
            / total_cases
            * 100
        )

        insights.append(
            "Caminhos contendo pendência ou retorno "
            f"aparecem em {exception_share:.2f}% "
            "dos casos."
        )

    exit_cases = (
        classified_variants.loc[
            classified_variants[
                "has_exit"
            ],
            "case_count",
        ].sum()
    )

    if total_cases > 0:
        exit_share = (
            exit_cases
            / total_cases
            * 100
        )

        insights.append(
            "Caminhos contendo cancelamento ou rejeição "
            f"aparecem em {exit_share:.2f}% "
            "dos casos."
        )

    bypass_transitions = (
        classified_transitions.loc[
            classified_transitions[
                "flow_class"
            ]
            == "Bypass Flow"
        ]
        .sort_values(
            by="case_count",
            ascending=False,
        )
    )

    if not bypass_transitions.empty:
        top_bypass = (
            bypass_transitions.iloc[0]
        )

        insights.append(
            "O bypass de maior volume observado é "
            f"'{top_bypass['transition']}', "
            f"presente em "
            f"{int(top_bypass['case_count']):,} "
            "casos da transição observada."
        )

    operational_activities = (
        activity_intelligence.loc[
            activity_intelligence[
                "activity_type"
            ]
            == "Operational"
        ]
        .dropna(
            subset=[
                "median_duration_hours"
            ]
        )
        .sort_values(
            by="median_duration_hours",
            ascending=False,
        )
    )

    if not operational_activities.empty:
        top_operational = (
            operational_activities.iloc[0]
        )

        insights.append(
            "Entre as fases classificadas como "
            "operacionais, a maior mediana de duração "
            f"é observada em "
            f"'{top_operational['activity']}' "
            f"({top_operational['median_duration_hours']:.2f} h)."
        )

    insights.append(
        "As classificações são sinais analíticos "
        "baseados no histórico disponível e não "
        "substituem validação do processo com o "
        "responsável operacional."
    )

    return insights


def save_results(
    classified_variants: pd.DataFrame,
    classified_transitions: pd.DataFrame,
    activity_intelligence: pd.DataFrame,
    flow_summary: pd.DataFrame,
    transition_summary: pd.DataFrame,
    insights: list[str],
    output_dir: Path,
) -> None:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    classified_variants.to_csv(
        output_dir
        / "classified_variants.csv",
        index=False,
        encoding="utf-8-sig",
    )

    classified_transitions.to_csv(
        output_dir
        / "classified_transitions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    activity_intelligence.to_csv(
        output_dir
        / "activity_intelligence.csv",
        index=False,
        encoding="utf-8-sig",
    )

    flow_summary.to_csv(
        output_dir
        / "flow_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    transition_summary.to_csv(
        output_dir
        / "transition_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    with (
        output_dir
        / "insights.txt"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        for index, insight in enumerate(
            insights,
            start=1,
        ):
            file.write(
                f"{index}. {insight}\n"
            )


def print_summary(
    flow_summary: pd.DataFrame,
    classified_transitions: pd.DataFrame,
    insights: list[str],
    output_dir: Path,
) -> None:
    print()
    print("=" * 76)
    print(
        "OPERATIONAL FLOW INTELLIGENCE"
    )
    print(
        "Flow Intelligence Engine"
    )
    print("=" * 76)

    print()
    print(
        "Distribuição dos casos "
        "por classificação principal:"
    )

    for _, row in (
        flow_summary.iterrows()
    ):
        print(
            f"  {row['primary_flow_class']:<28} "
            f"{int(row['cases']):>7,} casos | "
            f"{row['share_pct']:>6.2f}% | "
            f"{int(row['variants']):>4} variantes"
        )

    bypasses = (
        classified_transitions.loc[
            classified_transitions[
                "flow_class"
            ]
            == "Bypass Flow"
        ]
        .sort_values(
            by="case_count",
            ascending=False,
        )
        .head(5)
    )

    if not bypasses.empty:
        print()
        print(
            "Principais bypasses observados:"
        )

        for _, row in bypasses.iterrows():
            print(
                f"  {int(row['case_count']):>7,} | "
                f"{row['transition']}"
            )

    print()
    print("Insights iniciais:")

    for index, insight in enumerate(
        insights,
        start=1,
    ):
        print(
            f"  {index}. {insight}"
        )

    print()
    print("Arquivos gerados:")
    print(
        f"  {output_dir.resolve()}"
    )

    print("=" * 76)
    print()


def main() -> None:
    args = parse_arguments()

    discovery_dir = (
        args.discovery_dir.resolve()
    )

    output_dir = (
        args.output_dir.resolve()
    )

    variants = load_csv(
        discovery_dir
        / "variants.csv",
        {
            "variant_id",
            "path",
            "case_count",
            "share_pct",
        },
    )

    transitions = load_csv(
        discovery_dir
        / "transitions.csv",
        {
            "source_activity",
            "target_activity",
            "case_count",
            "outgoing_share_pct",
        },
    )

    activity_summary = load_csv(
        discovery_dir
        / "activity_summary.csv",
        {
            "activity",
            "cases",
            "events",
            "case_coverage_pct",
            "avg_duration_hours",
            "median_duration_hours",
        },
    )

    classified_transitions = (
        classify_transitions(
            transitions
        )
    )

    classified_variants = (
        classify_variants(
            variants
        )
    )

    activity_intelligence = (
        build_activity_intelligence(
            activity_summary
        )
    )

    flow_summary = (
        build_flow_summary(
            classified_variants
        )
    )

    transition_summary = (
        build_transition_summary(
            classified_transitions
        )
    )

    insights = build_insights(
        classified_variants=(
            classified_variants
        ),
        classified_transitions=(
            classified_transitions
        ),
        activity_intelligence=(
            activity_intelligence
        ),
    )

    save_results(
        classified_variants=(
            classified_variants
        ),
        classified_transitions=(
            classified_transitions
        ),
        activity_intelligence=(
            activity_intelligence
        ),
        flow_summary=flow_summary,
        transition_summary=(
            transition_summary
        ),
        insights=insights,
        output_dir=output_dir,
    )

    print_summary(
        flow_summary=flow_summary,
        classified_transitions=(
            classified_transitions
        ),
        insights=insights,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()