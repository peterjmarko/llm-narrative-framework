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

### Step 2: Clone and Set Up the Project

1.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

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
*   **Documentation**: To edit the main README, modify `README.template.md` and its diagram files. To edit this contribution guide, modify `CONTRIBUTING.md`. The `build-docs` hook will automatically generate the final `README.md`, `README.docx`, and `CONTRIBUTING.docx`. **Do not edit generated files directly.**

### 3. Run the Test Suite

This project includes tests that must pass before a pull request will be merged. The pre-commit hooks do not run these tests automatically, so you must run them manually.

The test suite covers both Python and PowerShell components. For PowerShell scripts, due to specific environmental challenges with traditional PowerShell testing frameworks (like Pester's advanced features), a custom, bare-bones testing approach is employed. This ensures maximum compatibility and reliability by directly executing test logic without relying on complex framework structures.

Use the PDM script shortcut:
```bash
python -m pdm run test
```

### 4. Commit Your Changes

Use clear and descriptive commit messages. We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. The general format is `type(scope): short description`.

*   **Examples**:
    *   `feat(analysis): Add support for chi-squared test`
    *   `fix(parser): Handle empty response files gracefully`
    *   `docs(readme): Update contribution workflow`
    *   `test(orchestrator): Add test for reprocess mode`

**Important: The Documentation Commit Workflow**

This project uses a `pre-commit` hook to ensure that the main `README.md` and all its diagrams are always up-to-date with their source files (e.g., `README.template.md`, diagram sources).

This hook **does not** automatically modify files during a commit. Instead, it **checks** if the documentation is current. If it's outdated, the commit will be aborted, and you must manually regenerate the documentation before you can successfully commit. Other hooks (like code formatters) may still modify files automatically.

Follow this workflow when your changes affect the documentation:

1.  **First Commit Attempt (Fails as Expected)**
    *   Make your changes to `README.template.md` or a diagram source file.
    *   Stage your changes: `git add .`
    *   Attempt to commit: `git commit -m "docs: Update architecture diagram"`
    *   The commit will be aborted with a message like:
        `ERROR: README.md is out of date. Please run 'pdm run build-docs' and commit the changes.`

2.  **Rebuild and Second Commit Attempt (Succeeds)**
    *   **Manually build the docs** by running the command from the error message:
        ```bash
        python -m pdm run build-docs
        ```
    *   **Stage the newly generated files** (`README.md`, diagrams in `docs/images/`, `*.docx`, etc.):
        ```bash
        git add .
        ```
    *   **Commit again** using the exact same message. This time, the hook will pass, and your commit will succeed.
        ```bash
        git commit -m "docs: Update architecture diagram"
        ```

### 5. Submit a Pull Request

1.  Push your branch to your fork on GitHub.
2.  Open a pull request against the `main` branch of the original repository.
3.  Provide a clear title and a detailed description of your changes. If your PR addresses an existing issue, link to it in the description (e.g., "Closes #123").

## Reporting Bugs and Suggesting Enhancements

If you find a bug or have an idea for an improvement, please **open an issue** on GitHub.
*   For bugs, include a clear title, steps to reproduce, expected behavior, and any relevant logs.
*   For enhancements, describe the feature and why it would be valuable.