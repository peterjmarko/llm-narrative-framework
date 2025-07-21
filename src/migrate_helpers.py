import os
import json
import re
import configparser
import logging
from datetime import datetime

def reverse_engineer_parameters(legacy_exp_dir):
    """
    Inspects a legacy experiment directory to reverse-engineer its parameters
    and construct a valid experiment manifest dictionary.

    Returns:
        A dictionary for the manifest content, or None if parameters cannot be found.
    """
    logging.info(f"Attempting to reverse-engineer parameters from: {legacy_exp_dir}")
    run_dirs = sorted([d for d in os.listdir(legacy_exp_dir) if d.startswith('run_') and os.path.isdir(os.path.join(legacy_exp_dir, d))])
    
    if not run_dirs:
        logging.error("Migration failed: No 'run_*' directories found.")
        return None

    # Find the first run directory that has an archived config to use as the source of truth
    source_run_dir = None
    config_path = None
    for run_dir in run_dirs:
        path = os.path.join(legacy_exp_dir, run_dir, 'config.ini.archived')
        if os.path.exists(path):
            source_run_dir = run_dir
            config_path = path
            logging.info(f"Found a source of truth for parameters in: {source_run_dir}")
            break
            
    if not config_path:
        logging.error("Migration failed: Could not find any 'config.ini.archived' in any run directory.")
        return None

    # Parse parameters from the found config file
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(config_path)

    def get_robust(section_keys, key_keys, value_type=str, default=None):
        for section in section_keys:
            if config.has_section(section):
                for key in key_keys:
                    if config.has_option(section, key):
                        try:
                            if value_type == int: return config.getint(section, key)
                            if value_type == float: return config.getfloat(section, key)
                            return config.get(section, key)
                        except (ValueError, TypeError): continue
        return default

    parameters = {
        "model_name": get_robust(['LLM'], ['model_name', 'model'], default='unknown'),
        "temperature": get_robust(['LLM'], ['temperature'], value_type=float, default=0.0),
        "mapping_strategy": get_robust(['Study'], ['mapping_strategy'], default='unknown'),
        "group_size": get_robust(['Study'], ['group_size', 'k_per_query'], value_type=int, default=0),
        "num_trials": get_robust(['Study'], ['num_trials', 'num_iterations'], value_type=int, default=0),
        "num_replications": len(run_dirs) # Best guess is the number of folders found
    }

    # Assemble the full manifest
    manifest_data = {
        "parameters": parameters,
        "provenance": {
            "personalities_db_checksum": "unknown_migrated",
            "base_query_checksum": "unknown_migrated",
            "framework_version": "unknown_migrated"
        },
        "metadata": {
            "creation_timestamp": datetime.now().isoformat(),
            "user_notes": "Manifest generated via automated migration from a legacy experiment.",
            "invoked_command": ' '.join(sys.argv)
        }
    }
    
    return manifest_data