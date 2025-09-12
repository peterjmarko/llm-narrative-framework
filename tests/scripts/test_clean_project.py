#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 Peter J. Marko
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: tests/scripts/test_clean_project.py

import unittest
from unittest.mock import patch, MagicMock
import pathlib
import sys
import os

# Add scripts directory to path to allow import
scripts_dir = str(pathlib.Path(__file__).resolve().parent.parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from clean_project import main as clean_main

class TestCleanProject(unittest.TestCase):

    def test_dry_run_discovery(self):
        """
        Tests that the script correctly identifies files for cleanup in a dry run.
        """
        # 1. Create a MagicMock to represent our fake project_root path
        mock_project_root = MagicMock(spec=pathlib.Path)
        
        # 2. Define the paths that our mock glob should "find"
        # These need to be MagicMocks themselves to have methods like `relative_to`
        mock_pycache = MagicMock(spec=pathlib.Path)
        mock_pycache.name = "__pycache__"
        mock_pycache.exists.return_value = True
        mock_pycache.is_dir.return_value = True
        mock_pycache.parents = [mock_project_root]
        mock_pycache.relative_to.return_value = pathlib.Path("__pycache__")
        
        mock_venv_pycache = MagicMock(spec=pathlib.Path)
        mock_venv_pycache.name = "__pycache__"
        mock_venv_pycache.exists.return_value = True
        mock_venv_pycache.is_dir.return_value = True
        mock_venv_pycache.parents = [mock_project_root / '.venv']
        mock_venv_pycache.relative_to.return_value = pathlib.Path(".venv/__pycache__")
        
        mock_htmlcov = MagicMock(spec=pathlib.Path)
        mock_htmlcov.name = "htmlcov"
        mock_htmlcov.exists.return_value = True
        mock_htmlcov.is_dir.return_value = True
        mock_htmlcov.parents = [mock_project_root]
        mock_htmlcov.relative_to.return_value = pathlib.Path("htmlcov")
        
        mock_temp_dir = MagicMock(spec=pathlib.Path)
        mock_temp_dir.name = "temp_test_environment"
        mock_temp_dir.exists.return_value = True
        mock_temp_dir.is_dir.return_value = True
        mock_temp_dir.parents = [mock_project_root]
        mock_temp_dir.relative_to.return_value = pathlib.Path("temp_test_environment")

        # 3. Configure the side effect for the glob method on our mock_project_root
        def glob_side_effect(pattern):
            if pattern == "**/__pycache__":
                return [mock_pycache, mock_venv_pycache]
            if pattern == "htmlcov":
                return [mock_htmlcov]
            if pattern == "temp_*":
                return [mock_temp_dir]
            return []
        
        mock_project_root.glob.side_effect = glob_side_effect

        # 4. Patch the now-global project_root variable in the script under test
        # Note: Use 'clean_project' not 'scripts.clean_project' since that's how it's imported
        with patch('clean_project.project_root', mock_project_root), \
            patch('clean_project.get_path_info', return_value=(1024, 1)), \
            patch('sys.argv', ['clean_project.py']), \
            patch('builtins.print') as mock_print:

            clean_main()

            # 5. Assertions
            output = "".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
            
            self.assertIn("__pycache__", output)
            self.assertIn("htmlcov", output)
            self.assertIn("temp_test_environment", output)
            
            # The key safety check: ensure the item inside .venv was excluded
            self.assertNotIn(".venv", output)

if __name__ == '__main__':
    unittest.main()

# === End of tests/scripts/test_clean_project.py ===
