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
# Filename: src/config_loader.py

"""
Universal Configuration Loader (config_loader.py)

This module provides a robust, centralized system for loading configurations
for the entire project. It is designed to be imported by any script that needs
access to project-wide settings.

Key Features:
-   **Loads `config.ini`**: Parses the main configuration file into a global
    `APP_CONFIG` object, automatically finding it relative to the project root.
-   **Loads `.env`**: Securely loads environment variables (like API keys) from
    a `.env` file at the project root.
-   **Safe Value Retrieval**: The `get_config_value()` helper function provides
    type-safe access to config values, with support for fallbacks, type
    conversion (str, int, float, bool), and stripping of inline comments.
-   **Advanced Parsing**: Includes helpers for parsing comma-separated lists
    (`get_config_list`) and entire sections as dictionaries
    (`get_config_section_as_dict`).
-   **Backward Compatibility**: The `get_config_compatibility_map()` function
    can parse a `[ConfigCompatibility]` section in the config, allowing
    scripts to read legacy parameter names from older configuration files.

Global Objects Provided:
-   `PROJECT_ROOT`: An absolute path to the project's root directory.
-   `APP_CONFIG`: A `configparser.ConfigParser` instance holding all data from
    `config.ini`.
-   `ENV_LOADED`: A boolean indicating if a `.env` file was successfully loaded.

Usage by other scripts:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT

    # Get a typed value with a fallback
    num_trials = get_config_value(APP_CONFIG, 'Study', 'num_trials',
                                  value_type=int, fallback=100)

    # Get a list
    model_list = get_config_list(APP_CONFIG, 'Analysis', 'models_to_plot')

    # Build a path relative to the project root
    db_path = os.path.join(PROJECT_ROOT, 'data', 'personalities.db')
"""

import configparser
import os
import logging
import pathlib
from dotenv import load_dotenv # For .env loading

CONFIG_FILENAME = "config.ini"
DOTENV_FILENAME = ".env"

# Setup a basic logger for this module if not already configured by the calling script
# This ensures messages from here are visible even if calling script hasn't set up logging yet.
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO) # Default level for this module's direct logs

def get_project_root() -> str:
    """Determines the project root by searching upwards for pyproject.toml."""
    current_path = pathlib.Path(__file__).resolve()
    while current_path != current_path.parent:
        if (current_path / "pyproject.toml").exists():
            return str(current_path)
        current_path = current_path.parent
    raise FileNotFoundError("Could not find project root (containing pyproject.toml).")

PROJECT_ROOT = get_project_root()

def load_app_config():
    config = configparser.ConfigParser()
    
    # Check for an override path from an environment variable first.
    # This is used for sandboxed testing.
    override_path = os.getenv('PROJECT_CONFIG_OVERRIDE')
    if override_path and os.path.exists(override_path):
        config_path = override_path
        logger.debug(f"Using override config from env var: {config_path}")
    else:
        config_path = os.path.join(PROJECT_ROOT, CONFIG_FILENAME)

    if os.path.exists(config_path):
        try:
            # Explicitly specify 'utf-8-sig' to handle files with a BOM,
            # which can be created by PowerShell's Set-Content.
            config.read(config_path, encoding='utf-8-sig')
            logger.debug(f"Successfully loaded configuration from: {config_path}")
        except configparser.Error as e:
            logger.error(f"Error parsing configuration file {config_path}: {e}")
    else:
        logger.warning(f"{CONFIG_FILENAME} not found at project root: {config_path}. Using fallbacks.")
        
    return config

def load_env_vars():
    """Loads environment variables from .env file located at the project root."""
    dotenv_path = os.path.join(PROJECT_ROOT, DOTENV_FILENAME)
    if os.path.exists(dotenv_path):
        if load_dotenv(dotenv_path):
            logger.debug(f"Successfully loaded .env file from: {dotenv_path}")
            return True
        else:
            # This branch is for when .env exists but load_dotenv returns False (e.g., it's empty).
            logger.warning(f"Found .env file at {dotenv_path}, but it may be empty or failed to load.")
            return False
    else:
        logger.info(f".env file not found at {dotenv_path}. API keys/secrets must be set as environment variables.")
        return False

def get_config_compatibility_map(config):
    """
    Parses the [ConfigCompatibility] section of the config file.

    This section allows mapping a canonical parameter name to a list of
    potential (section, key) locations, providing a fallback mechanism for
    reading legacy configuration formats.

    Args:
        config (configparser.ConfigParser): The loaded config object.

    Returns:
        dict: A dictionary where keys are canonical parameter names and
              values are lists of (section, key) tuples to try in order.
              Returns an empty dict if the section doesn't exist.
    """
    compat_map = {}
    if not config.has_section('ConfigCompatibility'):
        return compat_map

    for canonical_name, locations_str in config.items('ConfigCompatibility'):
        locations_list = []
        # Split by comma to get individual 'section:key' pairs
        for loc_pair in locations_str.split(','):
            try:
                section, key = loc_pair.strip().split(':', 1)
                locations_list.append((section.strip(), key.strip()))
            except ValueError:
                # Handle potential malformed entries gracefully
                print(f"Warning: Malformed entry in [ConfigCompatibility] for '{canonical_name}': '{loc_pair}'")
                continue
        if locations_list:
            compat_map[canonical_name] = locations_list
            
    return compat_map

def get_config_value(config: configparser.ConfigParser, section: str, key: str, 
                     fallback=None, value_type=str, fallback_key=None):
    """
    Helper to get a typed value from a configparser.ConfigParser object,
    with a fallback, type conversion, and stripping of common inline comments.
    Tries the primary 'key' first, then the 'fallback_key' if provided.

    Args:
        config (configparser.ConfigParser): The loaded config object.
        section (str): The section name in the INI file.
        key (str): The primary key name in the section.
        fallback: The value to return if no key is found or conversion fails.
        value_type (type): The expected type (str, int, float, bool).
        fallback_key (str, optional): An alternative key to try if the primary key is not found.

    Returns:
        The configured value converted to value_type, or the fallback.
    """
    if not config.has_section(section):
        return fallback

    keys_to_try = [key]
    if fallback_key:
        keys_to_try.append(fallback_key)

    raw_value = None
    found_key = None
    for k in keys_to_try:
        if config.has_option(section, k):
            raw_value = config.get(section, k)
            found_key = k # Store the key that was actually found
            break # Found a valid key, exit the loop
    
    if raw_value is None:
        return fallback # Neither key was found

    if isinstance(raw_value, str):
        # Strip common inline comment characters (;#) and surrounding whitespace
        # This handles cases like "value # comment" or "value ; comment"
        cleaned_value = raw_value
        for comment_char in [';', '#']:
            if comment_char in cleaned_value:
                cleaned_value = cleaned_value.split(comment_char, 1)[0].strip()
        
        # After stripping comments, if the value is effectively empty,
        # it might be treated as if the key was present but had no value.
        # Depending on desired behavior, you might want to return fallback if cleaned_value is empty.
        # For now, an empty string after stripping comments is a valid empty string value.

        if value_type == str:
            if cleaned_value == '\\t': # Handle literal \t from ini for tab character
                return '\t'
            if cleaned_value.lower() == 'none': # Handle "None" string as Python None
                return None
            return cleaned_value # Return the cleaned string
        elif value_type == int:
            try:
                return int(cleaned_value)
            except ValueError:
                logger.warning(f"Config: Error converting [{section}]/{found_key} value '{raw_value}' "
                               f"(cleaned: '{cleaned_value}') to int. Using fallback: {fallback}")
                return fallback
        elif value_type == float:
            try:
                return float(cleaned_value)
            except ValueError:
                logger.warning(f"Config: Error converting [{section}]/{found_key} value '{raw_value}' "
                               f"(cleaned: '{cleaned_value}') to float. Using fallback: {fallback}")
                return fallback
        elif value_type == bool:
            # configparser's getboolean is quite flexible (True/False, yes/no, 1/0, on/off)
            try:
                # Use the key that was actually found (`found_key`) for getboolean.
                return config.getboolean(section, found_key)
            except ValueError: # getboolean raises ValueError if not a valid boolean string
                logger.warning(f"Config: Error converting [{section}]/{found_key} value '{raw_value}' "
                               f"to bool. Using fallback: {fallback}")
                return fallback
        else: # Should not happen if value_type is one of the above
            logger.error(f"Config: Unsupported value_type '{value_type.__name__}' for key '{key}'. Using fallback.")
            return fallback
            
    else: # Should always be a string from config.get, but as a safeguard
        logger.warning(f"Config: Value for [{section}]/{key} was not a string: '{raw_value}'. Using fallback.")
        return fallback

def get_config_list(config, section, key, fallback=None):
    """
    Retrieves a comma-separated string from the config and returns it as a list
    of cleaned strings.
    """
    value_str = get_config_value(config, section, key, fallback=None)
    if value_str is not None and value_str != '':
        return [item.strip() for item in value_str.split(',')]
    elif value_str == '':
        return []
    return fallback if fallback is not None else []

def get_config_section_as_dict(config, section):
    """
    Reads an entire section from the config and returns it as a dictionary.
    """
    if config.has_section(section):
        return dict(config.items(section))
    return {}

def get_path(relative_path: str) -> str:
    """
    Resolves a path relative to the sandbox or project root.

    Checks for a PROJECT_SANDBOX_PATH environment variable. If set, it treats
    that path as the root for all file operations. Otherwise, it defaults to
    the main PROJECT_ROOT. This enables fully isolated, sandboxed testing.

    Args:
        relative_path (str): The path relative to the project root
                             (e.g., 'data/sources/file.txt').

    Returns:
        str: The absolute path to the resource, resolved correctly for either
             a normal run or a sandboxed test run.
    """
    sandbox_path = os.getenv('PROJECT_SANDBOX_PATH')
    if sandbox_path:
        return os.path.join(sandbox_path, relative_path)
    return os.path.join(PROJECT_ROOT, relative_path)

def get_sandbox_path() -> str | None:
    """Returns the path to the current sandbox, or None if not in a sandbox."""
    return os.getenv('PROJECT_SANDBOX_PATH')

# Global config object, loaded once
APP_CONFIG = load_app_config()
ENV_LOADED = load_env_vars() # Load .env once globally as well

# === End of src/config_loader.py ===
