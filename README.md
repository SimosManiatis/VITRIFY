# VITRIFY - IGU Recovery Environmental Impact Prototype

This project calculates and compares the environmental impact (Carbon Emissions in kg CO2e) of various recovery scenarios for Insulating Glass Units (IGUs) removed from buildings. It provides decision support for Reuse, Repair, Repurposing, and Recycling pathways.

## Features

- **11 Recovery Paths**: Detailed analysis of variants including:
  - **System Reuse**: Direct Reuse vs. Reuse w/ Repair.
  - **Component Reuse**: Disassembly and Reconditioning.
  - **Component Repurpose**: Light, Medium, and Heavy intensity variants.
  - **Closed-loop Recycling**: Intact vs. Broken on-site (Float plant quality checks).
  - **Open-loop Recycling**: Intact vs. Broken on-site (Glasswool/Container outputs).
  - **Landfill**: Baseline comparison.
  
- **Batch Analysis**:
  - Automatically processes entire product databases (Excel).
  - Runs **all 11 scenarios** for every product.
  - Generates comprehensive CSV reports in `reports/`.
  - Robust error handling and validation.

- **Detailed Reporting**:
  - **CSV**: KPIs (Yield, Emissions, Mass) and stage-by-stage breakdowns.
  - **Plots**: Automated generation of emission distribution charts.
  - **Markdown Breakdowns**: Granular logs for deep-dive analysis.

- **Transport Modeling**: Configurable Truck/Ferry routes with emission factors (DEFRA 2024, Z.E. Trucks, etc.).

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd VITRIFY
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # Unix:
    source .venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

The tool has a single entry point that offers both **Interactive (Single Run)** and **Batch (Automated)** modes.

### Run the Tool
```bash
python src/Recovery_IGU_CO2.py
```
*Or via module:*
```bash
python -m src.igu_recovery.main
```

### Modes
1.  **Single Run (Interactive)**:
    - Step-by-step prompts to define a specific IGU and scenario.
    - ideal for quick checks or sensitivity analysis.
    - Generates plots and Markdown breakdown for the single run.

2.  **Automated Analysis (Batch)**:
    - Loads the product database from `data/`.
    - Asks for Global Parameters (Location, Transport assumptions) once.
    - Iterates through the entire database.
    - Saves results to `d:\VITRIFY\reports\automated_analysis_report.csv`.

## Project Structure

```
d:\VITRIFY\
├── src\
│   ├── Recovery_IGU_CO2.py      # Entry point
│   └── igu_recovery\            # Main Code Package
│       ├── main.py              # Application Logic
│       ├── scenarios.py         # 11 Path Logic implementations
│       ├── models.py            # Data Structures
│       └── utils\               # Helpers & Math
├── data\                        # Product Database & Parameters
├── docs\                        # Methodology Documentation
├── reports\                     # Generated Outputs (CSV, Plots)
├── tests\                       # Integration & Unit Tests
└── README.md
```

## Testing

To verify the robustness of the installation:
```bash
# Run Unit Tests
python tests/test_batch_robustness.py

# Run Integration Test (End-to-End Batch)
python tests/test_integration_batch.py
```

## License
Proprietary. All rights reserved.
