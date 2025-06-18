# Contributing to the Project

We welcome contributions to this project! This document provides guidelines for getting your development environment set up and for contributing to the project.

## Getting Started: Project Setup for Beginners

This guide is for contributors who are new to setting up a standard Python development environment.

### 1. Essential Tools

Before you begin, ensure you have the following installed on your system:
*   **Python**: Version 3.8 or higher is recommended. You can download it from [python.org](https://www.python.org/downloads/).
*   **Visual Studio Code (VS Code)**: Our recommended code editor. You can download it from [code.visualstudio.com](https://code.visualstudio.com/).

### 2. Creating a Virtual Environment

A virtual environment is a self-contained directory that holds a specific Python interpreter and all the libraries required for a project. This prevents conflicts between different projects' dependencies.

1.  **Open a terminal** in the project's root directory.
2.  **Create the virtual environment**:
    ```bash
    python -m venv .venv
    ```
    This creates a folder named `.venv` in your project directory.

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

### 3. Understanding the Project Structure

A well-structured project is easier to navigate. Here's what the key files and directories are for:

*   `src/`: Contains all the Python source code for the pipeline.
    *   `src/__init__.py`: An empty file that tells Python to treat the `src` directory as a package, allowing for relative imports.
*   `data/`: Holds static data files, like the master list of personalities.
*   `output/`: The default directory where all generated files from experimental runs are saved.
*   `docs/`: Contains documentation artifacts, like Mermaid diagram source files.
*   `tests/`: Holds all unit and integration tests.
*   `.gitignore`: A list of files and directories (like `.venv` and `output/`) that Git should ignore and not commit to version control.
*   `.env`: A file for storing secrets like API keys. This file is listed in `.gitignore` and should **never** be committed.
*   `config.ini`: A configuration file for non-secret parameters, like model names, file paths, and default settings.
*   `README.md`: The main project overview (which is generated from `README.template.md`).
*   `requirements.txt`: A list of all Python packages the project depends on.

### 4. Installing Dependencies

Once your virtual environment is activated, you can install all the necessary packages.

1.  **Install from `requirements.txt`**: This command reads the file and installs the exact versions of all required libraries.
    ```bash
    pip install -r requirements.txt
    ```

2.  **Adding a new package**: If your contribution requires a new library, add it with `pip` and then update the `requirements.txt` file.
    ```bash
    # Install the new package
    pip install new-package-name

    # Update the requirements file with the new package list
    pip freeze > requirements.txt
    ```

## Running the Test Suite

This project includes a suite of unit and integration tests located in the `/tests` directory to ensure code quality and prevent regressions.

**All tests must pass before a pull request will be merged.**

The testing framework used is `pytest`, which is included in `requirements.txt`.

#### How to Run Tests

1.  Make sure your virtual environment is activated.
2.  From the project's **root directory**, run the following command:
    ```bash
    pytest -v
    ```
    The `-v` flag provides verbose output, showing the status of each individual test.

3.  If all tests pass, the output will end with a summary indicating success. If any tests fail, `pytest` will provide a detailed traceback to help you diagnose the issue.

## Documentation Workflow

This project uses a "docs-as-code" approach to keep the `README.md` and its diagrams in sync with the codebase. The `README.md` file is generated automatically and **should not be edited directly.**

Here is the workflow for updating any part of the documentation:

#### 1. To Edit the Main Text of the README

*   Modify the `README.template.md` file.

#### 2. To Edit the Code Architecture Diagram

*   Modify the Python script that generates the diagram: `src/generate_architecture_diagram.py`.
*   Run the script from the project root to regenerate the diagram artifact:
    ```bash
    python src/generate_architecture_diagram.py
    ```

#### 3. To Edit the Data Flow or Experimental Logic Diagrams

*   Manually edit the relevant source file in the `docs/diagrams/` folder:
    *   `docs/diagrams/architecture_data_flow.mmd`
    *   `docs/diagrams/architecture_experimental_logic.mmd`

#### 4. Final Build Step (After ANY of the above changes)

*   Run the build script to assemble all the pieces into the final `README.md`:
    ```bash
    python src/build_readme.py
    ```

## Reporting Bugs

If you find a bug, please open an issue and include the following:
*   A clear and descriptive title.
*   A description of the steps to reproduce the bug.
*   The expected behavior and what actually happened.
*   Any relevant logs or error messages.

## Suggesting Enhancements

If you have an idea for a new feature or an improvement, please open an issue to discuss it.