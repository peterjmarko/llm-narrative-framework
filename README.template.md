# LLM Personality Matching Experiment Pipeline

This project provides a fully automated and reproducible pipeline for testing a Large Language Model's (LLM) ability to solve a "who's who" personality matching task. It handles everything from data preparation and query generation to LLM interaction, response parsing, and final statistical analysis.

## Research Question
This project investigates whether large language models can perform a personality-matching task above chance level and how performance varies by model and experimental conditions.

## Key Features

-   **Automated Experiment Runner**: A single command executes an entire experiment, running dozens of replications, each with hundreds of trials.
-   **Guaranteed Reproducibility**: Each replication automatically archives the `config.ini` file used for that run, permanently linking the results to the exact parameters that generated them.
-   **Robust Error Handling & Resumption**: The pipeline is designed for resilience. Interrupted runs can be safely resumed. The `rebuild` command ensures data integrity after an interruption, and the `finalize` command is idempotent, automatically cleaning up corrupted summary data before writing a correct final version.
-   **Advanced Artifact Management**:
    -   **Reprocessing Engine**: The main runner has a `--reprocess` mode to re-run the analysis stages on existing experimental data, with a `--depth` parameter for recursive scanning.
    -   **Configuration Restoration**: Includes utilities to reverse-engineer and archive `config.ini` files for historical data that was generated before the auto-archiving feature was implemented.
-   **Hierarchical Analysis**: The `compile_results.py` script performs a bottom-up aggregation of all data. It creates a `final_summary_results.csv` within every run directory and then aggregates these into master summaries at each higher level of your project folder, creating a fully auditable research archive.
-   **Streamlined ANOVA Workflow**: The final statistical analysis is now a simple two-step process. `compile_results.py` first prepares a master dataset, which `run_anova.py` then automatically finds and analyzes, generating tables and publication-quality plots.
-   **Informative Console Output**: By default, the runner provides a clean, high-level console output. A `-Verbose` flag is available to enable detailed, real-time logs for debugging.

## Visual Architecture

The project's architecture can be understood through three different views: the code architecture, the data flow, and the experimental logic.

### 1. Code Architecture Diagram

This diagram shows how the scripts in the pipeline call one another, illustrating the hierarchy of control.

```mermaid
{{docs/diagrams/architecture_code.mmd}}
```

### 2. Data Flow Diagram

This diagram shows how data artifacts (files) are created and transformed by the pipeline scripts.

```mermaid
{{docs/diagrams/architecture_data_flow.mmd}}
```

### 3. Experimental Logic Flowchart

This diagram illustrates the scientific methodology for a single replication run.

```mermaid
{{docs/diagrams/architecture_experimental_logic.mmd}}
```

## Setup and Installation

1.  **Create Virtual Environment**:
    ```bash
    python -m venv .venv
    ```

2.  **Activate Environment**:
    *   On Windows (PowerShell): `.venv\Scripts\Activate.ps1`
    *   On macOS/Linux: `source .venv/bin/activate`

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Key**:
    *   Create a file named `.env` in the project root.
    *   Add your API key: `OPENROUTER_API_KEY=sk-or-your-key`.

## Configuration (`config.ini`)

The `config.ini` file is the central hub for defining all parameters for your experiments. Before running a new experiment, you should review and adjust the settings in this file. The pipeline is designed so that this configuration is automatically archived with the results for guaranteed reproducibility.

Below are some of the most critical settings.

### Experiment Settings (`[Experiment]`)

-   **`num_replications`**: The number of times the experiment will be repeated (e.g., `30`).
-   **`mapping_strategy`**: A key experimental variable. Can be `correct` (names are mapped to their true descriptions) or `random` (names are shuffled).
-   **`prompt_strategy`**: Defines which prompt template from `prompts.json` to use for the LLM queries.

### LLM Settings (`[LLM]`)

-   **`model`**: Specifies the API identifier for the Large Language Model to be tested (e.g., `mistralai/mistral-7b-instruct`). This is a primary independent variable.

### Analysis Settings (`[Analysis]`)

The `[Analysis]` section controls the behavior of the final study processing script (`process_study.ps1`).

-   **`min_valid_response_threshold`**: Sets the minimum average number of valid responses (`n_valid_responses`) a model's experiment must have to be included in the final analysis. This is crucial for automatically excluding unreliable models that failed to produce consistent output, preventing them from skewing the statistical results.
    -   A value of `25` is a reasonable default for an experiment with 100 trials per replication.
    -   Set to `0` to disable this filter and include all models regardless of their response rate.

## Standard Workflow

The workflow is designed to be fully automated. Each experiment run produces self-documenting output, which simplifies the final analysis.

### Phase 1: Running Experiments

The main entry point for executing a complete experiment (e.g., all 30 replications for a single LLM) is the `run_experiment.ps1` PowerShell script, which acts as a wrapper around `replication_manager.py`.

1.  **Configure**:
    *   Ensure your environment is set up and your API key is in the `.env` file.
    *   Adjust experimental parameters in `config.ini`. For example, to run the experiment with a random name-to-description mapping, you would set `mapping_strategy = random`.

2.  **Execute**:
    *   Open a PowerShell terminal (with the virtual environment activated) and run the main experiment script.
    ```powershell
    # Run with standard (quiet) output
    .\run_experiment.ps1

    # For detailed debugging, run with the -Verbose switch
    .\run_experiment.ps1 -Verbose
    ```
    *   The script manages the entire batch run. It will first run all replications, then automatically enter a repair phase for any failures.
    *   **Crucially**, each replication's output directory will now contain a `config.ini.archived` file, making it a self-contained, reproducible artifact.

3.  **Repeat for All Conditions**: Repeat steps 1-2 for each experimental condition you want to compare. It is best practice to organize the outputs into separate folders.
    *   Run once with `mapping_strategy = correct` and save the output to a folder like `output/reports/exp_mistral_correct_map`.
    *   Run again with `mapping_strategy = random` and save to `output/reports/exp_mistral_random_map`.

### Phase 2: Processing the Study

After running all individual experiments, this phase uses a single command to aggregate all data and perform the final statistical analysis across the entire study.

1.  **Run Study Processor**: Execute the `process_study.ps1` script, pointing it at the top-level directory that contains all your experiment folders (e.g., `output/reports`).
    ```powershell
    # Process the entire study located in the 'output/reports' directory
    .\process_study.ps1 -StudyDirectory "output/reports"
    ```
    This script automates the two critical post-processing stages:
    *   **Compilation**: It first runs `compile_results.py` to scan the entire directory tree, aggregating all data into a single master `final_summary_results.csv` file at the top of your study directory.
    *   **Analysis**: It then runs `run_anova.py` on the newly created master dataset, performing a full statistical analysis (ANOVA, Tukey's HSD).

2.  **Review Final Artifacts**: In the top-level analysis directory (`output/reports/anova/`), you will now find:
    *   Publication-quality **box plot `*.png` images** for each metric.
    *   A complete `STUDY_analysis_log.txt` with all statistical tables (ANOVA, Tukey's HSD, Performance Groups, etc.).
    *   An `archive/` subdirectory containing the results from the previous analysis run, providing a simple backup.

## Migrating Old Experiment Data

Due to updates in the reporting format and data processing pipeline, experiment data generated before a certain version may be incompatible with the latest analysis tools. A one-time migration process is required to upgrade these old data directories.

This process will:
1.  Archive old `config.ini` files.
2.  Rebuild individual `replication_report.txt` files into the modern format.
3.  Clean up legacy artifacts.
4.  Perform a final reprocessing to regenerate all summary files and create a clean data set.

#### Migration Steps

Ensure your Python environment is activated before running these commands from the project root directory.

**A. Manual Steps**

You can run the migration manually by executing these four steps in order. Replace `<path_to_old_experiment_dir>` with the actual path (e.g., `output/reports/6_Study_4`).

1.  **Patch Configs:** This archives the `config.ini` file in each `run_*` subdirectory.
    ```bash
    python src/patch_old_runs.py "<path_to_old_experiment_dir>"
    ```

2.  **Rebuild Reports:** This uses the archived configs to regenerate each `replication_report.txt` with a modern structure and a valid `METRICS_JSON` block.
    ```bash
    python src/rebuild_reports.py "<path_to_old_experiment_dir>"
    ```

3.  **Clean Artifacts:** Manually delete the following old files and directories from within the `<path_to_old_experiment_dir>`:
    - The top-level `final_summary_results.csv`
    - The top-level `batch_run_log.csv`
    - The `analysis_inputs` directory inside *each* `run_*` subdirectory.
    - All `*.txt.corrupted` files inside *each* `run_*` subdirectory.

4.  **Final Reprocess:** This will regenerate the summary CSV files, logs, and all analysis artifacts using the modern, rebuilt reports.
    ```bash
    python src/replication_manager.py --reprocess "<path_to_old_experiment_dir>"
    ```

**B. Automated Scripts**

Scripts are provided to automate all four steps for Windows environments. Choose the one that matches your preferred terminal.

-   **Using PowerShell (Recommended for Windows 10/11):**
    The PowerShell script offers more robust error handling and detailed output.
    ```powershell
    # If script execution is restricted, you can bypass the policy for this single command:
    PowerShell.exe -ExecutionPolicy Bypass -File .\migrate_old_experiment.ps1 "<path_to_old_experiment_dir>"

    # Or, if your execution policy allows it, run directly:
    .\migrate_old_experiment.ps1 "<path_to_old_experiment_dir>"
    ```

-   **Using Command Prompt (Legacy):**
    ```batch
    migrate_old_experiment.bat "<path_to_old_experiment_dir>"
    ```

After the chosen script completes, the data in the target directory will be fully migrated and compatible with the latest version of the toolkit.

---

## Maintenance and Utility Scripts

The project includes several scripts for maintenance, diagnostics, and handling historical data.

*   **`replication_manager.py`**:
    *   The main batch runner for managing multiple replications. Can be invoked in a reprocessing mode (`--reprocess`) to fix or update the analysis for existing runs without re-running expensive LLM sessions.
    *   Usage: `python src/replication_manager.py path/to/experiment --reprocess --depth 1`

*   **`rebuild_reports.py`**:
    *   A powerful utility to regenerate complete `replication_report.txt` files from the ground-truth archived config. Useful for applying fixes to the processing or analysis stages across an entire study.
    *   Usage: `python src/rebuild_reports.py path/to/study`

*   **`patch_old_runs.py`**:
    *   **Utility for historical data.** Scans a directory for old experiment runs that are missing a `config.ini.archived` file and generates one for each by reverse-engineering the `replication_report.txt`. Supports recursive scanning with `--depth`.
    *   Usage: `python src/patch_old_runs.py "path/to/old/experiments" --depth -1`

*   **`log_manager.py`**:
    *   The core utility for automated log management, operating in several modes. It is called by the main runner but can also be used manually for maintenance.
    *   `start`: Archives any old log and creates a new, empty one with a header.
    *   `rebuild`: Recreates the log from scratch by parsing all existing replication reports in a directory, ensuring a clean state.
    *   `finalize`: Intelligently cleans any existing summary from the log, recalculates a correct summary from the clean data, and appends it. This command is safe to re-run on a corrupted or finalized log.

*   **`retry_failed_sessions.py`**:
    *   Used automatically by the main runner for the repair cycle. Can be run manually to fix failed API calls in a specific run.

*   **`verify_pipeline_completeness.py`**:
    *   A diagnostic tool to check for missing files or incomplete stages in a run directory.

*   **`inject_metadata.py`**:
    *   **LEGACY UTILITY:** This script is no longer part of the standard workflow. It should only be used in rare cases for one-off data labeling where the standard `config.ini` archiving is not feasible.

---

## Testing

The project includes a suite of unit and integration tests. To run them, use `pytest`:

```bash
# Ensure you have pytest installed: pip install pytest
pytest -v
```