# Contributing to the LLM Personality Matching Project

This document serves as the **Developer's Guide** for the project. Its purpose is to provide clear and comprehensive guidelines for anyone wishing to contribute, covering development environment setup, project standards, and the full contribution workflow.

## Getting Started: Development Environment Setup

This guide provides comprehensive setup instructions for developers. Following these steps ensures your environment is correctly configured with all necessary tools and hooks.

### Step 1: Install Prerequisite Tools

Before cloning the project, ensure these essential tools are installed on your system.

| Tool | Purpose | Installation |
| :--- | :--- | :--- |
| **Python** | Core Language | Version 3.11+ from [python.org](https://www.python.org/downloads/) |
| **Git** | Version Control | Download from [git-scm.com](https://git-scm.com/downloads) |
| **Node.js** | Documentation Build | **LTS** version from [nodejs.org](https://nodejs.org/en/download/) |
| **Pandoc** | Document Conversion | Download from [pandoc.org](https://pandoc.org/installing.html) |
| **PDM** | Dependency Manager | `pip install --user pdm` |
| **Commitizen** | Commit Standardization | `pip install --user commitizen` |

### Step 2: Clone and Set Up the Project

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ````

2.  **Set the Project's Python Interpreter (Crucial Step)**:
    You must explicitly tell PDM which Python interpreter to use for this project. This prevents conflicts and ensures the local `.venv` is created correctly.
    
    First, try a simple alias:
    ```bash
    # Use the version you have installed, e.g., 3.11
    pdm use python3.11
    ```
    If this fails with a `[NoPythonVersion]` error, provide the **full, absolute path** to your Python executable.

    *   **To find the path on Windows:** Use the `py` launcher.
        ```bash
        py -0p 
        ```
        Copy the full path for the desired version.
    *   **To find the path on macOS/Linux:** Use the `which` command.
        ```bash
        which python3.11
        ```

    Now, use the full path you found (in quotes):
    ```bash
    # Example for Windows. Replace with your actual path.
    pdm use "C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe"
    ```

3.  **Install All Dependencies and Tools**:
    This single command installs everything needed for development: Python packages, dev tools, and pre-commit hooks. The `-G dev` flag installs the "dev" dependency group, which includes all development tools.
    ```bash
    pdm install -G dev
    ```

4.  **Install Node.js Dependencies**:
    Finally, install the Node.js tools required for the documentation build script.
    ```bash
    npm install
    ```
Your development environment is now fully configured.

### 3. Adding New Dependencies

If your contribution requires a new package, add it with PDM. This will update both `pyproject.toml` and `pdm.lock` automatically.

```bash
# Add a new core dependency
python -m pdm add new-package-name

# Add a new development-only dependency
python -m pdm add -G dev new-dev-package-name
```

## Getting Acquainted: The Interactive Guided Tour

For new contributors, the best way to understand the data preparation pipeline is to use the **Interactive Guided Tour**. This is a step-by-step walkthrough of the entire data processing workflow and a highly recommended first step for any developer looking to work on these scripts.

Detailed instructions for running the tour are available in the **[🧪 Testing Guide (TESTING.md)](TESTING.md)** under the "Layer 3: Data Pipeline Integration Testing" section.

## Developer Utilities (`scripts/` folder)

The `scripts/` directory contains helper utilities for development, maintenance, and building documentation. You generally do not need to run these directly, as many are called by PDM script shortcuts (e.g., `pdm run build-docs`, `pdm run release`).

| Script | Description |
| :--- | :--- |
| `build_docs.py` | Orchestrates the entire documentation build process. |
| `changelog_hook.py` | A pre-commit hook for `commitizen` to ensure changelog entries are correctly formatted. |
| `docx_postprocessor.py` | A helper for `build_docs.py` that inserts page breaks into generated DOCX files. |
| `finalize_release.py` | Automates the version bumping and changelog generation process. |
| `generate_scope_report.py` | Generates a high-level summary of the project's file structure. |
| `lint_docstrings.py` | Scans the codebase to enforce docstring standards. |
| `lint_file_headers.py` | Scans the codebase to enforce file header and footer standards. |

## Code Quality and Style

All contributions must adhere to standard software engineering best practices to ensure the codebase remains clean, readable, and maintainable.

*   **DRY (Don't Repeat Yourself)**: Avoid duplicating code. If you find yourself writing the same logic in multiple places, refactor it into a reusable function or a shared utility module. For example, the colored banner formatting in the PowerShell scripts is handled by a single, shared `Format-Banner` function.

*   **KISS (Keep It Simple, Stupid)**: Write the simplest possible code that solves the problem. Avoid premature optimization or overly complex solutions for simple tasks. Code should be straightforward and easy for other developers to understand.

*   **YAGNI (You Ain't Gonna Need It)**: Do not add functionality that is not required by the current set of tasks. Focus on solving the immediate problem, and avoid adding features just because they *might* be useful in the future.

*   **Readability Over Conciseness**: Clear, readable code is always preferred over clever, one-line solutions that are difficult to understand. Use descriptive variable names, add comments where the logic is complex, and break down long functions into smaller, more manageable pieces.

## Project-Specific Design Principles

To maintain the quality and consistency of the codebase, all contributions should adhere to the following core design principles.

*   **Separation of Concerns**: Each script must have a single, well-defined responsibility. This principle applies in two key ways:
    1.  **By Workflow Pattern (Create -> Check -> Fix)**: For managing experiments, the framework uses distinct scripts for creating, auditing, and repairing data. For example, `audit_experiment.ps1` only *checks* the state, while `fix_experiment.ps1` *fixes* it.
    2.  **By Data Pipeline Stage**: For complex data processing, workflows are broken into a clear, sequential pipeline of single-purpose scripts. For example, the original monolithic `validate_adb_data.py` was refactored into two more focused scripts: `find_wikipedia_links.py` is responsible only for finding subject URLs, while `validate_wikipedia_pages.py` handles the intensive work of validating the page content and generating the final reports.

    This separation makes the system predictable, easier to debug, and more maintainable.

*   **Fail Loudly and Early**: Scripts must not hide errors. If a script encounters a fatal error, it must exit with a non-zero status code and provide a clear, informative error message to `stderr`. Silent failures that allow the pipeline to continue in a broken state are considered critical bugs.

*   **Clarity and Control in Logging**: Scripts should be informative but not noisy by default. Standard runs should log high-level progress (e.g., stage completion). Detailed, line-by-line logs or internal state information should only be displayed when a `--verbose` flag is used.

*   **Predictable and Safe User Interaction**: All scripts that modify or delete data must follow a standard interaction model. By default, they should prompt for confirmation before overwriting existing files. A `--force` flag should be available to bypass this prompt for automated workflows. In either case, a backup of the overwritten data should be created automatically.

*   **Guaranteed Reproducibility**: Experimental results must be verifiably linked to the parameters that created them. The pipeline ensures this by automatically archiving the `config.ini` file within each run's output directory, creating an immutable record.

*   **Standardized Wrapper and Backend Interfaces**: All user-facing PowerShell wrappers and their Python backends must adhere to a consistent architectural pattern to ensure robustness and predictability.
    -   **Parameter Naming**: Wrappers that operate on a single experiment use the parameter `$ExperimentDirectory`. Wrappers that operate on a study (a directory of experiments) use `$StudyDirectory`.
    -   **PowerShell-to-Python Calls**: All calls from a PowerShell wrapper to a Python backend must use the **robust array-building method** to pass arguments. This correctly handles the mix of commands, flags, and positional arguments.
    -   **PowerShell-to-PowerShell Calls**: All calls from one PowerShell wrapper to another must use the **robust hashtable splatting method** for passing named parameters.
    -   **Python Argument Parsing**: Python backends maintain simple and conventional command-line interfaces, typically using a single primary positional argument for the target directory or a `verb + noun` pattern for more complex operations.

*   **Resilient and User-Friendly Pipeline Scripts**: All long-running data preparation and validation scripts must adhere to a standard, modern architecture to ensure a consistent and robust user experience. Key features of this standard include:
    -   **Intelligent Startup**: Scripts must use a "Filter First, Then Decide" architecture to accurately determine if there is new work to be done.
    -   **Automatic Stale Check**: Scripts must automatically detect if input files are newer than their own output and trigger a non-interactive re-run.
    -   **Full Resumability**: Scripts must be able to resume an interrupted run, processing only the records that were not previously completed. This includes appending to existing output files rather than overwriting them.
    -   **Interrupt Safety**: All processing loops must be wrapped in a `try...except KeyboardInterrupt` block to ensure that a user interruption (`Ctrl+C`) results in a graceful exit with partial results saved correctly.
    -   **Polished Reporting**: Scripts must use a `finalize_and_report` function to provide consistent, informative status messages for all exit conditions (e.g., success, interruption, up-to-date).

## Contribution Workflow

### 1. Create a Branch

Before making any changes, create a new branch from the `main` branch. Use a descriptive name that reflects the nature of your work.

```bash
# Example for a new feature
git checkout -b feat/add-new-analysis-metric

# Example for a bug fix
git checkout -b fix/correct-data-parsing-error
```

### 2. Make Your Changes

Write your code, update data, or adjust documentation as needed.

*   **Code**: Modify the Python files in `src/` or `tests/`. As you modify the code, you **must** update the corresponding docstrings to reflect any changes in logic, parameters, or behavior. Pre-commit hooks will handle formatting and linting.
*   **Data**: Modifications to data files should be handled carefully.
    -   **`data/foundational_assets/`**: Changes to these files will alter the database generation logic.
        -   `eminence_scores.csv` and `ocean_scores.csv` are generated by scripts but are treated as foundational assets. Modifying them directly will affect the final subject pool.
        -   Files like `point_weights.csv` and the neutralized delineations are static configurations. Justify any changes in your pull request.
    -   **`data/sources/`**: These files are considered static and should not be modified.
    -   **`data/processed/` & `data/intermediate/`**: These files are generated by scripts and should not be edited manually.
*   **Documentation Templates**: This refers to the high-level project documentation, not docstrings.
    -   Modify `docs/DOCUMENTATION.template.md` and its diagram sources in `docs/diagrams/`.
    -   Modify other root-level files like this guide (`CONTRIBUTING.md`) as needed.

### 3. Run the Test Suite

This project includes tests that must pass before a pull request will be merged. The pre-commit hooks do not run these tests automatically, so you must run them manually.

The test suite is divided into two parts, one for the Python source code and one for the PowerShell orchestration scripts.

*   **Python Tests (Pytest)**: These tests cover the core data processing, analysis, and utility functions in the `src/` directory.

    Use the PDM script shortcut:
    ````bash
    pdm run test
    ````

*   **PowerShell Tests**: The PowerShell orchestration scripts are tested using a custom, lightweight integration testing harness, not a traditional framework like Pester. This decision was made to ensure maximum reliability and compatibility across different environments, as Pester's advanced mocking and assertion features can introduce complexities that are not necessary for testing these simple wrapper scripts.

| Command | Workflow Tested |
| :--- | :--- |
| `pdm run test-ps-exp` | Single Experiment Lifecycle (`new`, `audit`, `fix`, `migrate`) |
| `pdm run test-ps-stu` | Study Processing (`compile_study.ps1`) |
| `pdm run test-ps-aud-stu`| Study Auditing (`audit_study.ps1`) |

#### How to Write a New Test (Best Practices)

Most modules in `src/` are designed as executable scripts. The standard testing pattern for these modules is to **import them directly and call their `main()` function**, rather than running them as a subprocess. This ensures that code coverage is collected reliably.

**All new tests for scripts must follow this pattern:**

1.  **Structure the Script:** Ensure the target script (e.g., `src/my_script.py`) has its core logic inside a `main()` function that returns an exit code (`0` for success, non-zero for failure). The call to `main()` must be protected by an `if __name__ == "__main__":` block.

    ````python
    # src/my_script.py
    import sys

    def main():
        # ... logic for parsing args and running the script ...
        print("Script finished successfully.")
        return 0 # Return 0 for success

    if __name__ == "__main__":
        # This code only runs when the script is executed directly
        # It does NOT run when the script is imported by a test
        sys.exit(main())
    ````

2.  **Structure the Test:** In your test file, import the script module and use `unittest.mock.patch` to simulate command-line arguments (`sys.argv`).

    ````python
    # tests/test_my_script.py
    import unittest
    from unittest.mock import patch
    import sys
    import my_script # Import the module we are testing

    class TestMyScript(unittest.TestCase):
        def test_some_functionality(self):
            # 1. Define the fake command-line arguments the script expects
            test_args = ['my_script.py', 'path/to/data', '--option', 'value']

            # 2. Patch sys.argv and call the script's main() function directly
            with patch.object(sys, 'argv', test_args):
                return_code = my_script.main()
                self.assertEqual(return_code, 0) # Check for success exit code
            
            # 3. Assert that the script created the expected files or side effects
            # ... your file-based assertions here ...
    ````

This approach is the required standard for maintaining test quality and coverage across the project.

### 4. Commit Your Changes

This project uses a standardized workflow to ensure all code is clean, documented, and properly formatted before being committed.

#### Pre-Commit Checklist

Before committing, please perform the following steps in order. For detailed explanations, see the guide below.

1.  **Run Linters**:
    ```bash
    pdm run python scripts/lint_file_headers.py
    pdm run python scripts/lint_docstrings.py --deep
    ```

2.  **Build Documentation**:
    ```bash
    pdm run build-docs
    ```

3.  **Review and Stage Changes**:
    Review your work with `git status`, then stage all changes with `git add .`.

4.  **Commit with Commitizen**:
    Use the interactive tool to create a compliant commit message.
    ```bash
    pdm run commit
    ```

#### Detailed Workflow Guide

After ensuring all tests pass (see the previous section), follow this detailed workflow.

**Linting File Headers**
Run the header linter. This script will check all Python and PowerShell files for a compliant header/footer and prompt you to fix any issues automatically.
```bash
pdm run python scripts/lint_file_headers.py
```

**Linting Docstrings (Manual Fix)**
Run the docstring linter. This is a **read-only** tool that will report any missing or incomplete docstrings. You must manually edit the reported files to fix the issues.
```bash
# Run a high-level scan first (checks module-level docstrings)
pdm run python scripts/lint_docstrings.py

# Run a deep scan for a more thorough check of functions and classes
pdm run python scripts/lint_docstrings.py --deep
```

**Step 3: Update High-Level Documentation**
If your changes affect the project's architecture, workflow, or data structures, update the relevant source files:
-   `docs/DOCUMENTATION.template.md`
-   Diagram source files in `docs/diagrams/`

**Step 4: Build the Final Documentation**
After updating any documentation templates or diagrams, you **must** run the build script to generate the final `docs/DOCUMENTATION.md` file.
```bash
pdm run build-docs
```

**Step 5: Stage and Commit Your Changes**
This project uses **`commitizen`** to enforce Conventional Commits. The final step is to stage your work and use the interactive commit tool.

1.  **Review Your Changes**:
    Check `git status` to ensure all intended changes are ready.
    ```bash
    git status
    ```

2.  **Stage Your Changes**:
    Add all new and modified files to the Git staging area.
    ```bash
    git add .
    ```

3.  **Run the Interactive Commit Command**:
    This command will guide you through creating a perfectly formatted commit message. Pre-commit hooks will run automatically and must pass for the commit to be finalized.
    ```bash
    pdm run commit
    ```

### 5. Releasing a New Version (Maintainers Only)

The release process is fully automated into a single command. It programmatically determines the next version, creates the release commit, generates a detailed changelog, and applies the correct Git tag.

1.  **Ensure `main` is up-to-date**:
    ```bash
    git checkout main
    git pull origin main
    ```

2.  **Run the Automated Release Command**:
    ```bash
    pdm run release
    ```
    This script handles all the necessary steps:
    *   Runs `cz bump --dry-run` to determine the correct next version.
    *   Executes the actual `cz bump` to create the initial release commit and tag.
    *   Generates a detailed, multi-line changelog entry.
    *   Amends the release commit to include the detailed changelog.
    *   Force-moves the Git tag to the final, amended commit.

#### How to Undo a Version Bump
If you run `cz bump` by mistake or realize a commit was missed, you must manually undo the release before trying again. Follow these steps precisely:

1.  **Undo the Commit**: The `bump` command creates a commit (e.g., `chore(release): v2.3.0`). Roll it back but keep the file changes staged for editing.
    ```bash
    git reset --soft HEAD~1
    ```

2.  **Delete the Git Tag**: The command also creates a version tag (`vX.Y.Z`) that must be deleted locally before you can re-create it.
    ```bash
    # Replace v2.3.0 with the actual tag that was created
    git tag -d v2.3.0
    ```

3.  **Revert File Changes**: The `reset` command kept the changes in your working directory. You must now manually revert them.
    *   **`pyproject.toml`**: Open this file and revert the `version` key in **both** the `[project]` and `[tool.commitizen]` sections to its original value (e.g., from `2.3.0` back to `2.2.1`).
    *   **`CHANGELOG.md`**: Open this file and delete the new version entry that was added at the top.

After these steps, your repository is clean. You can now make any additional changes, stage them, and then run the automated release command again.
    ```bash
    pdm run release
    ```

### 6. Submit a Pull Request

1.  Push your branch to your fork on GitHub.
2.  Open a pull request against the `main` branch of the original repository.
3.  Provide a clear title and a detailed description of your changes. If your PR addresses an existing issue, link to it in the description (e.g., "Closes #123").

### Continuous Integration (CI) Checks

This project is equipped with an automated Continuous Integration (CI) workflow using GitHub Actions. This workflow acts as a guardian for code quality and consistency.

When you submit a pull request, a series of automated checks will be run against your changes. Your pull request **must pass all checks** before it can be merged.

The CI pipeline performs the following key validation steps:
1.  **Installs Dependencies:** It creates a clean environment on Windows and Linux and installs all project dependencies to ensure compatibility.
2.  **Runs Linters:** It executes the project's quality-control scripts to ensure your code adheres to our standards:
    *   `pdm run check-headers`: Verifies that all script files have the correct license and filename header.
    *   `pdm run python scripts/lint_docstrings.py`: Performs a high-level check for the presence of module docstrings.
3.  **Validates Documentation:** It runs `pdm run build-docs --check` to confirm that any changes to diagrams or templates have been correctly compiled into the final documentation.

You can—and should—run these same checks locally before committing your code to ensure your pull request will pass.

```powershell
# Run the same header check the CI does
pdm run check-headers

# Run the docstring linter
pdm run python scripts/lint_docstrings.py

# Run the documentation validation
pdm run build-docs --check
```

If the CI build fails, please review the logs for the failed step on your pull request page, fix the issues locally, and push the new changes to your branch. This will automatically trigger a new CI run.

## Project Scope

To help guide contributions, please note the intended scope of the project. The framework's hierarchy culminates at the "study" level, which aggregates multiple experiments.

While there are parallel scripts for experiments and studies (e.g., `repair_experiment.ps1` and `repair_study.ps1`), a workflow to process or aggregate multiple studies (e.g., a hypothetical `process_studies.ps1`) is considered out of scope. Contributions focusing on meta-analysis across different studies fall outside the project's current goals.

## Reporting Bugs and Suggesting Enhancements

If you find a bug or have an idea for an improvement, please **open an issue** on GitHub.
*   For bugs, include a clear title, steps to reproduce, expected behavior, and any relevant logs.
*   For enhancements that align with the project scope, describe the feature and why it would be valuable.

