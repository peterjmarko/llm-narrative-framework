#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_colors_class_exists(self):
        """Test that Colors class is properly defined."""
        assert hasattr(build_docs.Colors, 'RED')
        assert hasattr(build_docs.Colors, 'GREEN')
        assert hasattr(build_docs.Colors, 'RESET')

    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_render_mermaid_diagram_success(self, mock_exists, mock_subprocess):
        """Test successful Mermaid diagram rendering."""
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        source_path = os.path.join(self.test_dir, "test.mmd")
        output_path = os.path.join(self.test_dir, "test.png")
        
        result = build_docs.render_mermaid_diagram(source_path, output_path, self.test_dir)
        
        assert result is True
        mock_subprocess.assert_called_once()

    @patch('os.path.exists')
    def test_render_mermaid_diagram_mmdc_not_found(self, mock_exists):
        """Test Mermaid rendering when mmdc is not found."""
        mock_exists.return_value = False
        
        source_path = os.path.join(self.test_dir, "test.mmd")
        output_path = os.path.join(self.test_dir, "test.png")
        
        result = build_docs.render_mermaid_diagram(source_path, output_path, self.test_dir)
        
        assert result is False

    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_render_mermaid_diagram_subprocess_error(self, mock_exists, mock_subprocess):
        """Test Mermaid rendering with subprocess error."""
        mock_exists.return_value = True
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'mmdc', stderr="Error message")
        
        source_path = os.path.join(self.test_dir, "test.mmd")
        output_path = os.path.join(self.test_dir, "test.png")
        
        result = build_docs.render_mermaid_diagram(source_path, output_path, self.test_dir)
        
        assert result is False

    @patch('builtins.open', new_callable=mock_open, read_data="line1\nline2\nline3")
    def test_render_text_diagram_pillow_not_available(self, mock_file):
        """Test text diagram rendering when Pillow is not available."""
        with patch.dict('sys.modules', {'PIL': None, 'PIL.Image': None, 'PIL.ImageDraw': None, 'PIL.ImageFont': None}):
            with patch('importlib.import_module', side_effect=ImportError):
                source_path = os.path.join(self.test_dir, "test.txt")
                output_path = os.path.join(self.test_dir, "test.png")
                
                result = build_docs.render_text_diagram(source_path, output_path, self.test_dir)
                
                assert result is False

    def test_render_text_diagram_success(self):
        """Test successful text diagram rendering."""
        mock_image = MagicMock()
        mock_img = MagicMock()
        mock_image.new.return_value = mock_img
        
        mock_font = MagicMock()
        mock_font_obj = MagicMock()
        mock_font_obj.getbbox.return_value = (0, 0, 10, 15)
        mock_font.truetype.return_value = mock_font_obj
        
        with patch('builtins.open', mock_open(read_data="line1\nline2")):
            with patch.dict('sys.modules', {
                'PIL': MagicMock(),
                'PIL.Image': mock_image,
                'PIL.ImageDraw': MagicMock(),
                'PIL.ImageFont': mock_font
            }):
                result = build_docs.render_text_diagram(
                    os.path.join(self.test_dir, "test.txt"),
                    os.path.join(self.test_dir, "test.png"),
                    self.test_dir
                )

    @patch('builtins.open', new_callable=mock_open, read_data="")
    def test_render_text_diagram_empty_file(self, mock_file):
        """Test text diagram rendering with empty file."""
        with patch.dict('sys.modules', {'PIL': MagicMock()}):
            source_path = os.path.join(self.test_dir, "empty.txt")
            output_path = os.path.join(self.test_dir, "empty.png")
            
            result = build_docs.render_text_diagram(source_path, output_path, self.test_dir)
            
            assert result is False

    def test_build_readme_content_diagram_placeholder(self):
        """Test README content building with diagram placeholders."""
        template_content = "# Test\n{{diagram:test.mmd}}\nEnd"
        template_path = os.path.join(self.test_dir, "README.template.md")
        
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        result = build_docs.build_readme_content(self.test_dir)
        
        assert "![](docs/images/test.png)" in result
        assert "{{diagram:test.mmd}}" not in result

    def test_build_readme_content_diagram_with_attributes(self):
        """Test README content building with diagram attributes."""
        template_content = "{{diagram:test.mmd|scale=2.0|width=500}}"
        template_path = os.path.join(self.test_dir, "README.template.md")
        
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        result = build_docs.build_readme_content(self.test_dir)
        
        assert "![](docs/images/test.png){width=500}" in result
        assert "scale=2.0" not in result

    def test_build_readme_content_include_placeholder(self):
        """Test README content building with include placeholders."""
        # Create include file
        include_content = "This is included content"
        include_path = os.path.join(self.test_dir, "include.txt")
        with open(include_path, 'w') as f:
            f.write(include_content)
        
        # Create template
        template_content = "# Test\n{{include:include.txt}}\nEnd"
        template_path = os.path.join(self.test_dir, "README.template.md")
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        result = build_docs.build_readme_content(self.test_dir)
        
        assert include_content in result
        assert "{{include:include.txt}}" not in result

    def test_build_readme_content_missing_include(self):
        """Test README content building with missing include file."""
        template_content = "{{include:missing.txt}}"
        template_path = os.path.join(self.test_dir, "README.template.md")
        
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        result = build_docs.build_readme_content(self.test_dir)
        
        assert "ERROR: Included file not found" in result

    @patch('src.build_docs.render_mermaid_diagram')
    @patch('src.build_docs.render_text_diagram')
    @patch('os.makedirs')
    def test_render_all_diagrams_success(self, mock_makedirs, mock_render_text, mock_render_mermaid):
        """Test successful rendering of all diagrams."""
        # Setup template with diagrams
        template_content = "{{diagram:test.mmd}}\n{{diagram:text.txt}}"
        template_path = os.path.join(self.test_dir, "README.template.md")
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        mock_render_mermaid.return_value = True
        mock_render_text.return_value = True
        
        result = build_docs.render_all_diagrams(self.test_dir)
        
        assert result is True
        mock_render_mermaid.assert_called_once()
        mock_render_text.assert_called_once()

    @patch('src.build_docs.render_mermaid_diagram')
    def test_render_all_diagrams_failure(self, mock_render_mermaid):
        """Test diagram rendering with failures."""
        template_content = "{{diagram:test.mmd}}"
        template_path = os.path.join(self.test_dir, "README.template.md")
        with open(template_path, 'w') as f:
            f.write(template_content)
        
        mock_render_mermaid.return_value = False
        
        result = build_docs.render_all_diagrams(self.test_dir)
        
        assert result is False

    def test_convert_to_docx_success(self):
        """Test successful DOCX conversion."""
        mock_pypandoc = MagicMock()
        mock_pypandoc.convert_file.return_value = None
        
        source_path = os.path.join(self.test_dir, "test.md")
        output_path = os.path.join(self.test_dir, "test.docx")
        
        result = build_docs.convert_to_docx(mock_pypandoc, source_path, output_path, self.test_dir)
        
        assert result is True
        mock_pypandoc.convert_file.assert_called_once()

    def test_convert_to_docx_permission_error(self):
        """Test DOCX conversion with permission error."""
        mock_pypandoc = MagicMock()
        mock_pypandoc.convert_file.side_effect = RuntimeError("permission denied")
        
        source_path = os.path.join(self.test_dir, "test.md")
        output_path = os.path.join(self.test_dir, "test.docx")
        
        result = build_docs.convert_to_docx(mock_pypandoc, source_path, output_path, self.test_dir)
        
        assert result is False

    def test_convert_to_docx_file_not_found(self):
        """Test DOCX conversion when pandoc not found."""
        mock_pypandoc = MagicMock()
        mock_pypandoc.convert_file.side_effect = FileNotFoundError("pandoc not found")
        
        source_path = os.path.join(self.test_dir, "test.md")
        output_path = os.path.join(self.test_dir, "test.docx")
        
        result = build_docs.convert_to_docx(mock_pypandoc, source_path, output_path, self.test_dir)
        
        assert result is False

    def test_convert_to_docx_runtime_error(self):
        """Test DOCX conversion with unexpected runtime error."""
        mock_pypandoc = MagicMock()
        mock_pypandoc.convert_file.side_effect = RuntimeError("unexpected error")
        
        source_path = os.path.join(self.test_dir, "test.md")
        output_path = os.path.join(self.test_dir, "test.docx")
        
        with pytest.raises(RuntimeError):
            build_docs.convert_to_docx(mock_pypandoc, source_path, output_path, self.test_dir)

    @patch('src.build_docs.build_readme_content')
    @patch('builtins.open', new_callable=mock_open, read_data="current content")
    def test_main_check_mode_up_to_date(self, mock_file, mock_build):
        """Test main function in check mode when README is up-to-date."""
        mock_build.return_value = "current content"
        
        with patch.object(sys, 'argv', ['build_docs.py', '--check']):
            with patch('os.path.dirname', return_value=self.test_dir):
                with pytest.raises(SystemExit) as exc_info:
                    build_docs.main()
                
                assert exc_info.value.code == 0

    @patch('src.build_docs.build_readme_content')
    @patch('builtins.open', new_callable=mock_open, read_data="old content")
    def test_main_check_mode_out_of_date(self, mock_file, mock_build):
        """Test main function in check mode when README is out of date."""
        mock_build.return_value = "new content"
        
        with patch.object(sys, 'argv', ['build_docs.py', '--check']):
            with patch('os.path.dirname', return_value=self.test_dir):
                with pytest.raises(SystemExit) as exc_info:
                    build_docs.main()
                
                assert exc_info.value.code == 1

    @patch('src.build_docs.build_readme_content')
    def test_main_check_mode_missing_readme(self, mock_build):
        """Test main function in check mode when README doesn't exist."""
        mock_build.return_value = "content"
        
        with patch.object(sys, 'argv', ['build_docs.py', '--check']):
            with patch('os.path.dirname', return_value=self.test_dir):
                with patch('builtins.open', side_effect=FileNotFoundError):
                    with pytest.raises(SystemExit) as exc_info:
                        build_docs.main()
                    
                    assert exc_info.value.code == 1

    @patch('src.build_docs.render_all_diagrams')
    @patch('src.build_docs.build_readme_content')
    def test_main_build_mode_diagram_failure(self, mock_build, mock_render):
        """Test main function in build mode when diagram rendering fails."""
        mock_render.return_value = False
        mock_build.return_value = "content"

        with patch.object(sys, 'argv', ['build_docs.py']):
            with patch('os.path.dirname', return_value=self.test_dir):
                with pytest.raises(SystemExit) as exc_info:
                    build_docs.main()
                
                assert exc_info.value.code == 1

    @patch('src.build_docs.render_all_diagrams')
    @patch('src.build_docs.build_readme_content')
    @patch('src.build_docs.convert_to_docx')
    @patch('builtins.open', new_callable=mock_open)
    def test_main_build_mode_success_no_pypandoc(self, mock_file, mock_convert, mock_build, mock_render):
        """Test main function in build mode without pypandoc."""
        mock_render.return_value = True
        mock_build.return_value = "README content"
        
        with patch.object(sys, 'argv', ['build_docs.py']):
            with patch('os.path.dirname', return_value=self.test_dir):
                with patch.dict('sys.modules', {'pypandoc': None}):
                    with patch('importlib.import_module', side_effect=ImportError):
                        build_docs.main()  # Should complete without error

    @patch('src.build_docs.render_all_diagrams')
    @patch('src.build_docs.build_readme_content')
    @patch('src.build_docs.convert_to_docx')
    @patch('os.path.exists')
    def test_main_build_mode_success_with_pypandoc(self, mock_exists, mock_convert, mock_build, mock_render):

        """Test main function in build mode with pypandoc."""
        mock_render.return_value = True
        mock_build.return_value = "README content"
        mock_convert.return_value = True
        mock_exists.return_value = True  # CONTRIBUTING.md exists
        
        mock_pypandoc = MagicMock()
        
        with patch.object(sys, 'argv', ['build_docs.py']):
            with patch('os.path.dirname', return_value=self.test_dir):
                with patch.dict('sys.modules', {'pypandoc': mock_pypandoc}):
                    build_docs.main()
        
        # Should call convert_to_docx twice (README + CONTRIBUTING)
        assert mock_convert.call_count == 2

    @patch('src.build_docs.render_all_diagrams')
    @patch('src.build_docs.build_readme_content')
    @patch('src.build_docs.convert_to_docx')
    @patch('builtins.open', new_callable=mock_open)
    def test_main_build_mode_docx_conversion_failure(self, mock_file, mock_convert, mock_build, mock_render):
        """Test main function when DOCX conversion fails."""
        mock_render.return_value = True
        mock_build.return_value = "README content"
        mock_convert.return_value = False
        
        mock_pypandoc = MagicMock()
        
        with patch.object(sys, 'argv', ['build_docs.py']):
            with patch('os.path.dirname', return_value=self.test_dir):
                with patch.dict('sys.modules', {'pypandoc': mock_pypandoc}):
                    with pytest.raises(SystemExit) as exc_info:
                        build_docs.main()
                    
                    assert exc_info.value.code == 1

# === End of tests/test_build_docs.py ===