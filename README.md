# Operational Flow Intelligence

**From recorded process history to observable operational behavior.**

### 🚀 [Open the Live Control Tower](https://operational-flow-intelligence-zi7a28wxhkwiw8v5az69fr.streamlit.app/)

Explore the interactive dashboard using the public synthetic dataset included in this repository.
Operational Flow Intelligence is a Python-based process discovery and operational analytics project that transforms structured historical data into event logs, process variants, transition analysis, flow classifications, cycle-time signals and management insights.

The project was designed to answer a simple question:

> **What is actually happening in the process, beyond the process that was originally designed?**

---

## Overview

Operational data often contains valuable process history, but that history is usually stored in a format that is difficult to analyze as a flow.

This project converts that structured history into an analytical pipeline:

```text
Operational Report
        ↓
Data-to-Event-Log Engine
        ↓
Event Log
        ↓
Process Discovery
        ↓
Variants + Transitions + Activity Metrics
        ↓
Flow Intelligence
        ↓
Core Flow + Exceptions + Exits + Bypasses
        ↓
Control Tower
```

The result is a reusable framework for understanding how cases actually move through an operational process.

---

## What the project does

### 1. Data-to-Event-Log Engine

Transforms a structured Excel operational report into an event log.

The engine automatically:

- detects process phases
- identifies phase entry and exit timestamps
- captures recorded phase durations
- creates one event structure per case and activity
- orders events chronologically
- preserves case-level attributes
- exports a standardized event log

Example output structure:

```text
case_id
event_order
activity
event_timestamp
start_time
end_time
duration_days
duration_hours
current_phase
is_current_phase
card_type
industry
```

---

### 2. Process Discovery

Uses the generated event log to reconstruct observed process behavior.

The discovery engine identifies:

- process variants
- most frequent paths
- transition frequencies
- start and end activities
- case coverage by activity
- average and median duration signals

Example:

```text
Intake
  ↓
Data Preparation
  ↓
System Upload
  ↓
Scheduled / Waiting Start
  ↓
Quality Review
  ↓
Validated / Active
  ↓
Completed
```

The engine also identifies alternative paths such as exceptions, early exits and skipped activities.

---

### 3. Flow Intelligence

The Flow Intelligence layer interprets discovered behavior through a configurable process profile.

Instead of hardcoding one specific process into the analytical engine, process semantics are defined in a JSON configuration.

Example:

```json
{
  "profile_name": "Synthetic Demo Process",
  "core_path": [
    "Intake",
    "Data Preparation",
    "System Upload",
    "Scheduled / Waiting Start",
    "Quality Review",
    "Validated / Active",
    "Completed"
  ]
}
```

This allows the same engine to be reused across different process structures.

Observed behavior can be classified as:

- **Core Flow** — the configured main process path
- **Exception Flow** — paths containing exception activities
- **Exit Flow** — paths containing cancellation or rejection states
- **Bypass Flow** — transitions that apparently skip activities in the configured core path
- **Optional / Rule Flow** — paths containing optional or rule-based activities
- **Reverse / Deviation Flow** — movements that go backwards in the expected sequence
- **Other Flow** — behavior not covered by the configured classifications

These classifications are analytical signals, not automatic conclusions of error or non-compliance.

---

## Control Tower

The project includes a Streamlit dashboard for executive and operational exploration.

The Control Tower currently provides:

### Overview

- analyzed cases
- discovered variants
- Core Flow participation
- cases containing exceptions
- distribution by flow classification
- Top 10 process variants

### Process Flow

- dominant transitions
- transition classification
- outgoing transition share
- highest-volume bypasses

### Cycle Time

- median duration of operational activities
- process coverage by phase
- activity-type classification
- distinction between operational time, business waiting and terminal states

### Management Insights

- automatically generated analytical observations
- Core Flow participation
- exception prevalence
- exit prevalence
- highest-volume bypass
- operational duration signals

---

## Public demo

The repository includes a **100% synthetic demonstration dataset**.

No real operational records, customer information, personal information or confidential business data are included in the public demo.

The synthetic dataset contains:

- **2,500 artificial cases**
- **12 generic process phases**
- **11 synthetic process scenarios**
- artificial timestamps and durations
- Core Flow cases
- exception paths
- early and late exits
- bypasses
- optional-rule paths
- open cases

The demo dataset is available at:

```text
examples/synthetic_operational_report.xlsx
```

The public process profile is available at:

```text
examples/demo_flow_profile.json
```

Pre-generated intelligence outputs used by the public dashboard are available at:

```text
examples/demo_intelligence/
```

---

## Synthetic demo results

Using the included synthetic dataset, the pipeline identifies:

```text
Cases analyzed       : 2,500
Variants identified  : 11
Transitions          : 19
```

Primary flow distribution:

| Classification | Cases | Share |
|---|---:|---:|
| Core Flow | 869 | 34.76% |
| Exception Flow | 498 | 19.92% |
| Exit Flow | 405 | 16.20% |
| Bypass Flow | 319 | 12.76% |
| Optional / Rule Flow | 264 | 10.56% |
| Other Flow | 145 | 5.80% |

The most frequent synthetic path is:

```text
Intake
→ Data Preparation
→ System Upload
→ Scheduled / Waiting Start
→ Quality Review
→ Validated / Active
→ Completed
```

---

## Project structure

```text
operational-flow-intelligence/
│
├── dashboard/
│   └── app.py
│
├── data/
│   ├── input/
│   │   └── .gitkeep
│   └── output/
│       └── .gitkeep
│
├── examples/
│   ├── README.md
│   ├── demo_flow_profile.json
│   ├── synthetic_operational_report.xlsx
│   └── demo_intelligence/
│       ├── activity_intelligence.csv
│       ├── classified_transitions.csv
│       ├── classified_variants.csv
│       ├── flow_summary.csv
│       ├── insights.txt
│       ├── profile_used.json
│       └── transition_summary.csv
│
├── src/
│   ├── event_log.py
│   ├── process_discovery.py
│   ├── flow_intelligence.py
│   └── generate_synthetic_data.py
│
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Installation

Clone the repository and create a virtual environment.

### Windows

```powershell
py -m venv .venv
```

Install the dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Run the public demo

### 1. Generate the synthetic dataset

```powershell
.\.venv\Scripts\python.exe .\src\generate_synthetic_data.py
```

### 2. Convert the report into an event log

```powershell
.\.venv\Scripts\python.exe .\src\event_log.py ".\examples\synthetic_operational_report.xlsx" -o ".\data\output\synthetic\event_log.csv"
```

### 3. Run Process Discovery

```powershell
.\.venv\Scripts\python.exe .\src\process_discovery.py ".\data\output\synthetic\event_log.csv" -o ".\data\output\synthetic\discovery"
```

### 4. Run Flow Intelligence

```powershell
.\.venv\Scripts\python.exe .\src\flow_intelligence.py ".\data\output\synthetic\discovery" --profile ".\examples\demo_flow_profile.json" -o ".\data\output\synthetic\intelligence"
```

### 5. Open the Control Tower

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\dashboard\app.py
```

The application will normally be available at:

```text
http://localhost:8501
```

---

## Analytical principles

The project intentionally separates different analytical concepts.

### Workload is not the same as bottleneck

A phase with high effort is not automatically the main process constraint.

### Waiting time is not automatically operational effort

Activities classified as business waiting should not be interpreted as analyst workload without context.

### Terminal-state duration is not a bottleneck

Completed, cancelled or rejected states can remain recorded for long periods. Their duration should not automatically be interpreted as process inefficiency.

### Frequency is not the same as priority

A frequent process variation can be expected behavior, while a less frequent variation can still have greater operational impact.

### A bypass is a signal, not proof of an error

A transition that skips an activity in the configured core path may represent:

- a legitimate business rule
- a different case type
- an exception
- incomplete historical data
- or a real deviation

Operational validation is always required.

---

## Important limitation

The current event-log reconstruction uses available historical phase fields such as:

- first entry into a phase
- last exit from a phase
- total recorded duration in the phase

This structure allows useful process discovery, but it does **not always reconstruct repeated visits to the same phase perfectly**.

For that reason, this project should be interpreted as:

> **process discovery and flow intelligence based on available operational history**

rather than a complete formal process-mining implementation.

---

## Data protection

Operational datasets are intentionally excluded from version control.

The repository ignores:

```text
data/input/*
data/output/*
*.xlsx
*.csv
*.parquet
```

Only explicitly allowed synthetic demonstration files under `examples/` are published.

This keeps the analytical logic reusable while separating source code from sensitive operational data.

---

## Technology

- Python
- Pandas
- OpenPyXL
- Streamlit
- Plotly
- Git

---

## Project evolution

Operational Flow Intelligence currently covers:

```text
Operational Data
      ↓
Event Log
      ↓
Process Discovery
      ↓
Flow Intelligence
      ↓
Control Tower
```

Potential future evolution includes:

- configurable column mapping
- richer event-log standards
- case-level filtering
- segmentation by process attributes
- temporal trend analysis
- deviation scoring
- bottleneck prioritization
- designed-process vs. executed-process comparison
- automated analytical recommendations

---

## Why this project exists

A process diagram shows how work is expected to happen.

Operational history shows how work actually happened.

**Operational Flow Intelligence connects the two perspectives by turning historical process data into observable flow behavior and decision-oriented signals.**