from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PATH_SEPARATOR = " → "

REQUIRED_PROFILE_FIELDS = {
    "profile_name",
    "core_path",
    "exception_activities",
    "exit_activities",
    "optional_rule_activities",
    "operational_activities",
    "waiting_activities",
    "terminal_activities",
}


# =========================================================
# Process profile
# =========================================================

@dataclass(frozen=True)
class FlowProfile:
    profile_name: str
    core_path: tuple[str, ...]
    exception_activities: frozenset[str]
    exit_activities: frozenset[str]
    optional_rule_activities: frozenset[str]
    operational_activities: frozenset[str]
    waiting_activities: frozenset[str]
    terminal_activities: frozenset[str]


def normalize_string_list(
    data: dict[str, object],
    field_name: str,
) -> list[str]:
    value = data.get(field_name)

    if not isinstance(value, list):
        raise ValueError(
            f"Profile field '{field_name}' must be a list."
        )

    normalized: list[str] = []

    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"All values in '{field_name}' must be strings."
            )

        clean_item = item.strip()

        if not clean_item:
            raise ValueError(
                f"Profile field '{field_name}' contains an empty value."
            )

        normalized.append(clean_item)

    return normalized


def validate_profile(
    profile: FlowProfile,
) -> None:
    if len(profile.core_path) < 2:
        raise ValueError(
            "The profile core_path must contain at least two activities."
        )

    if len(set(profile.core_path)) != len(profile.core_path):
        raise ValueError(
            "The profile core_path cannot contain duplicate activities."
        )

    behavior_groups = {
        "exception_activities": (
            profile.exception_activities
        ),
        "exit_activities": (
            profile.exit_activities
        ),
        "optional_rule_activities": (
            profile.optional_rule_activities
        ),
    }

    group_names = list(
        behavior_groups.keys()
    )

    for index, first_name in enumerate(
        group_names
    ):
        for second_name in group_names[
            index + 1:
        ]:
            overlap = (
                behavior_groups[first_name]
                & behavior_groups[second_name]
            )

            if overlap:
                overlap_text = ", ".join(
                    sorted(overlap)
                )

                raise ValueError(
                    "Behavior classifications cannot overlap. "
                    f"'{first_name}' and '{second_name}' share: "
                    f"{overlap_text}"
                )

    activity_type_groups = {
        "operational_activities": (
            profile.operational_activities
        ),
        "waiting_activities": (
            profile.waiting_activities
        ),
        "terminal_activities": (
            profile.terminal_activities
        ),
    }

    type_names = list(
        activity_type_groups.keys()
    )

    for index, first_name in enumerate(
        type_names
    ):
        for second_name in type_names[
            index + 1:
        ]:
            overlap = (
                activity_type_groups[first_name]
                & activity_type_groups[second_name]
            )

            if overlap:
                overlap_text = ", ".join(
                    sorted(overlap)
                )

                raise ValueError(
                    "Activity type classifications cannot overlap. "
                    f"'{first_name}' and '{second_name}' share: "
                    f"{overlap_text}"
                )


def load_profile(
    path: Path,
) -> FlowProfile:
    if not path.exists():
        raise FileNotFoundError(
            f"Flow profile not found: {path}"
        )

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON profile: {path}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError(
            "Flow profile must contain a JSON object."
        )

    missing_fields = (
        REQUIRED_PROFILE_FIELDS
        - set(data.keys())
    )

    if missing_fields:
        missing_text = ", ".join(
            sorted(missing_fields)
        )

        raise ValueError(
            "Flow profile is missing required fields: "
            f"{missing_text}"
        )

    profile_name = data.get(
        "profile_name"
    )

    if (
        not isinstance(
            profile_name,
            str,
        )
        or not profile_name.strip()
    ):
        raise ValueError(
            "Profile field 'profile_name' must be a non-empty string."
        )

    profile = FlowProfile(
        profile_name=(
            profile_name.strip()
        ),
        core_path=tuple(
            normalize_string_list(
                data,
                "core_path",
            )
        ),
        exception_activities=frozenset(
            normalize_string_list(
                data,
                "exception_activities",
            )
        ),
        exit_activities=frozenset(
            normalize_string_list(
                data,
                "exit_activities",
            )
        ),
        optional_rule_activities=frozenset(
            normalize_string_list(
                data,
                "optional_rule_activities",
            )
        ),
        operational_activities=frozenset(
            normalize_string_list(
                data,
                "operational_activities",
            )
        ),
        waiting_activities=frozenset(
            normalize_string_list(
                data,
                "waiting_activities",
            )
        ),
        terminal_activities=frozenset(
            normalize_string_list(
                data,
                "terminal_activities",
            )
        ),
    )

    validate_profile(
        profile
    )

    return profile


# =========================================================
# CLI
# =========================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classifies discovered process variants and "
            "transitions using a configurable flow profile."
        )
    )

    parser.add_argument(
        "discovery_dir",
        nargs="?",
        type=Path,
        default=Path(
            "data/output/discovery"
        ),
        help=(
            "Directory containing Process Discovery outputs. "
            "Default: data/output/discovery"
        ),
    )

    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help=(
            "JSON file containing the process flow profile."
        ),
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path(
            "data/output/intelligence"
        ),
        help=(
            "Directory where Flow Intelligence outputs "
            "will be generated."
        ),
    )

    return parser.parse_args()


# =========================================================
# Data loading
# =========================================================

def load_csv(
    path: Path,
    required_columns: set[str],
) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
    )

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(
                missing_columns
            )
        )

        raise ValueError(
            f"File {path.name} is missing required columns: "
            f"{missing_text}"
        )

    return df


# =========================================================
# Transition intelligence
# =========================================================

def get_core_transition_set(
    profile: FlowProfile,
) -> set[tuple[str, str]]:
    return set(
        zip(
            profile.core_path[:-1],
            profile.core_path[1:],
        )
    )


def get_core_position_map(
    profile: FlowProfile,
) -> dict[str, int]:
    return {
        activity: index
        for index, activity in enumerate(
            profile.core_path
        )
    }


def classify_transition(
    source: str,
    target: str,
    profile: FlowProfile,
) -> str:
    source = str(
        source
    ).strip()

    target = str(
        target
    ).strip()

    core_transitions = (
        get_core_transition_set(
            profile
        )
    )

    if (
        target
        in profile.exit_activities
    ):
        return "Exit Flow"

    if (
        source
        in profile.exception_activities
        or target
        in profile.exception_activities
    ):
        return "Exception Flow"

    if (
        source,
        target,
    ) in core_transitions:
        return "Core Flow"

    if (
        source
        in profile.optional_rule_activities
        or target
        in profile.optional_rule_activities
    ):
        return "Optional / Rule Flow"

    core_position = (
        get_core_position_map(
            profile
        )
    )

    if (
        source in core_position
        and target in core_position
    ):
        source_position = (
            core_position[source]
        )

        target_position = (
            core_position[target]
        )

        if (
            target_position
            > source_position + 1
        ):
            return "Bypass Flow"

        if (
            target_position
            <= source_position
        ):
            return (
                "Reverse / Deviation Flow"
            )

    return "Other Flow"


def classify_transitions(
    transitions: pd.DataFrame,
    profile: FlowProfile,
) -> pd.DataFrame:
    result = transitions.copy()

    result["case_count"] = (
        pd.to_numeric(
            result[
                "case_count"
            ],
            errors="coerce",
        )
        .fillna(0)
    )

    result[
        "outgoing_share_pct"
    ] = pd.to_numeric(
        result[
            "outgoing_share_pct"
        ],
        errors="coerce",
    )

    result["flow_class"] = (
        result.apply(
            lambda row: (
                classify_transition(
                    source=row[
                        "source_activity"
                    ],
                    target=row[
                        "target_activity"
                    ],
                    profile=profile,
                )
            ),
            axis=1,
        )
    )

    result["transition"] = (
        result[
            "source_activity"
        ].astype(str)
        + PATH_SEPARATOR
        + result[
            "target_activity"
        ].astype(str)
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
        result[
            "flow_class"
        ]
        .map(
            class_priority
        )
        .fillna(99)
    )

    result = (
        result
        .sort_values(
            by=[
                "class_order",
                "case_count",
            ],
            ascending=[
                True,
                False,
            ],
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    return result


# =========================================================
# Variant intelligence
# =========================================================

def split_path(
    path: str,
) -> list[str]:
    if pd.isna(
        path
    ):
        return []

    return [
        item.strip()
        for item in str(
            path
        ).split(
            PATH_SEPARATOR
        )
        if item.strip()
    ]


def analyze_variant_path(
    path: str,
    profile: FlowProfile,
) -> dict[str, object]:
    activities = split_path(
        path
    )

    transitions = list(
        zip(
            activities[:-1],
            activities[1:],
        )
    )

    transition_classes = [
        classify_transition(
            source=source,
            target=target,
            profile=profile,
        )
        for source, target in transitions
    ]

    has_exception = any(
        activity
        in profile.exception_activities
        for activity in activities
    )

    has_exit = any(
        activity
        in profile.exit_activities
        for activity in activities
    )

    has_optional_rule = any(
        activity
        in profile.optional_rule_activities
        for activity in activities
    )

    bypass_count = sum(
        flow_class
        == "Bypass Flow"
        for flow_class
        in transition_classes
    )

    reverse_deviation_count = sum(
        flow_class
        == "Reverse / Deviation Flow"
        for flow_class
        in transition_classes
    )

    exact_core_path = (
        tuple(
            activities
        )
        == profile.core_path
    )

    if exact_core_path:
        primary_class = (
            "Core Flow"
        )

    elif has_exit:
        primary_class = (
            "Exit Flow"
        )

    elif has_exception:
        primary_class = (
            "Exception Flow"
        )

    elif bypass_count > 0:
        primary_class = (
            "Bypass Flow"
        )

    elif has_optional_rule:
        primary_class = (
            "Optional / Rule Flow"
        )

    elif (
        reverse_deviation_count
        > 0
    ):
        primary_class = (
            "Reverse / Deviation Flow"
        )

    else:
        primary_class = (
            "Other Flow"
        )

    return {
        "primary_flow_class": (
            primary_class
        ),
        "exact_core_path": (
            exact_core_path
        ),
        "has_exception": (
            has_exception
        ),
        "has_exit": (
            has_exit
        ),
        "has_optional_rule": (
            has_optional_rule
        ),
        "bypass_count": (
            bypass_count
        ),
        "reverse_deviation_count": (
            reverse_deviation_count
        ),
    }


def classify_variants(
    variants: pd.DataFrame,
    profile: FlowProfile,
) -> pd.DataFrame:
    result = variants.copy()

    result["case_count"] = (
        pd.to_numeric(
            result[
                "case_count"
            ],
            errors="coerce",
        )
        .fillna(0)
    )

    analyses = (
        result[
            "path"
        ]
        .apply(
            lambda path: (
                analyze_variant_path(
                    path=path,
                    profile=profile,
                )
            )
        )
        .apply(
            pd.Series
        )
    )

    result = pd.concat(
        [
            result,
            analyses,
        ],
        axis=1,
    )

    return result


# =========================================================
# Activity intelligence
# =========================================================

def classify_activity_type(
    activity: str,
    profile: FlowProfile,
) -> str:
    activity = str(
        activity
    ).strip()

    if (
        activity
        in profile.terminal_activities
    ):
        return "Terminal State"

    if (
        activity
        in profile.waiting_activities
    ):
        return "Business Waiting"

    if (
        activity
        in profile.operational_activities
    ):
        return "Operational"

    return "Unclassified"


def build_activity_intelligence(
    activity_summary: pd.DataFrame,
    profile: FlowProfile,
) -> pd.DataFrame:
    result = (
        activity_summary.copy()
    )

    numeric_columns = [
        "cases",
        "events",
        "avg_duration_hours",
        "median_duration_hours",
        "case_coverage_pct",
    ]

    for column in numeric_columns:
        if column in result.columns:
            result[column] = (
                pd.to_numeric(
                    result[
                        column
                    ],
                    errors="coerce",
                )
            )

    result["activity_type"] = (
        result[
            "activity"
        ]
        .apply(
            lambda activity: (
                classify_activity_type(
                    activity=activity,
                    profile=profile,
                )
            )
        )
    )

    interpretation_map = {
        "Operational": (
            "Operational time signal. "
            "Interpret with process context."
        ),
        "Business Waiting": (
            "Business waiting or lifecycle time. "
            "Do not interpret automatically as effort."
        ),
        "Terminal State": (
            "Terminal process state. Duration should not "
            "be interpreted automatically as an operational bottleneck."
        ),
        "Unclassified": (
            "Activity without an analytical type classification."
        ),
    }

    result[
        "duration_interpretation"
    ] = (
        result[
            "activity_type"
        ]
        .map(
            interpretation_map
        )
    )

    return result


# =========================================================
# Summaries
# =========================================================

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

    if total_cases > 0:
        summary[
            "share_pct"
        ] = (
            summary[
                "cases"
            ]
            / total_cases
            * 100
        )

    else:
        summary[
            "share_pct"
        ] = 0.0

    summary = (
        summary
        .sort_values(
            by="cases",
            ascending=False,
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

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

    if total_occurrences > 0:
        summary[
            "transition_volume_share_pct"
        ] = (
            summary[
                "transition_case_occurrences"
            ]
            / total_occurrences
            * 100
        )

    else:
        summary[
            "transition_volume_share_pct"
        ] = 0.0

    summary = (
        summary
        .sort_values(
            by=(
                "transition_case_occurrences"
            ),
            ascending=False,
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    return summary


# =========================================================
# Insight generation
# =========================================================

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
            "The complete core path represents "
            f"{core_share:.2f}% of analyzed cases."
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
            "Paths containing exception activities appear in "
            f"{exception_share:.2f}% of analyzed cases."
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
            "Paths containing exit activities appear in "
            f"{exit_share:.2f}% of analyzed cases."
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
            bypass_transitions.iloc[
                0
            ]
        )

        insights.append(
            "The highest-volume observed bypass is "
            f"'{top_bypass['transition']}', with "
            f"{int(top_bypass['case_count']):,} observed cases."
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
            by=(
                "median_duration_hours"
            ),
            ascending=False,
        )
    )

    if not operational_activities.empty:
        top_operational = (
            operational_activities.iloc[
                0
            ]
        )

        insights.append(
            "Among activities classified as operational, "
            "the highest median duration is observed in "
            f"'{top_operational['activity']}' "
            f"({top_operational['median_duration_hours']:.2f} h)."
        )

    insights.append(
        "Classifications are analytical signals derived from "
        "the available process history and should be validated "
        "with operational context before being treated as "
        "errors, bottlenecks, or non-conformities."
    )

    return insights


# =========================================================
# Output
# =========================================================

def save_results(
    classified_variants: pd.DataFrame,
    classified_transitions: pd.DataFrame,
    activity_intelligence: pd.DataFrame,
    flow_summary: pd.DataFrame,
    transition_summary: pd.DataFrame,
    insights: list[str],
    profile: FlowProfile,
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

    profile_snapshot = {
        "profile_name": (
            profile.profile_name
        ),
        "core_path": list(
            profile.core_path
        ),
        "exception_activities": sorted(
            profile.exception_activities
        ),
        "exit_activities": sorted(
            profile.exit_activities
        ),
        "optional_rule_activities": sorted(
            profile.optional_rule_activities
        ),
        "operational_activities": sorted(
            profile.operational_activities
        ),
        "waiting_activities": sorted(
            profile.waiting_activities
        ),
        "terminal_activities": sorted(
            profile.terminal_activities
        ),
    }

    (
        output_dir
        / "profile_used.json"
    ).write_text(
        json.dumps(
            profile_snapshot,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# =========================================================
# Console
# =========================================================

def print_summary(
    profile: FlowProfile,
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

    print(
        f"Profile: {profile.profile_name}"
    )

    print()
    print(
        "Case distribution by primary classification:"
    )

    for _, row in (
        flow_summary.iterrows()
    ):
        print(
            f"  {row['primary_flow_class']:<28} "
            f"{int(row['cases']):>7,} cases | "
            f"{row['share_pct']:>6.2f}% | "
            f"{int(row['variants']):>4} variants"
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
            "Top observed bypasses:"
        )

        for _, row in (
            bypasses.iterrows()
        ):
            print(
                f"  {int(row['case_count']):>7,} | "
                f"{row['transition']}"
            )

    print()
    print(
        "Initial insights:"
    )

    for index, insight in enumerate(
        insights,
        start=1,
    ):
        print(
            f"  {index}. {insight}"
        )

    print()
    print(
        "Generated files:"
    )

    print(
        f"  {output_dir.resolve()}"
    )

    print("=" * 76)
    print()


# =========================================================
# Main
# =========================================================

def main() -> None:
    args = parse_arguments()

    discovery_dir = (
        args.discovery_dir.resolve()
    )

    profile_path = (
        args.profile.resolve()
    )

    output_dir = (
        args.output_dir.resolve()
    )

    profile = load_profile(
        profile_path
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
            transitions=transitions,
            profile=profile,
        )
    )

    classified_variants = (
        classify_variants(
            variants=variants,
            profile=profile,
        )
    )

    activity_intelligence = (
        build_activity_intelligence(
            activity_summary=(
                activity_summary
            ),
            profile=profile,
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
        profile=profile,
        output_dir=output_dir,
    )

    print_summary(
        profile=profile,
        flow_summary=flow_summary,
        classified_transitions=(
            classified_transitions
        ),
        insights=insights,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()