# LLM Personality Matching Experiment Pipeline

This project provides a fully automated and reproducible pipeline for testing a Large Language Model's (LLM) ability to solve a "who's who" personality matching task. It handles everything from data preparation and query generation to LLM interaction, response parsing, and final statistical analysis.

## Key Features

-   **Automated Pipeline**: A single command can run dozens of experimental replications, each with hundreds of trials.
-   **Reproducibility**: Uses deterministic seeding to ensure that the random selection of personalities and the shuffling of query items are repeatable.
-   **Self-Contained Runs**: Each experimental run is stored in a unique, timestamped, and descriptively named directory, containing all queries, responses, logs, and analysis results for complete traceability.
-   **Data Validation**: Includes multiple validation steps to ensure data integrity between the query generation, response processing, and final analysis stages.
-   **Robust Error Handling**: The main batch runner features a multi-attempt, automatic repair cycle to recover from intermittent API or network failures.
-   **Configurable**: Key parameters (LLM model, temperature, number of trials, etc.) are easily managed through a central `config.ini` file.

## Project Structure

```
.
├── output/                     # Default location for all experimental run outputs.
│   ├── run_.../                # A unique, self-contained directory for one replication.
│   │   ├── analysis_inputs/    # Processed data ready for the final analyzer.
│   │   ├── session_queries/    # All generated queries, manifests, and mappings.
│   │   ├── session_responses/  # Raw LLM responses and error logs.
│   │   └── replication_report_...txt # Final summary report for this run.
│   ├── batch_run_log.csv       # Log of all replications run by the batch script.
│   └── final_summary_results.csv # Master CSV compiling results from all runs.
│
├── src/                        # All Python pipeline scripts.
│   ├── build_queries.py        # Stage 1: Generates query files.
│   ├── run_llm_sessions.py     # Stage 2: Sends queries to the LLM.
│   ├── process_llm_responses.py# Stage 3: Parses LLM responses.
│   ├── analyze_performance.py  # Stage 4: Performs final statistical analysis.
│   ├── llm_prompter.py         # Worker script called by run_llm_sessions.
│   ├── query_generator.py      # Worker script called by build_queries.
│   ├── compile_results.py      # Utility: Compiles all run reports into one CSV.
│   ├── reprocess_runs.py       # Utility: Re-runs analysis on existing runs.
│   └── retry_failed_sessions.py# Utility: Finds and retries failed API calls.
│
├── tests/                      # Unit and integration tests for the pipeline.
│
├── data/                       # Source data files.
│   ├── personalities.txt       # Master list of personalities.
│   └── base_query.txt          # Template for the LLM prompt.
│
├── .env                        # For storing secrets like API keys (ignored by Git).
├── config.ini                  # Main configuration file for the project.
└── run_replications.ps1        # PowerShell script to orchestrate batch runs.
```

## Standard Workflow

The primary entry point for running a full study is the `run_replications.ps1` PowerShell script.

1.  **Configure**:
    *   Set your API key in a `.env` file in the project root (e.g., `OPENROUTER_API_KEY=sk-or-your-key`).
    *   Adjust experimental parameters (LLM model, temperature, etc.) in `config.ini`.

2.  **Execute**:
    *   Open a PowerShell terminal and run the batch script. This will execute the entire pipeline for the specified number of replications (default is 30).
    ```powershell
    .\run_replications.ps1
    ```
    *   The script will first run all experiments. Afterwards, it will automatically enter a repair phase, attempting to re-run any failed trials up to 3 times before finally compiling the results.

3.  **Review**:
    *   Monitor the progress in the console.
    *   Once complete, find the final aggregated results in `output/final_summary_results.csv`.
    *   Detailed logs and artifacts for each replication are available in their respective `output/run_.../` directories.

## Post-Run Utilities

These scripts are designed for manual intervention or re-analysis if needed.

### Manually Retrying Failures

If the automatic repair cycle fails, or if you want to manually re-run a specific trial (even a successful one), you can use `retry_failed_sessions.py`.

```bash
# Automatically find and fix all failures across all runs
python src/retry_failed_sessions.py --parent_dir output

# Manually re-run specific trials (e.g., 22 and 45) in a single run directory
python src/retry_failed_sessions.py --run_dir path/to/run_dir --indices 22 45
```

### Re-running Analysis

If you discover a bug in your analysis logic or want to add a new metric, you can re-run the analysis on all existing raw data without querying the LLM again.

```bash
# This command re-runs the processing and analysis stages for every
# run directory in 'output' and updates all reports and the final summary CSV.
python src/reprocess_runs.py --parent_dir output
```

## Testing

The project includes a suite of unit and integration tests. To run them, use `pytest`:

```bash
# Ensure you have pytest installed: pip install pytest
pytest -v
```