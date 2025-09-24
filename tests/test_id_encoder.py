#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: tests/test_id_encoder.py

"""
Unit tests for src/id_encoder.py.
"""
import pytest

from src.id_encoder import from_base58, to_base58

# Test cases: (integer, base58_string)
ENCODING_TEST_CASES = [
    (0, "1"),
    (57, "z"),
    (58, "21"),
    (255, "5Q"),
    (9999, "3yQ"),
    (123456789, "BukQL"),
]


@pytest.mark.parametrize("num, expected_str", ENCODING_TEST_CASES)
def test_to_base58_encoding(num, expected_str):
    """Test encoding of various integers to Base58."""
    assert to_base58(num) == expected_str


@pytest.mark.parametrize("expected_num, encoded_str", ENCODING_TEST_CASES)
def test_from_base58_decoding(expected_num, encoded_str):
    """Test decoding of various Base58 strings to integers."""
    assert from_base58(encoded_str) == expected_num


@pytest.mark.parametrize("invalid_input", [-1, -100, 1.5, "abc"])
def test_to_base58_invalid_input_raises_error(invalid_input):
    """Test that to_base58 raises ValueError for invalid inputs."""
    with pytest.raises(ValueError, match="Input must be a non-negative integer."):
        to_base58(invalid_input)


@pytest.mark.parametrize("invalid_char_str", ["0", "O", "I", "l", "21iY2e+"])
def test_from_base58_invalid_chars_raises_error(invalid_char_str):
    """Test that from_base58 raises ValueError for strings with invalid characters."""
    with pytest.raises(ValueError):
        from_base58(invalid_char_str)


@pytest.mark.parametrize("num", [0, 1, 58, 1000, 9876543210])
def test_round_trip_conversion(num):
    """Test that encoding and then decoding a number returns the original number."""
    encoded = to_base58(num)
    decoded = from_base58(encoded)
    assert decoded == num

# === End of tests/test_id_encoder.py ===
