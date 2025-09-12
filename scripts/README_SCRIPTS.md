# Utility Scripts

This directory contains utility scripts that support the project's development, maintenance, analysis, and build processes. They are organized into subdirectories based on their function.

## Directory Structure

-   [`analysis/`](analysis/): Contains one-off scripts for data analysis, diagnostics, and validation. These are typically used for deep dives into specific data artifacts or for exploring parameter sensitivity.

-   [`build/`](build/): Contains scripts related to the project's build and release process. This includes documentation generation, changelog management, and release finalization.

-   [`lint/`](lint/): Contains custom linters to enforce project-specific code quality and documentation standards, such as ensuring all scripts have correct headers and docstrings.

-   [`maintenance/`](maintenance/): Contains scripts for general project upkeep. This includes cleaning temporary files, generating scope reports, and managing the project workspace.

-   [`workflows/`](workflows/): Contains multi-step, ordered workflows that accomplish a specific, complex task.
    -   [`assembly_logic/`](workflows/assembly_logic/): A dedicated, five-step workflow to create and validate the "ground truth" dataset used for testing the core personality profile assembly algorithm. For a detailed guide, see the **[Assembly Logic Workflow README](workflows/assembly_logic/README_ASSEMBLY.md)**.