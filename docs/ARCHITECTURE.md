# VITRIFY Tool - Technical Architecture Reference

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [High-Level Architecture](#high-level-architecture)
3. [Package Structure](#package-structure)
4. [Core Modules](#core-modules)
   - [models.py](#modelspy)
   - [constants.py](#constantspy)
   - [scenarios.py](#scenariospy)
   - [main.py](#mainpy)
5. [Utility Modules](#utility-modules)
   - [calculations.py](#calculationspy)
   - [input_helpers.py](#input_helperspy)
6. [Supporting Modules](#supporting-modules)
   - [visualization.py](#visualizationpy)
   - [reporting.py](#reportingpy)
   - [audit.py](#auditpy)
   - [config.py](#configpy)
7. [Data Flow](#data-flow)
8. [Configuration System](#configuration-system)
9. [Scenario Logic Deep Dive](#scenario-logic-deep-dive)
10. [Extension Points](#extension-points)
11. [Testing Framework](#testing-framework)
12. [Glossary](#glossary)

---

## Executive Summary

VITRIFY is a Python-based decision-support tool for assessing the environmental impact (Carbon Footprint in kg CO₂e) of various end-of-life recovery pathways for Insulating Glass Units (IGUs). The tool models:

- **6 Base Scenarios**: System Reuse, Component Reuse, Component Repurpose, Closed-loop Recycling, Open-loop Recycling, and Landfill.
- **11 Path Variations**: Accounting for sub-decisions like "with Repair" vs. "without Repair", "Intact" vs. "Broken" transport, and repurposing intensity (Light/Medium/Heavy).

The tool operates in two primary modes:
1. **Single Run (Interactive)**: Step-by-step CLI prompts for ad-hoc analysis.
2. **Batch Analysis (Automated)**: Iterates over a product database, running all 11 path variations for every product, and outputs a comprehensive CSV report.

The architecture is designed for:
- **Modularity**: Core logic is isolated from I/O.
- **Configurability**: All physical constants and emission factors are externalized to an Excel file.
- **Traceability**: Audit logging records every emission calculation.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   USER                                      │
│                         (CLI / Excel Database)                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          ENTRY POINT (main.py)                               │
│  Orchestrates Single Run and Batch Analysis. Handles user prompts via       │
│  input_helpers. Delegates scenario execution to scenarios.py.               │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
               ▼                    ▼                    ▼
┌──────────────────────┐ ┌───────────────────────┐ ┌─────────────────────────┐
│    models.py         │ │    scenarios.py       │ │  utils/calculations.py  │
│  Data Structures     │ │  Recovery Path Logic  │ │  Math & Transport Calc  │
│  (Location, IGUGroup │ │  (System Reuse, etc.) │ │  (haversine, mass, etc.)│
│  ScenarioResult...)  │ │                       │ │                         │
└──────────────────────┘ └───────────────────────┘ └─────────────────────────┘
               │                    │                    │
               ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         constants.py (+ config.py)                           │
│  Emission Factors, Yield Rates, Material Properties loaded from Excel       │
└──────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            OUTPUT LAYER                                      │
│  visualization.py (Plots) | reporting.py (Markdown) | CSV Reports           │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Package Structure

```
d:\VITRIFY\
├── src\
│   ├── Recovery_IGU_CO2.py          # Entry point shim (calls main.main())
│   └── igu_recovery\                # Core Python Package
│       ├── __init__.py
│       ├── main.py                  # Application orchestrator
│       ├── models.py                # Data classes (12 dataclasses)
│       ├── constants.py             # ~70 configuration constants
│       ├── scenarios.py             # 6 scenario functions (+ variations)
│       ├── visualization.py         # Matplotlib plotting engine
│       ├── reporting.py             # Markdown report generator
│       ├── audit.py                 # Emission calculation audit logger
│       ├── logging_conf.py          # Centralized logging setup
│       ├── config.py                # Excel config loader
│       └── utils\
│           ├── __init__.py
│           ├── calculations.py      # 14 core calculation functions
│           └── input_helpers.py     # 24 CLI prompting & parsing functions
├── data\
│   ├── parameters_config\
│   │   └── project_parameters.xlsx  # Externalized constants
│   └── saint_gobain\                # Product database
│       └── saint gobain product database.xlsx
├── docs\
│   ├── methodology_and_logic.md     # Scenario math reference
│   └── ARCHITECTURE.md              # (This document)
├── reports\                         # Generated outputs
│   ├── plots\                       # Visualizations
│   ├── markdown_breakdowns\         # Detailed per-run reports
│   └── audit_logs\                  # Calculation trace logs
└── tests\
    ├── conftest.py
    ├── test_batch_robustness.py     # Unit tests for core logic
    ├── test_integration_batch.py    # End-to-end integration test
    ├── test_units.py
    └── test_parameter_loading.py
```

---

## Core Modules

### models.py

This module defines **12 dataclasses** that serve as the data backbone for the entire application. All scenario functions consume and produce these types.

#### Key Classes

| Class | Purpose | Key Fields |
|-------|---------|------------|
| `Location` | Geographical coordinate | `lat`, `lon` |
| `RouteConfig` | Transport route definition | `mode`, `truck_km`, `ferry_km` |
| `TransportModeConfig` | Full transport context | `origin`, `processor`, `reuse`, `landfill`, `emissionfactor_truck` |
| `ProcessSettings` | Global process assumptions | `route_configs`, `igus_per_stillage`, `breakage_rate_global`, `e_site_kgco2_per_m2` |
| `IGUCondition` | Physical state of an IGU | `visible_edge_seal_condition`, `visible_fogging`, `cracks_chips`, `reuse_allowed` |
| `SealGeometry` | Seal dimensions (constant per batch) | `primary_thickness_mm`, `primary_width_mm`, `secondary_width_mm` |
| `IGUGroup` | A homogeneous set of IGUs | `quantity`, `unit_width_mm`, `glazing_type`, `glass_type_outer`, `spacer_material`, `condition` |
| `FlowState` | Tracks mass/area throughput | `igus`, `area_m2`, `mass_kg` |
| `ScenarioResult` | Output of a scenario run | `scenario_name`, `total_emissions_kgco2`, `by_stage`, `yield_percent` |
| `BatchInput` | Wrapper for a calculation batch | `transport`, `processes`, `igu_groups` |
| `EmissionBreakdown` | Full-chain emission detail | `dismantling_from_building_kgco2`, `transport_A_kgco2`, ... |

#### Design Notes

- All classes are **frozen dataclasses** (immutable by convention) for thread-safety.
- `ProcessSettings.route_configs` is a `Dict[str, RouteConfig]` registry, allowing dynamic route definition (e.g., `"origin_to_processor"`, `"processor_to_landfill"`).
- `IGUCondition` determines reuse eligibility within `aggregate_igu_groups`.

---

### constants.py

This module centralizes all **configurable parameters**. Instead of hardcoding values, it loads them at import time from `project_parameters.xlsx` via `config.py`.

#### Parameter Categories

| Category | Examples |
|----------|----------|
| **Dismantling/Site** | `E_SITE_KGCO2_PER_M2` |
| **Processing** | `REMANUFACTURING_KGCO2_PER_M2`, `DISASSEMBLY_KGCO2_PER_M2`, `BREAKING_KGCO2_PER_M2`, `REPAIR_KGCO2_PER_M2` |
| **Repurposing** | `REPURPOSE_LIGHT_KGCO2_PER_M2`, `REPURPOSE_MEDIUM_KGCO2_PER_M2`, `REPURPOSE_HEAVY_KGCO2_PER_M2` |
| **Transport** | `EMISSIONFACTOR_TRUCK`, `EMISSIONFACTOR_FERRY`, `BACKHAUL_FACTOR` |
| **Yield Losses** | `YIELD_REPAIR`, `YIELD_DISASSEMBLY_REUSE`, `YIELD_DISASSEMBLY_REPURPOSE` |
| **Recycling Fractions** | `SHARE_CULLET_FLOAT`, `SHARE_CULLET_OPEN_LOOP_GW`, `SHARE_CULLET_OPEN_LOOP_CONT` |
| **Material Properties** | `GLASS_DENSITY_KG_M3`, `SEALANT_DENSITY_KG_M3`, `SPACER_MASS_PER_M_KG` |
| **Material Emission Factors** | `EF_MAT_SPACER_ALU`, `EF_MAT_SEALANT`, `EF_PROCESS_COATING` |

#### Type Literals

The module also defines **type literals** for strict type-checking:
- `GlazingType`: `"double" | "triple" | "single"`
- `GlassType`: `"annealed" | "tempered" | "laminated"`
- `SealantType`: `"polysulfide" | "polyurethane" | "silicone" | "combination"`
- `SpacerMaterial`: `"aluminium" | "steel" | "warm_edge_composite"`
- `EdgeSealCondition`: `"acceptable" | "unacceptable" | "not assessed"`
- `TransportMode`: `"HGV lorry" | "HGV lorry+ferry"`
- `RepurposePreset`: `"light" | "medium" | "heavy"`

---

### scenarios.py

The heart of the tool. Contains **6 scenario functions** (with configurable variations via kwargs):

| Function | Scenario | Kwargs |
|----------|----------|--------|
| `run_scenario_system_reuse` | System Reuse | `repair_needed: bool` |
| `run_scenario_component_reuse` | Component Reuse | (None) |
| `run_scenario_component_repurpose` | Component Repurpose | `repurpose_intensity: str` ("light"/"medium"/"heavy") |
| `run_scenario_closed_loop_recycling` | Closed-loop Recycling | `send_intact: bool` |
| `run_scenario_open_loop_recycling` | Open-loop Recycling | `send_intact: bool` |
| `run_scenario_landfill` | Straight to Landfill | (None) |

#### Common Flow Pattern

Each scenario function follows this structure:

```python
def run_scenario_X(processes, transport, group, flow_start, ..., interactive=True, **kwargs):
    # 1. Apply Removal Yield Loss (On-site breakage)
    flow_step1 = apply_yield_loss(flow_start, yield_removal)
    
    # 2. Calculate Dismantling Emissions
    e_dismantling = area * E_SITE_KGCO2_PER_M2
    
    # 3. Calculate Transport A (Origin -> Processor)
    e_transport_a = get_route_emissions(mass, "origin_to_processor", ...)
    
    # 4. Apply Processing Step(s) - Scenario Specific
    #    e.g., Repair, Disassembly, Breaking, etc.
    
    # 5. Calculate Transport B (Processor -> Destination)
    e_transport_b = get_route_emissions(mass, "processor_to_reuse", ...)
    
    # 6. Calculate Waste Transport (Yield Losses -> Landfill)
    e_waste = get_route_emissions(mass_loss, "origin_to_landfill", ...)
    
    # 7. Return ScenarioResult
    return ScenarioResult(
        scenario_name="...",
        total_emissions_kgco2=sum(...),
        by_stage={...},
        yield_percent=...
    )
```

#### Helper Function: `get_route_emissions`

This centralized function calculates transport emissions for any registered route:

```python
def get_route_emissions(mass_kg, route_key, processes, transport):
    config = processes.route_configs[route_key]
    mass_t = mass_kg / 1000.0
    truck_e = mass_t * config.truck_km * transport.emissionfactor_truck * transport.backhaul_factor
    ferry_e = mass_t * config.ferry_km * transport.emissionfactor_ferry * transport.backhaul_factor
    return truck_e + ferry_e
```

All calls are logged to the **Audit Logger** for traceability.

---

### main.py

The application orchestrator. Exposes:

- `main()`: Entry point. Prompts for mode selection.
- `run_automated_analysis(processes)`: Batch mode setup (global inputs).
- `execute_analysis_batch(df, processes, transport, ...)`: The core batch loop.

#### Batch Loop Structure

```python
scenarios = [
    ("System Reuse (Direct)", run_scenario_system_reuse, {"repair_needed": False}),
    ("System Reuse (Repair)", run_scenario_system_reuse, {"repair_needed": True}),
    ("Component Reuse", run_scenario_component_reuse, {}),
    ("Repurpose (Light)", run_scenario_component_repurpose, {"repurpose_intensity": "light"}),
    # ... (11 total)
]

for idx, row in df.iterrows():
    group = parse_db_row_to_group(row, ...)
    for sc_name, sc_func, kwargs in scenarios:
        res = sc_func(..., **kwargs)
        results.append(res)

report_df = format_and_clean_report_dataframe(pd.DataFrame(results))
report_df.to_csv(...)
```

---

## Utility Modules

### calculations.py

Contains **14 functions** for core math:

| Function | Purpose |
|----------|---------|
| `haversine_km(a, b)` | Great-circle distance between two Locations |
| `get_osrm_distance(origin, dest)` | Driving distance via OSRM API |
| `compute_route_distances(transport)` | Compute A-leg and B-leg baseline distances |
| `default_mass_per_m2(glazing_type)` | Default IGU surface mass by type |
| `aggregate_igu_groups(groups, processes)` | Aggregate counts/areas/yield for a batch |
| `packaging_factor_per_igu(processes)` | Stillage embodied carbon per IGU |
| `secondary_seal_thickness_mm_for_group(g)` | Derive secondary seal thickness |
| `compute_sealant_volumes(group, seal)` | Sealant volume calculations |
| `apply_yield_loss(state, loss_fraction)` | Apply yield reduction to FlowState |
| `calculate_material_masses(group, seal)` | Calculate Glass, Sealant, Spacer masses |
| `compute_igu_mass_totals(groups, stats, seal)` | Aggregate mass calculations |

#### Key Algorithm: `aggregate_igu_groups`

This function determines how many IGUs are "acceptable" for reuse based on their `IGUCondition`:

```python
if g.condition.reuse_allowed and not g.condition.cracks_chips:
    if g.condition.visible_edge_seal_condition != "unacceptable" and not g.condition.visible_fogging:
        acceptable_igus += g.quantity
```

It then applies global breakage and humidity failure rates before calculating `remanufactured_igus`.

---

### input_helpers.py

Contains **24 functions** for CLI interaction and data parsing:

| Function | Purpose |
|----------|---------|
| `prompt_location(label)` | Geocode or parse lat/lon |
| `prompt_choice(label, options, default)` | Choice selection |
| `prompt_yes_no(label, default)` | Boolean prompt |
| `prompt_seal_geometry()` | Seal input dialog |
| `define_igu_system_from_manual()` | Full manual IGU definition |
| `define_igu_system_from_database()` | Load from Excel database |
| `parse_db_row_to_group(row, qty, w, h, seal)` | Parse Excel row to IGUGroup |
| `configure_route(name, origin, dest, interactive)` | Interactive route setup |
| `format_and_clean_report_dataframe(df)` | Post-process batch report |
| `print_scenario_overview(result)` | Pretty-print a ScenarioResult |

#### Key Function: `parse_db_row_to_group`

This function translates an Excel row into a fully populated `IGUGroup`. It handles:
- Parsing the `Unit` column (e.g., `"6|16|6"`) to extract glass thicknesses.
- Detecting laminated glass via:
  - Keywords in `win_name` (e.g., `"44.2"`, `"lami"`)
  - The `Inner_Lam` column
- Defaulting missing values (e.g., `coating_type`, `spacer_material`).

---

## Supporting Modules

### visualization.py

Provides the `Visualizer` class for generating plots:

- `plot_single_scenario_breakdown(result, product_name)`: Bar chart of emission stages.
- `plot_scenario_comparison(results, product_name)`: Dual-axis (Emissions vs Yield).
- `plot_batch_summary(df)`: Boxplot and intensity charts for batch runs.

Plots are saved to `reports/plots/<session_timestamp>/`.

### reporting.py

Exports `save_scenario_md(result)`: Generates a detailed Markdown breakdown of a single scenario run, saved to `reports/markdown_breakdowns/`.

### audit.py

Provides `audit_logger.log_calculation(...)`: Records every emission calculation with:
- Context (e.g., "Transport Origin -> Processor")
- Formula (e.g., `Mass * Dist * EF * Backhaul`)
- Variables (Exact input values)
- Result

Logs are saved to `reports/audit_logs/`.

### config.py

Exports `load_excel_config()`: Reads `project_parameters.xlsx` and returns a dictionary of all parameters. Called once at import time by `constants.py`.

---

## Data Flow

### Single Run Flow

```
User Input (CLI)
       │
       ▼
[prompt_location, prompt_choice, ...] --> [Location, IGUGroup, SealGeometry]
       │
       ▼
[aggregate_igu_groups, compute_igu_mass_totals] --> [FlowState, Stats, Masses]
       │
       ▼
[run_scenario_X(...)] --> [ScenarioResult]
       │
       ▼
[print_scenario_overview, save_scenario_md] --> [Console, Markdown File]
       │
       ▼
[Visualizer.plot_...] --> [PNG Files]
```

### Batch Flow

```
Excel Database (df)
       │
       ▼
[run_automated_analysis] --> Prompts for Global Inputs
       │
       ▼
For each row in df:
    [parse_db_row_to_group] --> IGUGroup
             │
             ▼
    For each scenario:
        [run_scenario_X(...)] --> Append to results[]
             │
             ▼
[format_and_clean_report_dataframe] --> Cleaned DataFrame
             │
             ▼
[to_csv] --> reports/automated_analysis_report.csv
             │
             ▼
[Visualizer.plot_batch_summary] --> PNG Files
```

---

## Configuration System

All configurable parameters are stored in:

```
d:\VITRIFY\data\parameters_config\project_parameters.xlsx
```

### Excel Structure
- **Sheet**: Typically a single "Parameters" sheet.
- **Columns**: `Parameter Name`, `Value`

### Loading Mechanism

```python
# config.py
def load_excel_config():
    df = pd.read_excel("project_parameters.xlsx")
    return dict(zip(df['Parameter Name'], df['Value']))

# constants.py
_config = load_excel_config()
E_SITE_KGCO2_PER_M2 = _get("E_SITE_KGCO2_PER_M2")
```

### Adding a New Parameter
1. Add row to `project_parameters.xlsx`.
2. Add `NEW_PARAM = _get("NEW_PARAM")` to `constants.py`.
3. Use `NEW_PARAM` in your code.

---

## Scenario Logic Deep Dive

### System Reuse (with Repair variant)

```
[Removal] --> [Transport A] --> [Repair?] --> [Transport B] --> [Installation]
    │                              │
    └── Yield Loss ────────────────┴──> [Waste Transport to Landfill]
```

- **Repair Branch**: If `repair_needed=True`, applies `YIELD_REPAIR` (e.g., 20%) and `REPAIR_KGCO2_PER_M2`.
- **No Repair**: Passes flow directly to Transport B.

### Closed-loop Recycling

```
[Removal] --> [Break?] --> [Transport A] --> [Float Plant Check] --> [Transport B]
    │            │                              │
    │            └── If broken on-site, apply break yield
    │                                           │
    │                                           └── SHARE_CULLET_FLOAT (e.g., 80%)
    │                                                goes to Float Plant.
    │                                                Rest is Waste.
    └── Laminated Glass Handling:
            If glass_type == "laminated": SHARE_CULLET_FLOAT = 0%
            (Cannot recycle laminated into float)
```

### Open-loop Recycling

Similar to Closed-loop, but instead of Float Plant, the output is split:
- `SHARE_CULLET_OPEN_LOOP_GW` → Glasswool
- `SHARE_CULLET_OPEN_LOOP_CONT` → Container Glass

---

## Extension Points

### Adding a New Scenario

1. **Define Function**: Create `run_scenario_new(...)` in `scenarios.py`.
2. **Register in Batch**: Add tuple to `scenarios` list in `execute_analysis_batch`.
3. **Add Constants**: If new process steps, add factors to `constants.py` (and Excel).
4. **Update Reporting**: Add stage keys to `format_and_clean_report_dataframe`.

### Adding a New Parameter

1. Add to `project_parameters.xlsx`.
2. Add `_get("...")` line to `constants.py`.
3. Use in relevant module.

### Adding a New Data Source

1. Add loader function to `input_helpers.py` (e.g., `define_igu_system_from_json`).
2. Create parser similar to `parse_db_row_to_group`.
3. Integrate into `main.py` mode selection.

---

## Testing Framework

### Unit Tests (`tests/test_batch_robustness.py`)

- `test_geometry_parsing_edge_cases()`: Verifies `parse_db_row_to_group`.
- `test_mixed_glazing_aggregation()`: Verifies `aggregate_igu_groups` handles mixed types.
- `test_mass_calculation_consistency()`: Verifies `compute_igu_mass_totals`.
- `test_laminated_detection_runtime()`: Verifies laminated glass detection.

### Integration Tests (`tests/test_integration_batch.py`)

- `test_full_batch_execution()`: Runs `execute_analysis_batch` with dummy data and verifies:
  - Report file is created.
  - All 11 scenarios are present.

### Running Tests

```bash
# Unit
python tests/test_batch_robustness.py

# Integration
python tests/test_integration_batch.py
```

---

## Glossary

| Term | Definition |
|------|------------|
| **IGU** | Insulating Glass Unit |
| **Yield** | Percentage of material that survives a process step |
| **Flow State** | Snapshot of IGU count, area, and mass at a point in the process |
| **Transport A** | Leg from Origin to Processor |
| **Transport B** | Leg from Processor to Final Destination (Reuse/Recycling) |
| **Backhaul Factor** | Multiplier accounting for empty return trips (e.g., 1.5 = 50% empty return) |
| **Closed-loop** | Recycling into the same product type (e.g., glass to glass) |
| **Open-loop** | Recycling into a different product type (e.g., glass to glasswool) |
| **Float Plant** | Factory producing sheet glass from raw or recycled cullet |
| **Cullet** | Recycled glass fragments used as feedstock |

---

## Document History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-15 | VITRIFY Team | Initial comprehensive architecture documentation |

