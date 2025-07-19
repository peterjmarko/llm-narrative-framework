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

*   **Code**: Modify the Python files in `src/` or `tests/`. As you modify the code, you **must** update the corresponding docstrings to reflect any changes in logic, parameters, or behavior. Pre-commit hooks will handle formatting and linting.
*   **Data**: Edit the source file in the `data/` directory. Justify changes to this ground-truth data in your pull request.
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

This project uses **`commitizen`** to enforce the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. This ensures clear, automated versioning and changelog generation. All commits should be made using the following file-based workflow.

1.  **Update and Build Documentation (Pre-Commit)**
    Before staging any files, ensure all project documentation templates (`.template.md`, diagrams) are synchronized with your changes.

    a. **Build all documentation files**:
       This command generates the final `DOCUMENTATION.md` and other formats from their source templates.
       ```bash
       pdm run build-docs
       ```

    b. **Verify the status**:
       Check `git status` to ensure that all your code changes *and* the newly generated documentation files are ready to be committed. This is a critical sanity check.
       ```bash
       git status
       ```

2.  **Build All Documentation Files**
    Once all source materials are up-to-date, run the build command. This generates the final `DOCUMENTATION.md` and other formats from their templates.
    ```bash
    pdm run build-docs
    ```

3.  **Verify the Status**
    Check `git status` to ensure that all your code changes *and* the newly generated documentation files are present and ready to be committed.
    ```bash
    git status
    ```

4.  **Stage Your Changes**:
    Once you have verified that all intended files are present, stage everything for the commit.
    ```bash
    git add .
    ```

5.  **Create the Commit Message**:
    Create a temporary file named `commit.txt` in the project root. Write your full commit message inside, following the Conventional Commits format. This file is ignored by Git (via `.gitignore`).

    **Example `commit.txt`:**
    ```
    feat(analysis): add new statistical metric

    This commit introduces the F1 score as a new performance metric in the
    final analysis script. It is calculated for each replication and included
    in the final JSON report and summary CSVs.

    This provides a more nuanced view of model performance beyond MRR and Top-1 accuracy, especially for imbalanced results.
    ```

6.  **Run Pre-commit Hooks (Code Quality & Formatting)**:
    This is an important step, defined as the `lint` script in `pyproject.toml`. These hooks ensure code quality, formatting, and linting standards are met.
    ```bash
    pdm run lint
    ```
    *(Fix any issues reported by `pre-commit` and re-run `pdm run lint` until clean. You may need to `git add` fixed files).*

7.  **Create the Commit from the File**:
    Use the `-F` flag to create the commit from your prepared message file.
    ```bash
    git commit -F commit.txt
    ```

### 5. Releasing a New Version (Maintainers Only)

After one or more feature (`feat`) or fix (`fix`) commits have been merged into the `main` branch, a maintainer can create a new release.

This is a manual, two-step process that uses `commitizen` to automatically bump the version, generate a detailed changelog, and tag the release.

1.  **Ensure you are on the `main` branch and have pulled the latest changes.**
    ```bash
    git checkout main
    git pull origin main
    ```

2.  **Run the bump command.**
    `commitizen` determines the version bump based on the types of commits since the last release (`feat` for a minor bump, `fix` for a patch). Commits like `refactor` or `docs` will be added to the changelog but will not trigger a version bump.

    If a significant change was committed with the wrong type (e.g., a major bug fix was committed as `refactor`), you must first amend the commit message to ensure the version is bumped correctly.

    a. **(If Needed) Amend the commit type:**
       To change the type of the most recent commit, run:
       ```bash
       git commit --amend
       ```
       This command will open the last commit message in your default text editor. Simply change the commit type (e.g., from `refactor(...)` to `fix(...)`), then save the file and close the editor.

    b. **Run the bump command:**
       Once all commits are correctly typed, run the main release command:
       ```bash
       pdm run cz bump --changelog
       ```
       This command reads all commits since the last tag, determines the correct version increment, updates `pyproject.toml` and `CHANGELOG.md`, and creates a new release commit and tag.

3.  **(Manual Step) Update Changelog Details:**
    The `bump` command only adds the commit *header* to `CHANGELOG.md`. To include the full commit body for clarity, you must add it manually.

    a. View the last few commits using `git log -n 3` (or more). **Press 'q' to exit the log view.**
    b. Find and copy the full commit message (header and body) for the relevant `feat`, `fix`, or `refactor` commit(s) you want to document.
    c. Paste the message(s) into `CHANGELOG.md` under the appropriate version heading.
    d. Amend the release commit to include this documentation update:
       ```bash
       # Stage the changelog change
       git add CHANGELOG.md
       
       # Attach it to the last commit without changing the message
       git commit --amend --no-edit
       ```

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

After these steps, your repository is clean. You can now make any additional changes (like fixing the `changelog_file` path in `pyproject.toml`), stage them, and then run `pdm run cz bump --changelog` again.

### 6. Submit a Pull Request

1.  Push your branch to your fork on GitHub.
2.  Open a pull request against the `main` branch of the original repository.
3.  Provide a clear title and a detailed description of your changes. If your PR addresses an existing issue, link to it in the description (e.g., "Closes #123").

## Reporting Bugs and Suggesting Enhancements

If you find a bug or have an idea for an improvement, please **open an issue** on GitHub.
*   For bugs, include a clear title, steps to reproduce, expected behavior, and any relevant logs.
*   For enhancements, describe the feature and why it would be valuable.

