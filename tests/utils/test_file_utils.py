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
# Filename: tests/utils/test_file_utils.py

"""
Unit tests for src/utils/file_utils.py.
"""
import logging
import os
import shutil
from unittest.mock import patch

import pytest

from src.utils.file_utils import backup_and_remove


@patch('src.utils.file_utils.get_path')
def test_backup_and_remove_non_existent_path(mock_get_path, tmp_path):
    """Test that nothing happens if the target path doesn't exist."""
    non_existent_path = tmp_path / "non_existent.txt"
    backup_and_remove(non_existent_path)
    mock_get_path.assert_not_called()


@patch('src.utils.file_utils.get_path')
def test_backup_and_remove_file(mock_get_path, tmp_path, caplog, monkeypatch):
    """Test backing up and removing a single file."""
    caplog.set_level(logging.INFO)
    backup_dir = tmp_path / "backup"
    mock_get_path.return_value = backup_dir
    monkeypatch.setattr('src.utils.file_utils.PROJECT_ROOT', tmp_path)

    file_to_remove = tmp_path / "test_file.txt"
    file_to_remove.write_text("content")

    backup_and_remove(file_to_remove)

    assert not file_to_remove.exists()
    assert backup_dir.is_dir()
    backups = list(backup_dir.iterdir())
    assert len(backups) == 1
    backup_file = backups[0]
    assert backup_file.name.startswith("test_file.")
    assert backup_file.name.endswith(".txt.bak")
    assert backup_file.read_text() == "content"
    assert f"Backed up file 'test_file.txt' to 'backup{os.sep}{backup_file.name}'" in caplog.text


@patch('src.utils.file_utils.get_path')
def test_backup_and_remove_directory(mock_get_path, tmp_path, caplog, monkeypatch):
    """Test backing up and removing a directory."""
    caplog.set_level(logging.INFO)
    backup_dir = tmp_path / "backup"
    mock_get_path.return_value = backup_dir
    monkeypatch.setattr('src.utils.file_utils.PROJECT_ROOT', tmp_path)

    dir_to_remove = tmp_path / "test_dir"
    dir_to_remove.mkdir()
    (dir_to_remove / "child.txt").write_text("child_content")

    backup_and_remove(dir_to_remove)

    assert not dir_to_remove.exists()
    assert backup_dir.is_dir()
    backups = list(backup_dir.iterdir())
    assert len(backups) == 1
    backup_zip = backups[0]
    assert backup_zip.name.startswith("test_dir_")
    assert backup_zip.name.endswith(".zip")
    assert f"Backed up directory 'test_dir' to 'backup{os.sep}{backup_zip.name}'" in caplog.text

    unzip_dir = tmp_path / "unzipped"
    shutil.unpack_archive(backup_zip, unzip_dir)
    assert (unzip_dir / "child.txt").read_text() == "child_content"


@patch('src.utils.file_utils.shutil.rmtree')
@patch('src.utils.file_utils.get_path')
def test_backup_and_remove_handles_exception(mock_get_path, mock_rmtree, tmp_path, caplog):
    """Test that an exception during removal is caught, logged, and exits the program."""
    backup_dir = tmp_path / "backup"
    mock_get_path.return_value = backup_dir

    dir_to_remove = tmp_path / "test_dir"
    dir_to_remove.mkdir()

    error_message = "Permission denied"
    mock_rmtree.side_effect = OSError(error_message)

    with pytest.raises(SystemExit) as e:
        backup_and_remove(dir_to_remove)

    assert e.type == SystemExit
    assert e.value.code == 1
    assert f"Failed during backup/removal of test_dir: {error_message}" in caplog.text

# === End of tests/utils/test_file_utils.py ===
