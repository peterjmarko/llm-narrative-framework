#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/run_anova.py

"""
Performs a comprehensive statistical analysis on compiled experimental results.

This script automates the post-processing and statistical analysis of performance
metrics from a study's master CSV file. It identifies which experimental factors
have a statistically significant effect on various performance metrics.

Key Workflow Steps:
1.  **Archives Previous Results**: Safely moves existing contents of the `anova/`
    directory to an `anova/archive/` backup.
2.  **Loads Data**: Searches for and reads the master `STUDY_results.csv` file
    (or falls back to older names for compatibility).
3.  **Applies Display Names**: Uses the `[ModelDisplayNames]`, `[FactorDisplayNames]`,
    and `[MetricDisplayNames]` sections from `config.ini` to produce clean,
    human-readable plots and console output.
4.  **Filters Unreliable Models**: Excludes models that fall below a configurable
    `min_valid_response_threshold` from the analysis.
5.  **Performs Two-Way ANOVA**: For each performance metric, a two-way ANOVA is
    conducted to test for significant effects from the experimental factors.
    A Q-Q plot is generated to check the normality of residuals.
6.  **Conducts Post-Hoc Tests**: If ANOVA finds significant effects, a Tukey HSD
    test is performed to identify which specific factor levels differ.
7.  **Determines Performance Groups**: Summarizes Tukey HSD results into robust
    "Performance Groups" using a clique-finding algorithm.
8.  **Generates Visualizations**: Creates and saves boxplots for each factor and
    metric, annotated with the ANOVA p-value.

All output, including a detailed `STUDY_analysis_log.txt` and all generated
plots, is saved to the `anova/` directory within the specified study path.

Usage:
    python src/run_anova.py /path/to/top_level_results_dir/
"""

import argparse
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd
import os
import sys
import logging
import warnings
from textwrap import dedent

try:
    # Assumes this script is run from the project root or src is in the path
    from config_loader import APP_CONFIG, get_config_list, get_config_section_as_dict
except ImportError:
    # Fallback for running the script directly from src/
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_list, get_config_section_as_dict

try:
    # Use a non-interactive backend for saving plots to file
    import matplotlib
    matplotlib.use('Agg')
    import seaborn as sns
    import matplotlib.pyplot as plt
    import networkx as nx
    import pingouin as pg
except ImportError:
    logging.error("ERROR: Plotting libraries not found. Run: pip install seaborn matplotlib networkx pingouin")
    sys.exit(1)

import re

# Suppress the FutureWarning from seaborn/pandas
warnings.simplefilter(action='ignore', category=FutureWarning)


class ColorStrippingFormatter(logging.Formatter):
    """A logging formatter that strips ANSI color codes for file output."""
    ANSI_ESCAPE_CODE_RE = re.compile(r'\x1b\[[0-9;]*m')

    def format(self, record):
        # Let the parent formatter do the initial formatting
        formatted_message = super().format(record)
        # Strip ANSI codes from the final formatted message
        return self.ANSI_ESCAPE_CODE_RE.sub('', formatted_message)

def find_master_csv(search_dir):
    """Finds the most relevant summary CSV in a directory."""
    possible_files = [
        'STUDY_results.csv',          # New standard study-level file
        'final_summary_results.csv',  # Old study-level for backward compatibility
        'EXPERIMENT_results.csv'      # Experiment-level if no study file found
    ]
    for filename in possible_files:
        search_path = os.path.join(search_dir, filename)
        if os.path.exists(search_path):
            logging.info(f"Found summary file: {filename}")
            return search_path

    logging.error(f"ERROR: No summary CSV file found in {search_dir}.")
    logging.error(f"Looked for: {', '.join(possible_files)}")
    return None

def format_p_value(p_value):
    """Formats a p-value for display on plots."""
    if pd.isna(p_value): return "p = N/A"
    return "p < 0.001" if p_value < 0.001 else f"p = {p_value:.3f}"

def generate_performance_tiers(df, metric, posthoc_df, sanitized_to_display_map):
    """
    Generates performance groups from a post-hoc results DataFrame using a
    clique-finding algorithm. This avoids the issue of chaining non-significant
    results across disparate groups. A "clique" is a group where every model is
    not statistically different from every other model within that same group.
    """
    logging.info("\n--- Performance Groups (Models in the same group are not statistically different from each other) ---")
    G = nx.Graph()
    # Nodes are the friendly display names
    models_display = list(sanitized_to_display_map.values())
    G.add_nodes_from(models_display)
    
    for _, row in posthoc_df.iterrows():
        # Get the display names from the sanitized names in the post-hoc results
        group1_display = sanitized_to_display_map.get(row['group1'], row['group1'])
        group2_display = sanitized_to_display_map.get(row['group2'], row['group2'])

        # Only add edges for models that are actually in our current analysis set
        if group1_display in models_display and group2_display in models_display and not row['reject']:
            G.add_edge(group1_display, group2_display)
            
    # Find all maximal cliques. A clique is a fully connected subgraph.
    # This is a much better representation of performance tiers.
    cliques = list(nx.find_cliques(G))
    
    # Sort cliques by their median performance
    clique_medians = sorted(
        [(df[df['model_display'].isin(clique)][metric].median(), clique) for clique in cliques if clique], 
        key=lambda x: x[0], 
        reverse=True
    )
    
    if not clique_medians:
        logging.info("No distinct performance groups found (all models are significantly different from each other).")
        return

    group_data = [[f"Group {i+1}", f"{median_val:.4f}", ", ".join(sorted(list(clique_models)))] for i, (median_val, clique_models) in enumerate(clique_medians)]
    group_df = pd.DataFrame(group_data, columns=["Performance Group", "Median Score", "Models"])
    logging.info(f"\n{group_df.to_string(index=False)}")

def create_diagnostic_plot(model, display_metric_name, output_dir, metric_key):
    """Generates and saves a Q-Q plot into the 'diagnostics' subdirectory."""
    if hasattr(model, 'resid') and not model.resid.empty:
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        sm.qqplot(model.resid, line='s', ax=ax)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.set_title(f"Q-Q Plot of Residuals for '{display_metric_name}'")

        diagnostic_subdir = os.path.join(output_dir, 'diagnostics')
        plot_filename = f"qqplot_{metric_key}.png"
        full_plot_path = os.path.join(diagnostic_subdir, plot_filename)
        
        plt.savefig(full_plot_path)
        logging.info(f"-> Diagnostic plot saved successfully to: {full_plot_path}")
        plt.close(fig)
    else:
        logging.warning(f"-> Could not generate Q-Q plot for '{display_metric_name}': No residuals found.")


def create_and_save_plot(df, metric_key, display_metric_name, factor, p_value, output_dir, factor_display_map):
    """Creates and saves a boxplot into a factor-specific subdirectory."""
    fig = plt.figure(figsize=(12, 8))
    ax = plt.gca()
    
    # Use the friendly display names for the y-axis if plotting by model
    plot_factor = 'model_display' if factor == 'model' else factor
    
    order = df.groupby(plot_factor)[metric_key].median().sort_values(ascending=False).index
    sns.boxplot(ax=ax, y=plot_factor, x=metric_key, data=df, order=order, orient='h', palette="coolwarm")

    p_value_str = format_p_value(p_value)
    display_factor_name = factor_display_map.get(factor, factor.capitalize())
    title = f'Performance Comparison for: {display_metric_name}\n(Grouped by {display_factor_name}, ANOVA {p_value_str})'
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Metric: {display_metric_name}', fontsize=12)
    ax.set_ylabel(display_factor_name, fontsize=12)
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    
    # Save the plot into the correct subdirectory with a cleaner name
    boxplot_subdir = os.path.join(output_dir, 'boxplots', factor)
    plot_filename = f"{metric_key}_boxplot.png" # Use the key for a filesystem-safe name
    full_plot_path = os.path.join(boxplot_subdir, plot_filename)

    plt.savefig(full_plot_path)
    logging.info(f"-> Plot saved successfully to: {full_plot_path}")
    plt.close(fig)

def perform_analysis(df, metric_key, all_possible_factors, output_dir, sanitized_to_display_map, metric_display_map, factor_display_map):
    """Performs a full statistical analysis for a single metric."""
    display_metric_name = metric_display_map.get(metric_key, metric_key)
    
    logging.info("\n" + "="*80)
    logging.info(f" ANALYSIS FOR METRIC: '{display_metric_name}'")
    logging.info("="*80)

    if df[metric_key].var() == 0:
        logging.warning(f"WARNING: Metric '{display_metric_name}' has zero variance. Skipping all analysis.")
        return

    active_factors = [f for f in all_possible_factors if df[f].nunique() > 1]
    if not active_factors:
        logging.info("INFO: Only one experimental group found. No analysis possible.")
        if df[all_possible_factors[0]].nunique() == 1:
             create_and_save_plot(df, metric_key, display_metric_name, all_possible_factors[0], float('nan'), output_dir)
        return
    
    logging.info(f"Detected {len(active_factors)} active factor(s) with variation: {', '.join(active_factors)}")

    logging.info(f"\n--- Descriptive Statistics by {', '.join(active_factors)} ---")
    if 'n_valid_responses' in df.columns:
        desc_stats = df.groupby(active_factors).agg(
            Replications=('model', 'size'),
            N=('n_valid_responses', 'sum'),
            Mean=(metric_key, 'mean'),
            StdDev=(metric_key, 'std')
        ).rename(columns={'N': 'Total Trials (N)', 'StdDev': 'Std. Dev.'})
    else:
        desc_stats = df.groupby(active_factors)[metric_key].agg(['count', 'mean', 'std']).rename(columns={'count': 'Replications (N)'})
    logging.info(f"\n{desc_stats.to_string(float_format='%.4f')}")
    
    formula = f"Q('{metric_key}') ~ {' + '.join([f'C({f})' for f in active_factors])}"

    try:
        model = ols(formula, data=df).fit()
        create_diagnostic_plot(model, display_metric_name, output_dir, metric_key)
        anova_table = sm.stats.anova_lm(model, typ=2)

        # Add Eta-squared (η²) for effect size
        ss_total = anova_table['sum_sq'].sum()
        anova_table['eta_sq'] = anova_table['sum_sq'] / ss_total
        
        logging.info(f"\n--- ANOVA Summary for {display_metric_name} ---")
        logging.info(f"\n{anova_table.to_string(float_format='%.6f')}")
        
        significant_factors = [f.replace('C(', '').replace(')', '') for f in anova_table.index if anova_table.loc[f, 'PR(>F)'] < 0.05 and 'Residual' not in f]

        if significant_factors:
            logging.info(f"\nConclusion: Significant effect found for factor(s): {', '.join(significant_factors)}")
            logging.info("\n--- Post-Hoc Analysis ---")
            for factor in significant_factors:
                if df[factor].nunique() <= 2:
                    p_val_str = f"{anova_table.loc[f'C({factor})', 'PR(>F)']:.4f}"
                    logging.info(f"\nFactor '{factor}' has only two levels and is significant (ANOVA p={p_val_str}). No pairwise table needed.")
                    continue

                logging.info(f"\nComparing levels for factor: '{factor}'")
                posthoc_df = None
                
                try:
                    # Attempt Tukey HSD first, which assumes equal variance
                    logging.info("\nAttempting Tukey HSD...")
                    tukey_result = pairwise_tukeyhsd(endog=df[metric_key], groups=df[factor], alpha=0.05)
                    if pd.DataFrame(tukey_result._results_table.data).isnull().values.any():
                        raise ValueError("Tukey HSD result contains NaN values.")
                    
                    logging.info(f"\n{tukey_result}")
                    posthoc_df = pd.DataFrame(data=tukey_result._results_table.data[1:], columns=tukey_result._results_table.data[0])

                except (ValueError, ZeroDivisionError) as tukey_err:
                    logging.warning(f"  - Tukey HSD failed: {tukey_err}")
                    logging.info("  - Falling back to Games-Howell test (does not assume equal variance).")
                    
                    gh_result = pg.pairwise_gameshowell(data=df, dv=metric_key, between=factor)
                    logging.info(f"\n{gh_result.to_string()}")
                    
                    # Standardize Games-Howell output to match the format needed for tier generation
                    posthoc_df = gh_result[['A', 'B', 'pval']].copy()
                    posthoc_df.rename(columns={'A': 'group1', 'B': 'group2'}, inplace=True)
                    posthoc_df['reject'] = posthoc_df['pval'] < 0.05

                if factor == 'model' and posthoc_df is not None:
                    generate_performance_tiers(df, metric_key, posthoc_df, sanitized_to_display_map)

        else:
            logging.info("\nConclusion: No factors had a statistically significant effect on this metric.")
            
        logging.info("\n--- Generating Performance Plots ---")
        for factor in active_factors:
            key = f"C({factor})"
            p_val = anova_table.loc[key, 'PR(>F)'] if key in anova_table.index else float('nan')
            create_and_save_plot(df, metric_key, display_metric_name, factor, p_val, output_dir, factor_display_map)
            
    except Exception as e:
        logging.error(f"\nERROR: Could not perform ANOVA for metric '{display_metric_name}'. Reason: {e}")

def main():
    """Main entry point for the ANOVA analysis script."""
    parser = argparse.ArgumentParser(
        description="Perform ANOVA on experiment results.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=dedent("""
        Example Usage:
        --------------
        # To analyze a full study
        python src/run_anova.py path/to/your/study_folder/
        
        # To analyze a single experiment
        python src/run_anova.py path/to/your/experiment_folder/
        
        The script automatically finds the most relevant summary file 
        ('final_summary_results.csv' or 'EXPERIMENT_results.csv') in the
        specified directory and saves output to an 'anova/' subfolder.
        """)
    )
    parser.add_argument("input_path", help="Path to the top-level experiment directory containing the master CSV.")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.input_path)
    output_dir = os.path.join(base_dir, 'anova')
    os.makedirs(output_dir, exist_ok=True)

    # Note: BasicConfig can only be called once. We set it up here before any logging.
    log_filename = 'STUDY_analysis_log.txt'
    log_filepath = os.path.join(output_dir, log_filename)
    # Defer file handler creation until after archiving.
    temp_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(level=logging.INFO,
                        format='%(message)s',
                        handlers=[temp_handler])

    # --- Single-level Backup of Previous Run ---
    try:
        import shutil
        archive_dir = os.path.join(output_dir, 'archive')
        # List items in the anova/ directory, excluding the 'archive' subdir and the new log file
        items_to_archive = [item for item in os.listdir(output_dir) if item not in ['archive', log_filename]]
        
        if items_to_archive:
            logging.info(f"Archiving {len(items_to_archive)} file(s) from previous analysis run...")
            os.makedirs(archive_dir, exist_ok=True)
            for item_name in items_to_archive:
                source_path = os.path.join(output_dir, item_name)
                destination_path = os.path.join(archive_dir, item_name)
                
                # Overwrite existing item in archive to ensure a clean, single-level backup
                if os.path.exists(destination_path):
                    if os.path.isdir(destination_path):
                        shutil.rmtree(destination_path)
                    else:
                        os.remove(destination_path)
                
                shutil.move(source_path, destination_path)
            logging.info(f"Previous results moved to: {archive_dir}\n")
    except Exception as e:
        logging.warning(f"Could not archive previous results. Reason: {e}")
    # --- End of Backup ---

    # --- Create Output Subdirectories ---
    factors_from_config = get_config_list(APP_CONFIG, 'Schema', 'factors')
    if factors_from_config:
        boxplot_base_dir = os.path.join(output_dir, 'boxplots')
        os.makedirs(boxplot_base_dir, exist_ok=True)
        for factor in factors_from_config:
            os.makedirs(os.path.join(boxplot_base_dir, factor), exist_ok=True)
    
    os.makedirs(os.path.join(output_dir, 'diagnostics'), exist_ok=True)
    # --- End of Directory Creation ---

    # Now, set up the final logging configuration with two distinct handlers.
    root_logger = logging.getLogger()
    # Remove the temporary handler used for initial messages
    root_logger.removeHandler(temp_handler)

    # 1. Add a handler for the log file that uses the custom formatter to strip color codes.
    file_handler = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
    file_handler.setFormatter(ColorStrippingFormatter('%(message)s'))
    root_logger.addHandler(file_handler)

    # 2. Add a handler for the console that uses a standard formatter to preserve color codes.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(console_handler)

    master_csv_path = find_master_csv(base_dir)
    if not master_csv_path:
        sys.exit(1)
    
    logging.info(f"Full analysis log is being saved to: {log_filepath}")
    
    try:
        df = pd.read_csv(master_csv_path)
        logging.info(f"Successfully loaded {len(df)} rows from {master_csv_path}")
    except Exception as e:
        logging.error(f"FATAL: Could not load master CSV file. Error: {e}")
        return

    # --- Data Cleaning and Preparation ---
    if 'db' in df.columns:
        original_db_values = df['db'].unique()
        df['db'] = df['db'].replace('personalities_db_1-5000.jsonl', 'personalities_db_1-5000.txt')
        cleaned_db_values = df['db'].unique()
        if len(original_db_values) > len(cleaned_db_values):
            logging.info("Performed data cleaning on 'db' column to unify values.")
            logging.info(f" -> Original unique values: {original_db_values}")
            logging.info(f" -> Cleaned unique values:  {cleaned_db_values}\n")

    # --- Pre-analysis Filtering based on Valid Response Rate ---
    min_valid_responses = APP_CONFIG.getint('Analysis', 'min_valid_response_threshold', fallback=0)
    if 'n_valid_responses' in df.columns and min_valid_responses > 0:
        logging.info(f"Applying filter: Models with an average valid response rate < {min_valid_responses} will be excluded.")
        model_avg_responses = df.groupby('model')['n_valid_responses'].mean()
        models_to_exclude = model_avg_responses[model_avg_responses < min_valid_responses].index.tolist()
        
        if models_to_exclude:
            logging.info(f"Excluding {len(models_to_exclude)} model(s) due to low valid response rates: {', '.join(models_to_exclude)}")
            df = df[~df['model'].isin(models_to_exclude)]
            logging.info(f"Analysis will proceed with {len(df)} rows from {df['model'].nunique()} models.\n")
        else:
            logging.info("All models meet the minimum valid response rate.\n")

    normalization_map = get_config_section_as_dict(APP_CONFIG, 'ModelNormalization')
    display_name_map = get_config_section_as_dict(APP_CONFIG, 'ModelDisplayNames')
    metric_display_map = get_config_section_as_dict(APP_CONFIG, 'MetricDisplayNames')
    factor_display_map = get_config_section_as_dict(APP_CONFIG, 'FactorDisplayNames')
    factors = get_config_list(APP_CONFIG, 'Schema', 'factors')
    metrics = get_config_list(APP_CONFIG, 'Schema', 'metrics')

    if not all([normalization_map, display_name_map, factors, metrics, metric_display_map, factor_display_map]):
        logging.error("FATAL: Could not load required sections ('ModelNormalization', 'ModelDisplayNames', 'MetricDisplayNames', 'FactorDisplayNames', 'Schema') from config.ini.")
        return

    keyword_to_canonical_map = {kw.strip(): can for can, kws in normalization_map.items() for kw in kws.split(',')}

    if 'model' in df.columns:
        logging.info("Normalizing model names for consistency based on config...")
        df['model_canonical'] = df['model'].apply(lambda name: next((can for kw, can in keyword_to_canonical_map.items() if kw in str(name)), str(name)))
        df['model_display'] = df['model_canonical'].map(display_name_map).fillna(df['model_canonical'])
        df['model'] = df['model_canonical'].str.replace(r'[/.-]', '_', regex=True) # Sanitize for formula
        logging.info("Model name normalization and sanitization complete.\n")

        sanitized_to_display = df[['model', 'model_display']].drop_duplicates().set_index('model')['model_display'].to_dict()

    for factor in factors:
        if factor in df.columns:
            df[factor] = df[factor].astype(str)

    # Perform analysis for each metric
    for metric_key in metrics:
        if metric_key in df.columns:
            perform_analysis(df, metric_key, factors, output_dir, sanitized_to_display, metric_display_map, factor_display_map)
        else:
            logging.warning(f"\nWarning: Metric column '{metric_key}' not found. Skipping analysis.")

if __name__ == "__main__":
    main()


# === End of src/run_anova.py ===