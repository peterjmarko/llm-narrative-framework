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
# Filename: src/id_encoder.py

"""
A utility module for encoding and decoding integer IDs using Base58.

This allows large integer IDs to be stored in short, human-friendly strings
that avoid visually ambiguous characters (0, O, I, l). This is useful for
passing identifiers through systems with field length limitations.

This module is not intended to be run directly but is imported by other scripts.
"""

# Base58 standard alphabet (avoids 0, O, I, l)
BASE58_CHARS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE = len(BASE58_CHARS)

def to_base58(num: int) -> str:
    """Encodes a positive integer into a Base58 string."""
    if not isinstance(num, int) or num < 0:
        raise ValueError("Input must be a non-negative integer.")
    if num == 0:
        return BASE58_CHARS[0]
    
    encoded_str = ""
    while num > 0:
        num, remainder = divmod(num, BASE)
        encoded_str = BASE58_CHARS[remainder] + encoded_str
    return encoded_str

def from_base58(encoded_str: str) -> int:
    """Decodes a Base58 string back into an integer."""
    num = 0
    for char in encoded_str:
        num = num * BASE + BASE58_CHARS.index(char)
    return num

# === End of src/id_encoder.py ===
