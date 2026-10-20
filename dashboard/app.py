from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# =========================================================
# Configuration
# =========================================================

st.set_page_config(
    page_title="Operational Flow Intelligence",
    page_icon="ðŸ“Š",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INTELLIGENCE_DIR = (
    PROJECT_ROOT
    / "examples"
    / "demo_intelligence"
)


# =========================================================
# Data loading
# =========================================================

@st.cache_data
def load_csv(filename: str) -> pd.DataFrame:
    path = INTELLIGENCE_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {path}"
        )

    return pd.read_csv(
        path,
        encoding="utf-8-sig",
    )


@st.cache_data
def load_insights() -> list[str]:
    path = INTELLIGENCE_DIR / "insights.txt"

    if not path.exists():
        return []

    lines = path.read_text(
        encoding="utf-8",
    ).splitlines()

    insights = []

    for line in lines:
        clean_line = line.strip()

        if not clean_line:
            continue

        if ". " in clean_line:
            clean_line = clean_line.split(
                ". ",
                1,
            )[1]

        insights.append(clean_line)

    return insights


def load_data() -> dict[str, object]:
    return {
        "flow_summary": load_csv(
            "flow_summary.csv"
        ),
        "variants": load_csv(
            "classified_variants.csv"
        ),
        "transitions": load_csv(
            "classified_transitions.csv"
        ),
        "activities": load_csv(
            "activity_intelligence.csv"
        ),
        "insights": load_insights(),
    }


# =========================================================
# Helpers
# =========================================================

def get_flow_share(
    flow_summary: pd.DataFrame,
    flow_class: str,
) -> float:
    filtered = flow_summary.loc[
        flow_summary[
            "primary_flow_class"
        ]
        == flow_class,
        "share_pct",
    ]

    if filtered.empty:
        return 0.0

    return float(filtered.iloc[0])


def format_integer(value: float | int) -> str:
    return f"{int(value):,}".replace(
        ",",
        ".",
    )


def format_percent(value: float) -> str:
    return (
        f"{value:.2f}%"
        .replace(
            ".",
            ",",
        )
    )


def format_hours(value: float) -> str:
    if pd.isna(value):
        return "-"

    if value < 24:
        return (
            f"{value:.2f} h"
            .replace(
                ".",
                ",",
            )
        )

    days = value / 24

    return (
        f"{days:.1f} dias"
        .replace(
            ".",
            ",",
        )
    )


# =========================================================
# Load data
# =========================================================

try:
    data = load_data()

except FileNotFoundError as error:
    st.error(
        "Os arquivos de inteligência ainda não estão "
        "disponíveis."
    )

    st.code(str(error))

    st.info(
        "Execute primeiro os motores de Process Discovery "
        "e Flow Intelligence."
    )

    st.stop()


flow_summary = data["flow_summary"]
variants = data["variants"]
transitions = data["transitions"]
activities = data["activities"]
insights = data["insights"]


# =========================================================
# Data preparation
# =========================================================

flow_summary["cases"] = pd.to_numeric(
    flow_summary["cases"],
    errors="coerce",
).fillna(0)

flow_summary["share_pct"] = pd.to_numeric(
    flow_summary["share_pct"],
    errors="coerce",
).fillna(0)

variants["case_count"] = pd.to_numeric(
    variants["case_count"],
    errors="coerce",
).fillna(0)

variants["share_pct"] = pd.to_numeric(
    variants["share_pct"],
    errors="coerce",
).fillna(0)

transitions["case_count"] = pd.to_numeric(
    transitions["case_count"],
    errors="coerce",
).fillna(0)

transitions["outgoing_share_pct"] = (
    pd.to_numeric(
        transitions[
            "outgoing_share_pct"
        ],
        errors="coerce",
    )
)

activities["median_duration_hours"] = (
    pd.to_numeric(
        activities[
            "median_duration_hours"
        ],
        errors="coerce",
    )
)

activities["case_coverage_pct"] = (
    pd.to_numeric(
        activities[
            "case_coverage_pct"
        ],
        errors="coerce",
    )
)


total_cases = int(
    flow_summary["cases"].sum()
)

total_variants = int(
    len(variants)
)

core_share = get_flow_share(
    flow_summary,
    "Core Flow",
)

exit_share = get_flow_share(
    flow_summary,
    "Exit Flow",
)

exception_cases = int(
    variants.loc[
        variants["has_exception"]
        .astype(str)
        .str.lower()
        .eq("true"),
        "case_count",
    ].sum()
)

exception_share = (
    exception_cases
    / total_cases
    * 100
    if total_cases
    else 0
)


# =========================================================
# Header
# =========================================================

st.title(
    "Operational Flow Intelligence"
)

st.subheader(
    "Control Tower"
)

st.caption(
    "Do processo registrado ao comportamento realmente "
    "observado no fluxo operacional."
)

st.divider()


# =========================================================
# Executive metrics
# =========================================================

metric_1, metric_2, metric_3, metric_4 = (
    st.columns(4)
)

metric_1.metric(
    "Casos analisados",
    format_integer(total_cases),
)

metric_2.metric(
    "Variantes encontradas",
    format_integer(total_variants),
)

metric_3.metric(
    "Core Flow",
    format_percent(core_share),
)

metric_4.metric(
    "Casos com exceção",
    format_percent(exception_share),
)


# =========================================================
# Tabs
# =========================================================

overview_tab, flow_tab, time_tab, insight_tab = (
    st.tabs(
        [
            "Overview",
            "Process Flow",
            "Cycle Time",
            "Management Insights",
        ]
    )
)


# =========================================================
# Overview
# =========================================================

with overview_tab:

    st.subheader(
        "Distribuição do comportamento do processo"
    )

    flow_chart_data = (
        flow_summary
        .sort_values(
            by="cases",
            ascending=True,
        )
        .copy()
    )

    flow_chart = px.bar(
        flow_chart_data,
        x="cases",
        y="primary_flow_class",
        orientation="h",
        text="share_pct",
        labels={
            "cases": "Casos",
            "primary_flow_class": (
                "Classificação"
            ),
            "share_pct": (
                "Participação"
            ),
        },
        hover_data={
            "cases": ":,.0f",
            "share_pct": ":.2f",
            "variants": True,
        },
    )

    flow_chart.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
    )

    flow_chart.update_layout(
        xaxis_title="Casos",
        yaxis_title="",
        showlegend=False,
        margin=dict(
            l=20,
            r=40,
            t=20,
            b=20,
        ),
    )

    st.plotly_chart(
        flow_chart,
        width="stretch",
    )

    st.divider()

    st.subheader(
        "Top 10 variantes"
    )

    top_variants = (
        variants
        .sort_values(
            by="case_count",
            ascending=False,
        )
        .head(10)
        .copy()
    )

    top_variants["variant_label"] = (
        "V"
        + top_variants[
            "variant_id"
        ]
        .astype(int)
        .astype(str)
        .str.zfill(3)
    )

    variant_chart = px.bar(
        top_variants,
        x="variant_label",
        y="case_count",
        text="share_pct",
        custom_data=[
            "path",
        ],
        labels={
            "variant_label": (
                "Variante"
            ),
            "case_count": (
                "Casos"
            ),
        },
    )

    variant_chart.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Casos: %{y:,.0f}<br>"
            "Caminho: %{customdata[0]}"
            "<extra></extra>"
        ),
    )

    variant_chart.update_layout(
        xaxis_title="Variante",
        yaxis_title="Casos",
        showlegend=False,
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20,
        ),
    )

    st.plotly_chart(
        variant_chart,
        width="stretch",
    )


# =========================================================
# Process Flow
# =========================================================

with flow_tab:

    st.subheader(
        "Transições dominantes"
    )

    dominant_transitions = (
        transitions
        .sort_values(
            by="case_count",
            ascending=False,
        )
        .head(15)
        .copy()
    )

    dominant_transitions[
        "outgoing_share_pct"
    ] = dominant_transitions[
        "outgoing_share_pct"
    ].round(2)

    st.dataframe(
        dominant_transitions[
            [
                "source_activity",
                "target_activity",
                "flow_class",
                "case_count",
                "outgoing_share_pct",
            ]
        ].rename(
            columns={
                "source_activity": (
                    "Origem"
                ),
                "target_activity": (
                    "Destino"
                ),
                "flow_class": (
                    "Classificação"
                ),
                "case_count": (
                    "Casos"
                ),
                "outgoing_share_pct": (
                    "% das saídas observadas"
                ),
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.divider()

    st.subheader(
        "Principais Bypass Flows"
    )

    bypasses = (
        transitions.loc[
            transitions[
                "flow_class"
            ]
            == "Bypass Flow"
        ]
        .sort_values(
            by="case_count",
            ascending=False,
        )
        .head(10)
        .copy()
    )

    if bypasses.empty:
        st.info(
            "Nenhum Bypass Flow foi "
            "identificado."
        )

    else:
        bypass_chart = px.bar(
            bypasses.sort_values(
                by="case_count",
                ascending=True,
            ),
            x="case_count",
            y="transition",
            orientation="h",
            labels={
                "case_count": "Casos",
                "transition": "",
            },
            hover_data={
                "outgoing_share_pct": (
                    ":.2f"
                ),
            },
        )

        bypass_chart.update_layout(
            xaxis_title="Casos",
            yaxis_title="",
            showlegend=False,
            margin=dict(
                l=20,
                r=20,
                t=20,
                b=20,
            ),
        )

        st.plotly_chart(
            bypass_chart,
            width="stretch",
        )

        st.caption(
            "Bypass Flow representa uma etapa "
            "aparentemente pulada na sequência "
            "observada. O sinal deve ser validado "
            "com o contexto operacional."
        )


# =========================================================
# Cycle Time
# =========================================================

with time_tab:

    st.subheader(
        "Tempo mediano das fases operacionais"
    )

    operational_activities = (
        activities.loc[
            activities[
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
            ascending=True,
        )
        .copy()
    )

    time_chart = px.bar(
        operational_activities,
        x="median_duration_hours",
        y="activity",
        orientation="h",
        text="median_duration_hours",
        labels={
            "median_duration_hours": (
                "Mediana de duração (horas)"
            ),
            "activity": "",
        },
    )

    time_chart.update_traces(
        texttemplate="%{text:.1f} h",
        textposition="outside",
    )

    time_chart.update_layout(
        xaxis_title=(
            "Mediana de duração (horas)"
        ),
        yaxis_title="",
        showlegend=False,
        margin=dict(
            l=20,
            r=40,
            t=20,
            b=20,
        ),
    )

    st.plotly_chart(
        time_chart,
        width="stretch",
    )

    st.divider()

    st.subheader(
        "Leitura das fases"
    )

    activity_table = (
        activities[
            [
                "activity",
                "activity_type",
                "case_coverage_pct",
                "median_duration_hours",
                "duration_interpretation",
            ]
        ]
        .copy()
    )

    activity_table[
        "case_coverage_pct"
    ] = (
        activity_table[
            "case_coverage_pct"
        ]
        .round(2)
    )

    activity_table[
        "median_duration"
    ] = (
        activity_table[
            "median_duration_hours"
        ]
        .apply(format_hours)
    )

    st.dataframe(
        activity_table[
            [
                "activity",
                "activity_type",
                "case_coverage_pct",
                "median_duration",
                "duration_interpretation",
            ]
        ].rename(
            columns={
                "activity": "Fase",
                "activity_type": "Tipo",
                "case_coverage_pct": (
                    "Cobertura dos casos (%)"
                ),
                "median_duration": (
                    "Duração mediana"
                ),
                "duration_interpretation": (
                    "Interpretação"
                ),
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Estados terminais e tempos de ciclo de "
        "negócio não são tratados automaticamente "
        "como gargalos operacionais."
    )


# =========================================================
# Management Insights
# =========================================================

with insight_tab:

    st.subheader(
        "Insights gerados pelo motor"
    )

    if not insights:
        st.info(
            "Nenhum insight disponível."
        )

    else:
        for index, insight in enumerate(
            insights,
            start=1,
        ):
            st.markdown(
                f"**{index}.** {insight}"
            )

    st.divider()

    st.subheader(
        "Visão executiva"
    )

    executive_col_1, executive_col_2 = (
        st.columns(2)
    )

    with executive_col_1:

        st.metric(
            "Exit Flow",
            format_percent(
                exit_share
            ),
        )

        st.caption(
            "Casos cuja classificação principal "
            "contém cancelamento ou rejeição."
        )

    with executive_col_2:

        bypass_primary_share = (
            get_flow_share(
                flow_summary,
                "Bypass Flow",
            )
        )

        st.metric(
            "Bypass Flow",
            format_percent(
                bypass_primary_share
            ),
        )

        st.caption(
            "Casos cuja classificação principal "
            "contém uma etapa aparentemente pulada."
        )

    st.warning(
        "As classificações representam sinais "
        "analíticos derivados do histórico disponível. "
        "Elas não devem ser interpretadas isoladamente "
        "como erro, não conformidade ou gargalo sem "
        "validação do processo."
    )


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "Operational Flow Intelligence · "
    "Process Discovery + Flow Intelligence"
)
