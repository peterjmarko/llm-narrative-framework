# LLM Personality Matching Experiment Pipeline

This project provides a fully automated and reproducible pipeline for testing a Large Language Model's (LLM) ability to solve a "who's who" personality matching task. It handles everything from data preparation and query generation to LLM interaction, response parsing, and final statistical analysis.

## Key Features

-   **Automated Pipeline**: A single command can run dozens of experimental replications, each with hundreds of trials.
-   **Reproducibility**: Uses deterministic seeding to ensure that the random selection of personalities and the shuffling of query items are repeatable.
-   **Self-Contained Runs**: Each experimental run is stored in a unique, timestamped, and descriptively named directory, containing all queries, responses, logs, and analysis results for complete traceability.
-   **Data Validation**: Includes multiple validation steps to ensure data integrity between the query generation, response processing, and final analysis stages.
-   **Robust Error Handling**: The main batch runner features a multi-attempt, automatic repair cycle to recover from intermittent API or network failures.
-   **Configurable**: Key parameters (LLM model, temperature, number of trials, etc.) are easily managed through a central `config.ini` file.
-   **Publication-Ready Analysis**: Automatically generates statistical summaries (ANOVA, post-hoc tests) and publication-quality plots with a single command.

## Visual Architecture

The project's architecture can be understood through three different views: the code architecture, the data flow, and the experimental logic.

### 1. Code Architecture Diagram

This diagram shows how the scripts in the pipeline call one another, illustrating the hierarchy of control from the main batch runner down to the individual worker scripts.

```mermaid
{{docs/diagrams/architecture_code.mmd}}
```

### 2. Data Flow Diagram

This diagram shows how data artifacts (files) are created and transformed by the pipeline scripts, tracing the data from its source to the final outputs.

```mermaid
{{docs/diagrams/architecture_data_flow.mmd}}
```

### 3. Experimental Logic Flowchart

This diagram illustrates the scientific methodology for a single replication run, explaining the conceptual flow of the experiment from sampling to final analysis.

```mermaid
{{docs/diagrams/architecture_experimental_logic.mmd}}
```

## Setup and Installation

1.  **Create Virtual Environment**: From the project root, create a Python virtual environment.
    ```bash
    python -m venv .venv
    ```

2.  **Activate Environment**:
    *   On Windows (PowerShell):
        ```powershell
        .venv\Scripts\Activate.ps1
        ```
    *   On macOS/Linux:
        ```bash
        source .venv/bin/activate
        ```

3.  **Install Dependencies**: Install all required packages using pip and the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Key**:
    *   Create a file named `.env` in the project root.
    *   Add your API key to this file, for example: `OPENROUTER_API_KEY=sk-or-your-key`.

## Standard Workflow

The primary workflow involves two main phases: running the experiments and then analyzing the results.

### Phase 1: Running Experiments

The entry point for running a full study is the `run_replications.ps1` PowerShell script.

1.  **Configure**:
    *   Ensure your environment is set up and your API key is in the `.env` file.
    *   Adjust experimental parameters (LLM model, temperature, etc.) in `config.ini`.

2.  **Execute**:
    *   Open a PowerShell terminal (with the virtual environment activated) and run the batch script. This will execute the entire pipeline for the specified number of replications (default is 30).
    ```powershell
    .\run_replications.ps1
    ```
    *   The script will first run all experiments. Afterwards, it **automatically** enters a repair phase, attempting to re-run any failed trials up to 3 times.

3.  **Compile Initial Results**: After the batch run completes, `run_replications.ps1` automatically calls `compile_results.py` to create a `final_summary_results.csv` for that set of runs. Repeat this process for all experimental conditions (e.g., for each LLM you want to test).

### Phase 2: Statistical Analysis and Visualization

Once you have run all desired experiments (e.g., one batch for each model, each in its own subfolder), you perform the final cross-condition analysis.

1.  **Run Final Analysis**: Use `run_anova.py` and point it at the parent directory containing all your experiment sets. The script will automatically find all `final_summary_results.csv` files, aggregate them into a master dataset, perform the ANOVA, generate plots, and create a detailed log file.
    ```powershell
    # Example: Analyze all data within the '3_Study' folder
    python src/run_anova.py output/reports/3_Study
    ```

2.  **Review Final Artifacts**: In the study directory (`output/reports/3_Study/`), you will now find:
    *   `MASTER_ANOVA_DATASET.csv`: The aggregated data from all runs.
    *   The final, publication-quality **box plot `*.png` images**.
    *   A complete `MASTER_ANOVA_DATASET_analysis_log.txt` with all statistical tables.

## Testing

The project includes a suite of unit and integration tests. To run them, use `pytest`:

```bash
# Ensure you have pytest installed: pip install pytest
pytest -v
```