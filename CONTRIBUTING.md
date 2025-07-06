# Contributing to the LLM Personality Matching Project

We welcome contributions to this project! This document provides guidelines for setting up your development environment, adhering to project standards, and submitting your work.

## Getting Started: Development Environment Setup

This project uses **PDM** for dependency and environment management. It simplifies setup and guarantees reproducible environments.

### 1. Essential Tools

Before you begin, ensure you have the following installed on your system:

*   **Python**: Version 3.8 or higher is recommended. You can download it from [python.org](https://www.python.org/downloads/).
*   **Git**: For version control. You can download it from [git-scm.com](https://git-scm.com/downloads).
*   **Node.js and npm**: Required by the documentation build script to automatically render Mermaid diagrams.
    *   Download the **LTS** version from [nodejs.org](https://nodejs.org/en/download/).
    *   During installation, ensure the default **"Add to PATH"** option is enabled. After installing, you may need to restart your computer or terminal for the `npm` command to be recognized.
*   **Project Dependencies**: Once Node.js is installed, navigate to the project root and install the required Node.js development tools:
    ```bash
    npm install
    ```
    This reads the `package.json` file and installs dependencies locally into a `node_modules` folder.
*   **Pandoc**: A universal document converter used to generate DOCX and other document formats. You can download it from [pandoc.org](https://pandoc.org/installing.html).
*   **PDM**: The Python dependency manager. Install it once with pip (if you haven't already):
    ```bash
    # It's best to run this from a terminal *outside* of any virtual environment.
    pip install --user pdm
    ```
    > **Note for Windows Users:** If you see a `pdm: The term 'pdm' is not recognized...` error in a new terminal, it means the install location is not in your system's PATH. The most reliable way to run PDM is to use `python -m pdm` instead of just `pdm`. All examples below will use this robust form.

### 2. Project Installation

With PDM installed, setting up the entire project environment is a single command. From the project's root directory, run:

```bash
python -m pdm install -G dev
```
This command will automatically:
1.  Create a local virtual environment inside the project's `.venv` folder.
2.  Install all required packages from the `pdm.lock` file.
3.  Install all development packages (like `pytest` and `pre-commit`).
4.  Install the pre-commit hooks into your Git configuration.

To activate the virtual environment manually for use with your IDE, you can still use the standard command:
*   On Windows (PowerShell): `.venv\Scripts\Activate.ps1`
*   On macOS/Linux: `source .venv/bin/activate`

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

Use the PDM script shortcut:
```bash
python -m pdm run test
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
    *   Run the **same `git commit` command again** with '--no-verify --no-edit' added:
        ```bash
        git commit --no-verify --no-edit -m "feat(analysis): Add support for chi-squared test"
        ```
        This time, the hooks will find no issues and your commit will succeed.

*   **Format**: `type(scope): short description`
*   **Examples**:
    *   `feat(analysis): Add support for chi-squared test`
    *   `fix(parser): Handle empty response files gracefully`
    *   `docs(readme): Update contribution workflow`
    *   `test(orchestrator): Add test for reprocess mode`

### 5. Submit a Pull Request

1.  Push your branch to your fork on GitHub.
2.  Open a pull request against the `main` branch of the original repository.
3.  Provide a clear title and a detailed description of your changes. If your PR addresses an existing issue, link to it in the description (e.g., "Closes #123").

## Reporting Bugs and Suggesting Enhancements

If you find a bug or have an idea for an improvement, please **open an issue** on GitHub.
*   For bugs, include a clear title, steps to reproduce, expected behavior, and any relevant logs.
*   For enhancements, describe the feature and why it would be valuable.