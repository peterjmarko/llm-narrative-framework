# Filename: tests/conftest.py

import sys
import os

# Add the 'src' directory to the Python path
# This ensures that modules like 'run_batch', 'llm_prompter', etc.,
# can be imported directly from the 'src' directory by tests,
# allowing coverage.py to correctly track their execution.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
src_path = os.path.join(project_root, 'src')

if src_path not in sys.path:
    sys.path.insert(0, src_path)

# You can add common fixtures here if needed for multiple tests.
# For example:
# @pytest.fixture(scope="function")
# def temp_output_dir():
#     with tempfile.TemporaryDirectory() as tmpdir:
#         yield tmpdir