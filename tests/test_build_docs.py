#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
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
# Filename: tests/test_build_docs.py

import pytest
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
import subprocess

from src import build_docs

class TestBuildDocs:
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.docs_dir = os.path.join(self.test_dir, "docs")
        os.makedirs(self.docs_dir, exist_ok=True)
        self.template_path = os.path.join(self.docs_dir, "DOCUMENTATION.template.md")

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_build_readme_content_diagram_placeholder(self):
        """Test README content building with diagram placeholders (default HTML flavor)."""
        template_content = "# Test\n{{diagram:test.mmd}}\nEnd"
        with open(self.template_path, 'w') as f:
            f.write(template_content)
        
        result = build_docs.build_readme_content(self.test_dir)
        
        assert '<img src="images/test.png"' in result

    def test_build_readme_content_diagram_with_attributes(self):
        """Test README content building with diagram attributes (default HTML flavor)."""
        template_content = "{{diagram:test.mmd|scale=2.0|width=500}}"
        with open(self.template_path, 'w') as f:
            f.write(template_content)

        result = build_docs.build_readme_content(self.test_dir)

        assert '<img src="images/test.png" width="500">' in result
    
    def test_build_readme_content_pandoc_flavor(self):
        """Test README content building for the 'pandoc' flavor."""
        template_content = "{{diagram:test.mmd|width=80%}}"
        with open(self.template_path, 'w') as f:
            f.write(template_content)

        result = build_docs.build_readme_content(self.test_dir, flavor='pandoc')
        assert '![](images/test.png){width="80%"}' in result

    def test_build_readme_content_include_placeholder(self):
        """Test README content building with include placeholders."""
        include_content = "This is included content"
        include_path = os.path.join(self.test_dir, "include.txt")
        with open(include_path, 'w') as f:
            f.write(include_content)
        
        template_content = "# Test\n{{include:include.txt}}\nEnd"
        with open(self.template_path, 'w') as f:
            f.write(template_content)
        
        result = build_docs.build_readme_content(self.test_dir)
        
        assert include_content in result
        assert "{{include:include.txt}}" not in result

    @patch('src.build_docs.render_mermaid_diagram')
    def test_render_all_diagrams_failure(self, mock_render_mermaid):
        """Test diagram rendering with failures."""
        template_content = "{{diagram:test.mmd}}"
        with open(self.template_path, 'w') as f:
            f.write(template_content)
        
        mock_render_mermaid.return_value = False
        
        result = build_docs.render_all_diagrams(self.test_dir)
        
        assert result is False

    @patch('src.build_docs.time.sleep', return_value=None) # Patch sleep to speed up test
    def test_convert_to_docx_permission_error_then_success(self, mock_sleep):
        """Test DOCX conversion with recoverable permission error."""
        mock_pypandoc = MagicMock()
        # Fail twice with permission error, then succeed
        mock_pypandoc.convert_file.side_effect = [
            RuntimeError("permission denied"),
            RuntimeError("permission denied"),
            None  # Success on the third try
        ]
        
        source_path = os.path.join(self.test_dir, "test.md")
        output_path = os.path.join(self.test_dir, "test.docx")
        
        result = build_docs.convert_to_docx(mock_pypandoc, output_path, self.test_dir, source_md_path=source_path)
        
        assert result is True
        assert mock_pypandoc.convert_file.call_count == 3

    @patch('src.build_docs.check_diagrams_are_up_to_date', return_value=True)
    @patch('src.build_docs.build_readme_content', return_value="current content")
    @patch('builtins.open', new_callable=mock_open, read_data="current content")
    def test_main_check_mode_up_to_date(self, mock_file, mock_build, mock_check_diagrams):
        """Test main function in check mode when everything is up-to-date."""
        cli_args = ['build_docs.py', '--check']
        with patch.object(sys, 'argv', cli_args), \
             pytest.raises(SystemExit) as exc_info:
            build_docs.main()
        
        assert exc_info.value.code == 0

    @patch('src.build_docs.check_diagrams_are_up_to_date', return_value=False)
    @patch('src.build_docs.build_readme_content', return_value="content")
    def test_main_check_mode_outdated_diagrams(self, mock_build, mock_check_diagrams):
        """Test main function in check mode when diagrams are out of date."""
        cli_args = ['build_docs.py', '--check']
        with patch.object(sys, 'argv', cli_args), \
             patch('builtins.open', new_callable=mock_open, read_data="content"), \
             pytest.raises(SystemExit) as exc_info:
            build_docs.main()
            
        assert exc_info.value.code == 1

    @patch('src.build_docs.render_all_diagrams', return_value=False)
    def test_main_build_mode_diagram_failure(self, mock_render):
        """Test main function in build mode when diagram rendering fails."""
        cli_args = ['build_docs.py']
        with patch.object(sys, 'argv', cli_args), \
             pytest.raises(SystemExit) as exc_info:
            build_docs.main()
        
        assert exc_info.value.code == 1

    @patch('src.build_docs.render_all_diagrams', return_value=True)
    @patch('src.build_docs.build_readme_content', return_value="content")
    @patch('os.path.exists', return_value=True) # Mock os.path.exists for CONTRIBUTING.md
    def test_main_build_mode_success_with_pypandoc(self, mock_exists, mock_build, mock_render):
        """Test main function in build mode with pypandoc."""
        mock_pypandoc = MagicMock()
        # Mock the convert functions directly to avoid file I/O issues in test
        mock_pypandoc.convert_text.return_value = None
        mock_pypandoc.convert_file.return_value = None

        cli_args = ['build_docs.py']
        with patch.object(sys, 'argv', cli_args), \
             patch.dict(sys.modules, {'pypandoc': mock_pypandoc}):
            
            with patch('src.build_docs.convert_to_docx', wraps=build_docs.convert_to_docx) as wrapped_convert:
                build_docs.main()
                # Should call convert_to_docx twice (README + CONTRIBUTING)
                assert wrapped_convert.call_count == 2

    def test_render_text_diagram(self):
        """Test rendering of a text-based diagram."""
        source_path = os.path.join(self.test_dir, "test.txt")
        output_path = os.path.join(self.test_dir, "test.png")
        with open(source_path, 'w') as f:
            f.write("Hello\nWorld")

        # Mock Pillow to avoid actual image processing
        mock_font_obj = MagicMock()
        mock_font_obj.getbbox.return_value = (0, 0, 10, 15)

        def truetype_side_effect(font_path, size, **kwargs):
            # Fail for the fonts in the list, succeed for the default
            if font_path != "courB.pil":
                raise IOError("Font not found")
            return mock_font_obj

        with patch('PIL.Image.new'), \
             patch('PIL.ImageDraw.Draw'), \
             patch('PIL.ImageFont.truetype', side_effect=truetype_side_effect), \
             patch('PIL.ImageFont.load_default', return_value=mock_font_obj):
            
            result = build_docs.render_text_diagram(source_path, output_path, self.test_dir)
            assert result is True

    @patch('os.path.getmtime')
    @patch('src.build_docs.render_mermaid_diagram')
    def test_render_all_diagrams_caching(self, mock_render, mock_getmtime):
        """Test that up-to-date diagrams are skipped."""
        template_content = "{{diagram:docs/test.mmd}}"
        with open(self.template_path, 'w') as f:
            f.write(template_content)

        # Simulate image being NEWER than source
        mock_getmtime.side_effect = [100, 200] # source_mtime, image_mtime
        
        # Create a dummy image file to satisfy os.path.exists
        os.makedirs(os.path.join(self.docs_dir, 'images'))
        with open(os.path.join(self.docs_dir, 'images', 'test.png'), 'w') as f:
            f.write('dummy')

        build_docs.render_all_diagrams(self.test_dir, force_render=False)
        mock_render.assert_not_called()

    @patch('os.path.getmtime')
    @patch('src.build_docs.render_mermaid_diagram')
    def test_render_all_diagrams_force_render(self, mock_render, mock_getmtime):
        """Test that force_render overrides the cache."""
        template_content = "{{diagram:docs/test.mmd}}"
        with open(self.template_path, 'w') as f:
            f.write(template_content)
        
        mock_getmtime.side_effect = [100, 200]
        os.makedirs(os.path.join(self.docs_dir, 'images'))
        with open(os.path.join(self.docs_dir, 'images', 'test.png'), 'w') as f:
            f.write('dummy')

        build_docs.render_all_diagrams(self.test_dir, force_render=True)
        mock_render.assert_called_once()

    def test_check_diagrams_outdated(self):
        """Test check mode detects outdated diagrams."""
        template_content = "{{diagram:docs/test.mmd}}"
        with open(self.template_path, 'w') as f:
            f.write(template_content)

        # Simulate image being OLDER than source
        with patch('os.path.getmtime', side_effect=[200, 100]):
            os.makedirs(os.path.join(self.docs_dir, 'images'))
            with open(os.path.join(self.docs_dir, 'images', 'test.png'), 'w') as f:
                f.write('dummy')
            
            result = build_docs.check_diagrams_are_up_to_date(self.test_dir)
            assert result is False

    @patch('src.build_docs.render_all_diagrams', return_value=True)
    @patch('src.build_docs.build_readme_content', return_value="content")
    @patch('os.path.exists', return_value=False) # Mock CONTRIBUTING.md as MISSING
    def test_main_build_mode_no_contributing_md(self, mock_exists, mock_build, mock_render):
        """Test build mode when CONTRIBUTING.md does not exist."""
        mock_pypandoc = MagicMock()
        mock_pypandoc.convert_text.return_value = None
        
        cli_args = ['build_docs.py']
        with patch.object(sys, 'argv', cli_args), \
             patch.dict(sys.modules, {'pypandoc': mock_pypandoc}):
            
            with patch('src.build_docs.convert_to_docx', wraps=build_docs.convert_to_docx) as wrapped_convert:
                build_docs.main()
                # Should only be called once for DOCUMENTATION.md
                assert wrapped_convert.call_count == 1

# === End of tests/test_build_docs.py ===
