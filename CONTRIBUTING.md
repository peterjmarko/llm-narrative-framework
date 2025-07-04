# Contributing to the Project

We welcome contributions to this project! This document provides guidelines for setting up your development environment, adhering to project standards, and submitting your work.

## Getting Started: Development Environment Setup

This project uses **PDM** for dependency and environment management. It simplifies setup and guarantees reproducible environments.

### 1. Essential Tools

Before you begin, ensure you have the following installed on your system:
*   **Python**: Version 3.8 or higher is recommended. You can download it from [python.org](https://www.python.org/downloads/).
*   **Git**: For version control. You can download it from [git-scm.com](https://git-scm.com/downloads).
*   **PDM**: The Python dependency manager. Install it once with pip (if you haven't already):
    ```bash
    # It's best to run this from a terminal *outside* of any virtual environment.
    pip install --user pdm
    ```

### 2. Project Installation

With PDM installed, setting up the entire project environment is a single command. From the project's root directory, run:

```bash
pdm install -G dev
```
This command will automatically:
1.  Create a local virtual environment inside the project's `.venv` folder.
2.  Install all required packages from the `pdm.lock` file.
3.  Install all development packages (like `pytest` and `pre-commit`).
4.  Install the pre-commit hooks into your Git configuration.

To activate the virtual environment manually for use with your IDE, you can still use the standard command:
*   On Windows (PowerShell): `.venv\Scripts\Activate.ps1`
*   On macOS/Linux: `source .venv/bin/activate`

If your contribution requires a new library, please add its name directly to `requirements.txt` and then run `pip install -r requirements.txt`. Do not use `pip freeze`.

### 4. Set Up Pre-commit Hooks

This project uses `pre-commit` to automatically format code, check for style violations, and build the README file before each commit. This ensures all contributions meet our quality standards automatically.

1.  **Install the hooks**: After installing the requirements, run this one-time setup command from the project root:
    ```bash
    pre-commit install
    ```
2.  **That's it!** Now, every time you run `git commit`, the hooks will run automatically.

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

Write your code and update documentation as needed.

*   **Code**: Modify the Python files in `src/` or `tests/`. The pre-commit hooks will automatically handle formatting (Black) and linting (Flake8).
*   **Documentation**: To edit the main README, modify `README.template.md` or the diagram files in `docs/diagrams/`. The `build-readme` hook will automatically generate the final `README.md`. **Do not edit `README.md` directly.**

### 3. Run the Test Suite

The pre-commit hooks do not run the test suite automatically. You must still run the tests manually to ensure your changes haven't broken anything.

**All tests must pass before a pull request will be merged.**
```bash
pytest -v
```

### 4. Commit Your Changes

Use clear and descriptive commit messages. We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

**Important: The Two-Stage Commit Process**

Because our pre-commit hooks can modify files (like formatting code or rebuilding the README), you may sometimes need to commit twice. This is the expected and correct behavior.

1.  **First Attempt**: Run `git commit` as you normally would.
    ```bash
    git commit -m "feat(analysis): Add support for chi-squared test"
    ```
    If a hook modifies a file, the commit will be aborted with a message like "`files were modified by this hook`". This is a safety feature that gives you a chance to review the automatic changes.

2.  **Review and Re-commit**:
    *   Review the changes made by the hook (e.g., `git diff`).
    *   If the changes are correct, add them to the staging area:
        ```bash
        git add .
        ```
    *   Run the **exact same `git commit` command again**. This time, the hooks will find no issues and your commit will succeed.

*   **Format**: `type(scope): short description`
*   **Examples**:
    *   `feat(analysis): Add support for chi-squared test`
    *   `fix(parser): Handle empty response files gracefully`
    *   `docs(readme): Update contribution workflow`
    *   `test(orchestrator): Add test for reprocess mode`

### 6. Submit a Pull Request

1.  Push your branch to your fork on GitHub.
2.  Open a pull request against the `main` branch of the original repository.
3.  Provide a clear title and a detailed description of your changes. If your PR addresses an existing issue, link to it in the description (e.g., "Closes #123").

## Reporting Bugs and Suggesting Enhancements

If you find a bug or have an idea for an improvement, please **open an issue** on GitHub.
*   For bugs, include a clear title, steps to reproduce, expected behavior, and any relevant logs.
*   For enhancements, describe the feature and why it would be valuable.