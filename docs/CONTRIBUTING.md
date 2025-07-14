# Contributing to the LLM Personality Matching Project

We welcome contributions to this project! This document provides guidelines for setting up your development environment, adhering to project standards, and submitting your work.

## Getting Started: Development Environment Setup

This guide provides comprehensive setup instructions for developers. Following these steps ensures your environment is correctly configured with all necessary tools and hooks.

### Step 1: Install Prerequisite Tools

Before cloning the project, ensure these essential tools are installed on your system.

*   **Python**: Version 3.8 or higher. Download from [python.org](https://www.python.org/downloads/).
*   **Git**: For version control. Download from [git-scm.com](https://git-scm.com/downloads).
*   **Node.js and npm**: Required for building documentation. Download the **LTS** version from [nodejs.org](https://nodejs.org/en/download/).
*   **Pandoc**: A universal document converter. Download from [pandoc.org](https://pandoc.org/installing.html).
*   **PDM**: The Python dependency manager. Install it once globally with pip:
    ```bash
    pip install --user pdm
    ```
*   **Commitizen**: A tool for standardized commits and automated changelogs. Install it once globally with pip:
    ```bash
    pip install --user commitizen
    ```
*   **Commitizen**: A tool for standardized commits and automated changelogs. Install it once globally with pip:
    ```bash
    pip install --user commitizen
    ```

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
    This single command installs everything needed for development: Python packages, dev tools, and pre-commit hooks. The `-d` flag includes all development dependencies.
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

*   **Code**: Modify the Python files in `src/` or `tests/`. The pre-commit hooks will automatically handle formatting (Black) and linting (Flake8).
*   **Data**: The project's ground truth is stored in the `data/` directory, particularly the file containing the 5,000 historical individuals and their verified birth data. If you are adding or correcting entries, edit this source file directly. Changes here are significant, so please justify them clearly in your pull request.
*   **Documentation**: The project's main documentation is generated from source files in the `docs/` directory.
    -   To edit the main documentation, modify `docs/DOCUMENTATION.template.md` and its diagram files.
    -   To edit this contribution guide, modify the `CONTRIBUTING.md` file at the project root.
    -   The `pdm run build-docs` command (run by the pre-commit hook) will automatically generate the final `docs/DOCUMENTATION.md`, `docs/DOCUMENTATION.docx`, and `docs/CONTRIBUTING.docx`. **Do not edit generated files directly.**

### 3. Run the Test Suite

This project includes tests that must pass before a pull request will be merged. The pre-commit hooks do not run these tests automatically, so you must run them manually.

The test suite is divided into two parts, one for the Python source code and one for the PowerShell orchestration scripts.

*   **Python Tests (Pytest)**: These tests cover the core data processing, analysis, and utility functions in the `src/` directory.

    Use the PDM script shortcut:
    ````bash
    pdm run test
    ````

*   **PowerShell Tests**: Due to specific environmental challenges with traditional PowerShell testing frameworks (like Pester's advanced features), a custom, bare-bones testing harness is used for the orchestration scripts. This ensures maximum compatibility and reliability.

    -   To test the study analysis script (`analyze_study.ps1`):
        ````bash
        pdm run test-ps-stu
        ````
    -   To test the data migration script (`migrate_experiment.ps1`):
        ````bash
        pdm run test-ps-mig
        ````
    -   To test the main experiment runner (`run_experiment.ps1`):
        ````bash
        pdm run test-ps-exp
        ````

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

This approach, demonstrated in `tests/test_experiment_aggregator.py`, is the required standard for maintaining test quality and coverage across the project.

### 4. Commit Your Changes

This project uses **`commitizen`** to enforce the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. This ensures clear, automated versioning and changelog generation.

Instead of using `git commit -m "..."`, all commits should be made using the `commitizen` interactive prompt:
```bash
# Stage your changes first
git add .

# Then, run the commitizen command
pdm run cz commit
```
The prompt will guide you through selecting the type of change (`feat`, `fix`, `docs`, etc.), defining the scope, and writing a subject line and body.

### 5. Releasing a New Version (Maintainers Only)

Maintainers can automatically generate the changelog, bump the project version, and create a Git tag with a single command:
```bash
pdm run cz bump --changelog
```
This command reads all commits since the last tag and updates `pyproject.toml` and `docs/CHANGELOG.md` accordingly.

### 6. Submit a Pull Request

1.  Push your branch to your fork on GitHub.
2.  Open a pull request against the `main` branch of the original repository.
3.  Provide a clear title and a detailed description of your changes. If your PR addresses an existing issue, link to it in the description (e.g., "Closes #123").

## Reporting Bugs and Suggesting Enhancements

If you find a bug or have an idea for an improvement, please **open an issue** on GitHub.
*   For bugs, include a clear title, steps to reproduce, expected behavior, and any relevant logs.
*   For enhancements, describe the feature and why it would be valuable.

