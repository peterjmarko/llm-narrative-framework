# Contributing to the Project

We welcome contributions to this project! This document provides guidelines for setting up your development environment, adhering to project standards, and submitting your work.

## Getting Started: Development Environment Setup

This guide will walk you through setting up a standard Python development environment for this project.

### 1. Essential Tools

Before you begin, ensure you have the following installed on your system:
*   **Python**: Version 3.8 or higher is recommended. You can download it from [python.org](https://www.python.org/downloads/).
*   **Git**: For version control. You can download it from [git-scm.com](https://git-scm.com/downloads).
*   **Visual Studio Code (VS Code)**: Our recommended code editor. You can download it from [code.visualstudio.com](https://code.visualstudio.com/).

### 2. Creating a Virtual Environment

A virtual environment is a self-contained directory that holds a specific Python interpreter and all the libraries required for a project. This prevents conflicts between different projects' dependencies.

1.  **Open a terminal** in the project's root directory.
2.  **Create the virtual environment**:
    ```bash
    python -m venv .venv
    ```
    This creates a folder named `.venv` in your project directory, which is already ignored by Git.

3.  **Activate the virtual environment**: You must do this every time you open a new terminal to work on the project.
    *   On Windows (PowerShell):
        ```powershell
        .venv\Scripts\Activate.ps1
        ```
    *   On macOS/Linux:
        ```bash
        source .venv/bin/activate
        ```
    When activated, your terminal prompt will usually show `(.venv)` at the beginning.

### 3. Installing Dependencies

Once your virtual environment is activated, you can install all the necessary packages with a single command.

```bash
pip install -r requirements.txt
```

If your contribution requires a new library, please install it and then update the `requirements.txt` file:
```bash
# Install the new package
pip install new-package-name

# Update the requirements file with the new package list
pip freeze > requirements.txt```

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

Write your code, following the style guidelines below.

#### Code Style and Quality

To maintain a clean and consistent codebase, we adhere to the following standards.

*   **Code Formatting**: All Python code must be formatted with **Black**. Before committing, please run Black on any files you've changed:
    ```bash
    # Install black if you haven't already
    pip install black

    # Format all files in the src directory
    black src/ tests/
    ```
*   **Linting**: We use **Flake8** to check for logical errors and style violations according to PEP 8.
    ```bash
    # Install flake8 if you haven't already
    pip install flake8

    # Run the linter
    flake8 src/ tests/
    ```
*   **Docstrings**: All new functions, classes, and modules should have clear, well-written docstrings explaining their purpose, arguments, and return values.

### 3. Run the Test Suite

This project includes a suite of unit and integration tests located in the `/tests` directory.

**All tests must pass before a pull request will be merged.**

The testing framework used is `pytest`. To run the tests:
1.  Make sure your virtual environment is activated.
2.  From the project's **root directory**, run the following command:
    ```bash
    pytest -v
    ```

### 4. Update Documentation (If Necessary)

This project uses a "docs-as-code" approach. **Do not edit `README.md` directly.**

1.  **To Edit Text**: Modify `README.template.md`.
2.  **To Edit Diagrams**: Modify the relevant `.mmd` file in `docs/diagrams/`.
3.  **Build the Final README**: After making changes, run the build script to assemble the final `README.md`:
    ```bash
    python src/build_readme.py
    ```

### 5. Commit Your Changes

Use clear and descriptive commit messages. We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

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