#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/run_anova.py

"""
Performs a two-way Analysis of Variance (ANOVA) on compiled experimental results.

This script automates the statistical analysis of performance metrics from a master
CSV file. It is designed to identify which experimental factors (e.g., model, 
mapping strategy) have a statistically significant effect on various performance
metrics.

Key Workflow Steps:
1.  Loads data from a master CSV file specified via command-line arguments.
2.  Performs a critical data cleaning step to unify known data integrity issues
    (e.g., different names for the same database file).
3.  Normalizes model names for consistent display using a provided config file.
4.  For each specified performance metric, it conducts a two-way ANOVA.
5.  Generates a Q-Q plot to diagnose the normality of residuals, a key
    assumption for ANOVA.
6.  If the ANOVA reveals significant effects, it performs a post-hoc Tukey HSD
    (Honestly Significant Difference) test to determine which specific groups
    (e.g., which models) are different from each other.
7.  Summarizes the post-hoc results into clear "Performance Tiers".
8.  Generates and saves boxplots visualizing the performance of each factor on
    the metric, annotated with the corresponding ANOVA p-value.

All output, including a detailed analysis log and all generated plots, is saved
to a specified output directory.

Usage:
    python src/run_anova.py --input /path/to/results.csv --output /path/to/report_dir --config /path/to/config.ini
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

try:
    from config_loader import APP_CONFIG, get_config_list, get_config_section_as_dict
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_list

try:
    import matplotlib
    matplotlib.use('Agg')
    import seaborn as sns
    import matplotlib.pyplot as plt
    import networkx as nx
except ImportError:
    logging.error("ERROR: Plotting libraries not found. Run: pip install seaborn matplotlib networkx")
    sys.exit(1)

warnings.simplefilter(action='ignore', category=FutureWarning)

def find_master_csv(search_dir):
    """Finds the top-level summary CSV in a directory."""
    search_path = os.path.join(search_dir, 'final_summary_results.csv')
    if os.path.exists(search_path):
        return search_path
    logging.error(f"ERROR: No 'final_summary_results.csv' found directly in {search_dir}.")
    return None

def format_p_value(p_value):
    if pd.isna(p_value): return "p = nan"
    return "p < 0.001" if p_value < 0.001 else f"p = {p_value:.3f}"

def generate_performance_tiers(df, metric, tukey_result, display_name_map):
    logging.info("\n--- Performance Tiers (Models in the same tier are not statistically different) ---")
    G = nx.Graph()
    # Use the friendly display names for the graph nodes
    models = df['model_display'].unique()
    G.add_nodes_from(models)
    
    tukey_df = pd.DataFrame(data=tukey_result._results_table.data[1:], columns=tukey_result._results_table.data[0])
    
    for _, row in tukey_df.iterrows():
        # Tukey results use sanitized internal names; map them back to display names
        group1_display = display_name_map.get(row['group1'].replace('_', '-'), row['group1'])
        group2_display = display_name_map.get(row['group2'].replace('_', '-'), row['group2'])
        if not row['reject']:
            G.add_edge(group1_display, group2_display)
            
    tiers = list(nx.connected_components(G))
    tier_medians = sorted([(df[df['model_display'].isin(tier)][metric].median(), tier) for tier in tiers], key=lambda x: x[0], reverse=True)
    
    tier_data = [[f"Tier {i+1}", f"{median_val:.4f}", ", ".join(sorted(list(tier_models)))] for i, (median_val, tier_models) in enumerate(tier_medians)]
    tier_df = pd.DataFrame(tier_data, columns=["Performance Tier", "Median Score", "Models"])
    logging.info(f"\n{tier_df.to_string(index=False)}")

def create_diagnostic_plot(model, metric, output_dir):
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    sm.qqplot(model.resid, line='s', ax=ax)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_title(f"Q-Q Plot of Residuals for '{metric}'")
    plot_filename = f"diagnostic_qqplot_{metric}.png"
    full_plot_path = os.path.join(output_dir, plot_filename)
    plt.savefig(full_plot_path)
    logging.info(f"-> Diagnostic plot saved successfully to: {full_plot_path}")
    plt.close(fig)

def create_and_save_plot(df, metric, factor, p_value, output_dir):
    fig = plt.figure(figsize=(12, 8))
    ax = plt.gca()
    
    # If we are plotting by model, use the friendly display names instead
    plot_factor = 'model_display' if factor == 'model' else factor
    
    order = df.groupby(plot_factor)[metric].median().sort_values(ascending=False).index
    sns.boxplot(ax=ax, y=plot_factor, x=metric, data=df, order=order, orient='h', palette="coolwarm")

    p_value_str = format_p_value(p_value)
    # Use the original factor name for the title for consistency
    title = f'Performance Comparison for: {metric}\n(Grouped by {factor}, ANOVA {p_value_str})'
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Metric: {metric}', fontsize=12)
    # Label the axis with the friendly name 'Model' or the original factor name
    ylabel = 'Model' if factor == 'model' else factor
    ax.set_ylabel(ylabel, fontsize=12)
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plot_filename = f"{metric}_by_{factor}_boxplot.png"
    full_plot_path = os.path.join(output_dir, plot_filename)
    plt.savefig(full_plot_path)
    logging.info(f"-> Plot saved successfully to: {full_plot_path}")
    plt.close(fig)

def perform_analysis(df, metric, all_possible_factors, output_dir, display_name_map):
    """
    Performs a full statistical analysis for a single metric.

    This function orchestrates the entire analysis pipeline for a given
    performance metric, including:
    - Printing descriptive statistics.
    - Running a two-way ANOVA.
    - Generating and saving a Q-Q diagnostic plot.
    - If significant factors are found, running and reporting on a
      post-hoc Tukey HSD test and creating performance tiers.
    - Calling the plotting function to generate summary boxplots.

    Args:
        df (pd.DataFrame): The DataFrame containing the complete, cleaned data.
        metric (str): The name of the column to be treated as the dependent variable.
        active_factors (list): A list of column names to be used as independent variables.
        output_dir (str): The path to the directory where plots and logs are saved.
    
    Side Effects:
        - Prints all statistical results to standard output.
        - Saves a Q-Q plot (`diagnostic_qqplot_{metric}.png`) to the output directory.
        - Saves performance boxplots for each factor to the output directory.
    """
    logging.info("\n" + "="*80)
    logging.info(f" ANALYSIS FOR METRIC: '{metric}'")
    logging.info("="*80)

    if df[metric].var() == 0:
        logging.warning(f"WARNING: Metric '{metric}' has zero variance. Skipping all analysis for this metric.")
        return

    active_factors = [f for f in all_possible_factors if df[f].nunique() > 1]
    if not active_factors:
        logging.info("INFO: Only one experimental group found. No analysis possible.")
        return
    logging.info(f"Detected {len(active_factors)} active factor(s) with variation: {', '.join(active_factors)}")

    logging.info(f"\n--- Descriptive Statistics by {', '.join(active_factors)} ---")
    # MODIFIED: Use n_valid_responses for a more accurate sample size count (N).
    # 'count' now represents the number of replications, while 'N' is the total number of trials.
    if 'n_valid_responses' in df.columns:
        desc_stats = df.groupby(active_factors).agg(
            replications=('model', 'size'),
            N=('n_valid_responses', 'sum'),
            Mean=(metric, 'mean'),
            StdDev=(metric, 'std')
        ).rename(columns={'replications': 'Replications', 'N': 'Total Trials (N)', 'StdDev': 'Std. Dev.'})
    else:
        # Fallback for older data that doesn't have the new column
        desc_stats = df.groupby(active_factors)[metric].agg(['count', 'mean', 'std']).rename(columns={'count': 'Replications (N)', 'mean': 'Mean', 'std': 'Std. Dev.'})
    
    logging.info(f"\n{desc_stats.to_string(float_format='%.4f')}")
    
    formula = f"{metric} ~ {' + '.join([f'C({f})' for f in active_factors])}"
    
    try:
        model = ols(formula, data=df).fit()
        create_diagnostic_plot(model, metric, output_dir)
        anova_table = sm.stats.anova_lm(model, typ=2)
        
        logging.info(f"\n--- ANOVA Summary for {metric} ---")
        logging.info(f"\n{anova_table.to_string()}")
        
        significant_factors = [f.replace('C(', '').replace(')', '') for f in anova_table.index if anova_table.loc[f, 'PR(>F)'] < 0.05 and 'Residual' not in f]

        if significant_factors:
            logging.info(f"\nConclusion: Significant effect found for factor(s): {', '.join(significant_factors)}")
            logging.info("\n--- Post-Hoc Analysis (Tukey's HSD) ---")
            for factor in significant_factors:
                if factor == 'Residual': continue
                logging.info(f"\nComparing levels for factor: '{factor}'")
                tukey_result = pairwise_tukeyhsd(endog=df[metric], groups=df[factor], alpha=0.05)
                logging.info(f"\n{tukey_result}")
                if factor == 'model':
                    generate_performance_tiers(df, metric, tukey_result, display_name_map)
        else:
            logging.info("\nConclusion: No factors had a statistically significant effect on this metric.")
            
        logging.info("\n--- Generating Performance Plots ---")
        for factor in active_factors:
            # Construct the correct key to look up the p-value from the ANOVA table's index
            key = f"C({factor})"
            p_val = anova_table.loc[key, 'PR(>F)'] if key in anova_table.index else float('nan')
            create_and_save_plot(df, metric, factor, p_val, output_dir)
            
    except Exception as e:
        logging.error(f"\nERROR: Could not perform ANOVA for metric '{metric}'. Reason: {e}")

def main():
    """
    Main entry point for the ANOVA analysis script.

    Orchestrates the entire process:
    1. Parses command-line arguments for input file, output directory, and config.
    2. Sets up structured logging to file and console.
    3. Loads the master results CSV into a pandas DataFrame.
    4. **Performs a critical data cleaning step** to unify database names,
       correcting for known inconsistencies in the source data.
    5. Normalizes model names for display purposes based on the config file.
    6. Determines which metrics and factors to analyze.
    7. Iterates through each metric, calling perform_analysis to conduct the
       full statistical analysis and generate outputs.
    """
    parser = argparse.ArgumentParser(description="Perform ANOVA on experiment results.")
    parser.add_argument("input_path", help="Path to the top-level experiment directory.")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.input_path)
    output_dir = os.path.join(base_dir, 'anova')
    os.makedirs(output_dir, exist_ok=True)
    
    master_csv_path = find_master_csv(base_dir)
    if not master_csv_path:
        return

    log_filename = os.path.basename(master_csv_path).replace('.csv', '_analysis_log.txt')
    log_filepath = os.path.join(output_dir, log_filename)
    
    logging.basicConfig(level=logging.INFO,
                        format='%(message)s',
                        handlers=[logging.FileHandler(log_filepath, mode='w', encoding='utf-8'),
                                  logging.StreamHandler(sys.stdout)])
    
    logging.info(f"Full analysis log is being saved to: {log_filepath}")
    
    try:
        df = pd.read_csv(master_csv_path)
        logging.info(f"Successfully loaded {len(df)} rows from {master_csv_path}")
    except Exception as e:
        logging.error(f"FATAL: Could not load master CSV file. Error: {e}")
        return

    # --- DATA CLEANING (CRITICAL FIX) ---
    # Correct known data integrity issues in the source CSV.
    if 'db' in df.columns:
        original_db_values = df['db'].unique()
        df['db'] = df['db'].replace('personalities_db_1-5000.jsonl', 'personalities_db_1-5000.txt')
        cleaned_db_values = df['db'].unique()
        if len(original_db_values) > len(cleaned_db_values):
            logging.info("Performed data cleaning on 'db' column to unify values.")
            logging.info(f" -> Original unique values: {original_db_values}")
            logging.info(f" -> Cleaned unique values:  {cleaned_db_values}\n")

    # --- Load Normalization and Display Mappings from Config ---
    normalization_map = get_config_section_as_dict(APP_CONFIG, 'ModelNormalization')
    display_name_map = get_config_section_as_dict(APP_CONFIG, 'ModelDisplayNames')

    # Build a reverse map for efficient lookup: {keyword -> canonical_name}
    keyword_to_canonical_map = {}
    if normalization_map:
        for canonical, keywords in normalization_map.items():
            for keyword in keywords.split(','):
                keyword_to_canonical_map[keyword.strip()] = canonical

    # --- UNIFY AND SANITIZE MODEL NAMES (CRITICAL FIX) ---
    if 'model' in df.columns and keyword_to_canonical_map:
        logging.info("Normalizing model names for consistency based on config...")
        
        def normalize_name(raw_name):
            if not isinstance(raw_name, str): return raw_name
            for keyword, canonical in keyword_to_canonical_map.items():
                if keyword in raw_name:
                    return canonical
            return raw_name # Return original if no keyword matches

        df['model'] = df['model'].apply(normalize_name)
        logging.info("Model name normalization complete.")

        # Create a new column for display names to be used in plots
        df['model_display'] = df['model'].map(display_name_map).fillna(df['model'])
        logging.info("Created 'model_display' column for plots.")

        # Perform final sanitization on the canonical name for formula compatibility
        df['model'] = df['model'].str.replace('/', '_', regex=False).str.replace('-', '_', regex=False).str.replace('.', '_', regex=False)
        logging.info("Sanitized canonical model names for formula compatibility.\n")

    factors = get_config_list(APP_CONFIG, 'Schema', 'factors')
    metrics = get_config_list(APP_CONFIG, 'Schema', 'metrics')

    if not factors or not metrics:
        logging.error("FATAL: Could not load 'factors' or 'metrics' from config.ini.")
        return

    for factor in factors:
        if factor in df.columns:
            df[factor] = df[factor].astype(str)

    for metric in metrics:
        if metric in df.columns:
            perform_analysis(df, metric, factors, output_dir, display_name_map)
        else:
            logging.warning(f"\nWarning: Metric column '{metric}' not found. Skipping analysis.")

if __name__ == "__main__":
    main()

# === End of src/run_anova.py ===