#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/config_loader.py

"""
Configuration Loader (config_loader.py)

Purpose:
This module is responsible for loading project-wide configurations. It defines:
1.  The project's root directory (`PROJECT_ROOT`).
2.  An application configuration object (`APP_CONFIG`) by parsing 'config.ini'.
3.  A helper function (`get_config_value`) to safely retrieve typed values from `APP_CONFIG`.
4.  Logic to load environment variables from a '.env' file (`ENV_LOADED`).

Configuration File ('config.ini'):
- Expected to be at the `PROJECT_ROOT`.
- Uses INI format with sections and key-value pairs.
- Supports inline comments starting with '#' or ';'.

Environment Variables File ('.env'):
- Expected to be at the `PROJECT_ROOT`.
- Used for sensitive information like API keys (e.g., OPENROUTER_API_KEY).
- Loaded using python-dotenv.

Usage by other scripts:
    from config_loader import APP_CONFIG, ENV_LOADED, get_config_value, PROJECT_ROOT

    # Example:
    # api_key = os.getenv("OPENROUTER_API_KEY")
    # default_k = get_config_value(APP_CONFIG, 'General', 'default_k', fallback=6, value_type=int)
    # data_file_path = os.path.join(PROJECT_ROOT, "data", "my_data.csv")

Key Components:
- `PROJECT_ROOT`: Dynamically determined absolute path to the project's root directory.
  Assumes `config_loader.py` is in a subdirectory (e.g., 'src/') of `PROJECT_ROOT`.
- `APP_CONFIG`: A `configparser.ConfigParser` instance holding data from 'config.ini'.
- `ENV_LOADED`: Boolean indicating if a '.env' file was successfully found and loaded.
- `get_config_value()`: Safely retrieves values, handles missing sections/keys,
  type conversion (str, int, float, bool), and inline comment stripping.
  Recognizes '\t' string in config as a tab character.
  Recognizes 'None' string in config as Python None for string types.

Error Handling:
- Logs warnings if 'config.ini' or '.env' are not found or if parsing errors occur,
  allowing scripts to proceed with fallbacks or default behaviors.
- `get_config_value` logs warnings for type conversion errors and uses fallbacks.
"""

# === Start of src/config_loader.py ===

import configparser
import os
import logging
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
    """Determines the project root directory (assumed to be parent of src/)."""
    # Assumes this file (config_loader.py) is in a directory like 'src/'
    # which is a direct child of the project root.
    current_file_path = os.path.abspath(__file__)
    src_dir = os.path.dirname(current_file_path)
    project_root = os.path.dirname(src_dir)
    return project_root

PROJECT_ROOT = get_project_root()

def load_app_config():
    config = configparser.ConfigParser()
    
    # For tests, CWD will be the temp test dir containing the mock config.
    # For normal runs, CWD might be project root, or script dir if src/ is CWD.
    # Simplest: prioritize CWD for config.ini, then try calculated project root.
    
    config_path_cwd = os.path.join(os.getcwd(), CONFIG_FILENAME)
    
    current_file_path = os.path.abspath(__file__)
    src_dir_of_loader = os.path.dirname(current_file_path)
    project_root_of_loader = os.path.dirname(src_dir_of_loader)
    config_path_project_root_default = os.path.join(project_root_of_loader, CONFIG_FILENAME)

    config_path_found = None
    if os.path.exists(config_path_cwd): # Check CWD first
        config_path_found = config_path_cwd
    elif os.path.exists(config_path_project_root_default): # Then default project structure
        config_path_found = config_path_project_root_default
    
    if config_path_found:
        config_path_found = os.path.abspath(config_path_found)
        try:
            config.read(config_path_found)
            logger.debug(f"Successfully loaded configuration from: {config_path_found}")
        except configparser.Error as e:
            logger.error(f"Error parsing configuration file {config_path_found}: {e}")
    else:
        logger.warning(f"{CONFIG_FILENAME} not found in CWD ({config_path_cwd}) or project root relative to loader ({config_path_project_root_default}). Using fallbacks.")
        
    return config

APP_CONFIG = load_app_config()

def load_env_vars():
    """Loads environment variables from .env file located at the project root."""
    dotenv_path = os.path.join(PROJECT_ROOT, DOTENV_FILENAME)
    if os.path.exists(dotenv_path):
        if load_dotenv(dotenv_path):
            logger.debug(f"Successfully loaded .env file from: {dotenv_path}")
            return True
        else:
            logger.warning(f"Found .env file at {dotenv_path}, but python-dotenv reported an issue loading it.")
            return False
    else:
        logger.info(f".env file not found at {dotenv_path}. API keys/secrets must be set as environment variables.")
        return False


def get_config_value(config: configparser.ConfigParser, section: str, key: str, 
                     fallback=None, value_type=str):
    """
    Helper to get a typed value from a configparser.ConfigParser object,
    with a fallback, type conversion, and stripping of common inline comments.

    Args:
        config (configparser.ConfigParser): The loaded config object.
        section (str): The section name in the INI file.
        key (str): The key name in the section.
        fallback: The value to return if the key is not found or conversion fails.
        value_type (type): The expected type (str, int, float, bool).

    Returns:
        The configured value converted to value_type, or the fallback.
    """
    if not config.has_section(section):
        # logger.debug(f"Config: Section [{section}] not found, using fallback for key '{key}': {fallback}")
        return fallback
    if not config.has_option(section, key):
        # logger.debug(f"Config: Key '{key}' not found in section [{section}], using fallback: {fallback}")
        return fallback
    
    raw_value = config.get(section, key) # Get the raw string value

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
                logger.warning(f"Config: Error converting [{section}]/{key} value '{raw_value}' "
                               f"(cleaned: '{cleaned_value}') to int. Using fallback: {fallback}")
                return fallback
        elif value_type == float:
            try:
                return float(cleaned_value)
            except ValueError:
                logger.warning(f"Config: Error converting [{section}]/{key} value '{raw_value}' "
                               f"(cleaned: '{cleaned_value}') to float. Using fallback: {fallback}")
                return fallback
        elif value_type == bool:
            # configparser's getboolean is quite flexible (True/False, yes/no, 1/0, on/off)
            # We can rely on it if we pass the original raw_value,
            # or implement similar logic for cleaned_value.
            # For simplicity using config.getboolean directly if type is bool:
            try:
                return config.getboolean(section, key) # Let configparser handle bool conversion
            except ValueError: # getboolean raises ValueError if not a valid boolean string
                logger.warning(f"Config: Error converting [{section}]/{key} value '{raw_value}' "
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
    if value_str:
        return [item.strip() for item in value_str.split(',')]
    return fallback if fallback is not None else []

# Global config object, loaded once
APP_CONFIG = load_app_config()
ENV_LOADED = load_env_vars() # Load .env once globally as well

# === End of src/config_loader.py ===

# Example of how scripts might use this:
# from config_loader import APP_CONFIG, ENV_LOADED, get_config_value, PROJECT_ROOT
# DEFAULT_K = get_config_value(APP_CONFIG, 'General', 'default_k', fallback=6, value_type=int)
# api_key = os.getenv("OPENROUTER_API_KEY")
# if ENV_LOADED and api_key:
#    logging.info("API key ready.")