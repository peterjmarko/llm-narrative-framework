#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/run_anova.py

"""
Statistical Analysis and Visualization (run_anova.py)

Purpose:
This script performs a full analysis pipeline:
1.  Loads data by either accepting a direct path to a master CSV file or by
    scanning a directory to find and aggregate all `final_summary_results.csv`
    files into a new master dataset.
2.  Performs an Analysis of Variance (ANOVA) to test for significant effects.
3.  Calculates effect size (Eta Squared) to determine the magnitude of the findings.
4.  Generates formatted, report-ready tables for Descriptive Statistics and ANOVA results.
5.  Runs post-hoc tests and generates a simplified "Performance Tiers" table.
6.  Generates and saves publication-quality box plots with visual legends.
7.  Optionally creates diagnostic plots (Q-Q plots) to check statistical assumptions.
8.  Saves all statistical output from the console to a detailed log file.

Plots and logs are saved in the same directory as the input path.
"""

import argparse
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from scipy.stats import levene
import os
import sys
import logging
import warnings
import glob

try:
    import matplotlib
    matplotlib.use('Agg')  # Use a non-interactive backend for servers or tests
    import seaborn as sns
    import matplotlib.pyplot as plt
    import networkx as nx
except ImportError:
    logging.error("\nERROR: Plotting or graph libraries not found. Please run:")
    logging.error("pip install seaborn matplotlib networkx")
    sys.exit(1)

warnings.simplefilter(action='ignore', category=FutureWarning)


def aggregate_and_load_data(base_dir, output_filename):
    """
    Finds, aggregates, and saves summary CSVs, then returns the master DataFrame.
    This function contains the logic from the original aggregate_summaries.py.
    """
    search_pattern = os.path.join(base_dir, '**', 'final_summary_results.csv')
    logging.info(f"AGGREGATION MODE: Searching for files matching: {search_pattern}")
    csv_files = glob.glob(search_pattern, recursive=True)

    if not csv_files:
        logging.error("ERROR: No 'final_summary_results.csv' files found. Cannot proceed.")
        return None, None

    logging.info(f"\nFound {len(csv_files)} summary files to aggregate.")
    all_dfs = []
    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path)
            # Clean the data: The provided CSV shows blank lines or summary rows
            # from compile_results.py. We only want rows with run data.
            df.dropna(subset=['run_directory'], inplace=True)
            if not df.empty:
                all_dfs.append(df)
        except Exception as e:
            logging.warning(f"Warning: Could not read or process file {file_path}. Error: {e}")

    if not all_dfs:
        logging.error("ERROR: Although files were found, none could be successfully read or contained data. Aborting.")
        return None, None
        
    master_df = pd.concat(all_dfs, ignore_index=True)
    final_output_path = os.path.join(base_dir, output_filename)
    
    master_df.to_csv(final_output_path, index=False)
    logging.info(f"\nSuccessfully aggregated {len(master_df)} rows into: {final_output_path}\n")
    return master_df, final_output_path


def format_p_value(p_value):
    """Formats a p-value for display on a plot title."""
    if p_value < 0.001:
        return "p < 0.001"
    else:
        return f"p = {p_value:.3f}"


def calculate_eta_squared(anova_table):
    """Calculates Eta Squared (η²) effect size from an ANOVA table."""
    ss_effect = anova_table.loc[anova_table.index[0], 'sum_sq']
    ss_residual = anova_table.loc['Residual', 'sum_sq']
    eta_squared = ss_effect / (ss_effect + ss_residual)
    return eta_squared


def generate_performance_tiers(df, metric, tukey_result):
    """Groups models into performance tiers based on Tukey HSD results."""
    logging.info("\n--- Performance Tiers (Models in the same tier are not statistically different) ---")
    
    G = nx.Graph()
    models = df['model'].unique()
    G.add_nodes_from(models)
    
    tukey_df = pd.DataFrame(data=tukey_result._results_table.data[1:], columns=tukey_result._results_table.data[0])
    
    for _, row in tukey_df.iterrows():
        if not row['reject']:
            G.add_edge(row['group1'], row['group2'])
            
    tiers = list(nx.connected_components(G))
    
    tier_medians = []
    for tier in tiers:
        tier_median = df[df['model'].isin(tier)][metric].median()
        tier_medians.append((tier_median, tier))
        
    sorted_tiers = sorted(tier_medians, key=lambda x: x[0], reverse=True)
    
    tier_data = []
    for i, (median_val, tier_models) in enumerate(sorted_tiers):
        tier_data.append([f"Tier {i+1}", f"{median_val:.4f}", ", ".join(tier_models)])
    
    tier_df = pd.DataFrame(tier_data, columns=["Performance Tier", "Median Score", "Models"])
    logging.info(f"\n{tier_df.to_string(index=False)}")


def create_diagnostic_plot(model, metric, output_dir):
    """Creates and saves a Q-Q plot of the ANOVA residuals to check for normality."""
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    sm.qqplot(model.resid, line='s', ax=ax)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    ax.set_title(f"Q-Q Plot of Residuals for '{metric}'")
    
    plot_filename = f"diagnostic_qqplot_{metric}.png"
    full_plot_path = os.path.join(output_dir, plot_filename)
    
    try:
        plt.savefig(full_plot_path)
        logging.info(f"-> Diagnostic plot saved successfully to: {full_plot_path}")
    except Exception as e:
        logging.error(f"-> ERROR: Could not save diagnostic plot. Reason: {e}")
    
    plt.close(fig)


def draw_visual_legend(fig):
    """Draws a detailed, graphical legend as an inset on the figure."""
    legend_ax = fig.add_axes([0.798, 0.02, 0.18, 0.15])
    
    legend_ax.set_facecolor('#f7f7f7')
    for spine in legend_ax.spines.values():
        spine.set_edgecolor('gray')
        spine.set_linewidth(0.5)

    y_center = 0.5
    box_left, median, box_right = [0.25, 0.4, 0.55]
    whisker_left, whisker_right = [0.05, 0.75]
    outlier = 0.95

    legend_ax.add_patch(plt.Rectangle((box_left, y_center-0.1), box_right-box_left, 0.2, 
                                      fill=True, facecolor='#a9a9a9', edgecolor='black', lw=1))
    legend_ax.plot([median, median], [y_center-0.1, y_center+0.1], color='black', lw=1.5)
    
    legend_ax.plot([whisker_left, box_left], [y_center, y_center], color='black', lw=1)
    legend_ax.plot([box_right, whisker_right], [y_center, y_center], color='black', lw=1)
    
    legend_ax.plot(outlier, y_center, 'o', mec='black', mfc='white', markersize=5)

    text_color = '#222222'
    
    legend_ax.annotate('Median', xy=(median, y_center+0.1), xytext=(median, 0.95),
                       ha='center', va='top', fontsize=8, color=text_color,
                       arrowprops=dict(arrowstyle='->', facecolor='black', shrinkB=5))
    
    legend_ax.annotate('Middle 50%\n(Interquartile Range)', xy=(median, y_center-0.1), xytext=(median, 0.05),
                       ha='center', va='bottom', fontsize=8, color=text_color,
                       arrowprops=dict(arrowstyle='->', facecolor='black', shrinkB=5))
    
    legend_ax.annotate('Typical Range', xy=(whisker_right, y_center), xytext=(whisker_right, 0.95),
                       ha='center', va='top', fontsize=8, color=text_color,
                       arrowprops=dict(arrowstyle='->', facecolor='black', shrinkB=5))
    
    legend_ax.annotate('Outlier', xy=(outlier, y_center), xytext=(outlier, 0.05),
                       ha='center', va='bottom', fontsize=8, color=text_color,
                       arrowprops=dict(arrowstyle='->', facecolor='black', shrinkB=5))

    legend_ax.set_xticks([])
    legend_ax.set_yticks([])
    legend_ax.set_xlim(0, 1.1)
    legend_ax.set_ylim(0, 1.1)


def create_and_save_plot(df, metric, factor, p_value, output_dir):
    """Generates and saves a sorted box plot, annotated with a p-value and a visual legend."""
    fig = plt.figure(figsize=(12, 8))
    ax = plt.gca()
    
    try:
        # Group data by the factor and sort groups by median value for ordered plotting
        grouped = df.groupby(factor)
        sorted_groups = sorted(grouped, key=lambda x: x[1][metric].median(), reverse=True)
        sorted_labels = [name for name, _ in sorted_groups]
        data_to_plot = [group[metric].dropna().values for _, group in sorted_groups]
    except Exception as e:
        logging.error(f"Could not prepare data for plotting: {e}")
        plt.close(fig)
        return

    # Create the boxplot directly with Matplotlib, using the modern API to avoid warnings.
    ax.boxplot(data_to_plot, orientation='horizontal', tick_labels=sorted_labels, patch_artist=True,
               boxprops=dict(facecolor='lightblue', color='black'),
               medianprops=dict(color='black'))

    ax.invert_yaxis()  # Reverse the order to show the best model on top

    p_value_str = format_p_value(p_value)
    title = f'Performance Comparison for: {metric}\n(Grouped by {factor}, ANOVA {p_value_str})'
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Metric: {metric}', fontsize=12)
    ax.set_ylabel(f'Factor: {factor}', fontsize=12)
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    
    # Adjust layout before drawing the legend. The `rect` right boundary is set
    # to extend the main plot area underneath the legend's position.
    plt.tight_layout(rect=[0, 0, 0.99, 1])
    draw_visual_legend(fig)
    
    plot_filename = f"{metric}_by_{factor}_boxplot.png"
    full_plot_path = os.path.join(output_dir, plot_filename)
    
    try:
        plt.savefig(full_plot_path)
        logging.info(f"-> Plot with visual legend saved successfully to: {full_plot_path}")
    except Exception as e:
        logging.error(f"-> ERROR: Could not save plot. Reason: {e}")
    
    plt.close(fig)


def perform_analysis(df, metric, all_possible_factors, output_dir):
    """Performs ANOVA, post-hoc analysis, and plotting for a single metric."""
    logging.info("\n" + "="*80)
    logging.info(f" ANALYSIS FOR METRIC: '{metric}'")
    logging.info("="*80)

    active_factors = [f for f in all_possible_factors if df[f].nunique() > 1]
    if not active_factors:
        logging.info("INFO: Only one experimental group found. No analysis possible.")
        return
    logging.info(f"Detected {len(active_factors)} active factor(s) with variation: {', '.join(active_factors)}")

    logging.info("\n--- Descriptive Statistics by Model ---")
    desc_stats = df.groupby('model')[metric].agg(['count', 'mean', 'std']).rename(
        columns={'count': 'N', 'mean': 'Mean', 'std': 'Std. Dev.'}
    )
    logging.info(f"\n{desc_stats.to_string(float_format='%.4f')}")
    
    # Check if ANOVA is possible (at least 2 groups with >1 data point each)
    can_run_anova = not any(count <= 1 for count in desc_stats['N'])
    significant_factors_clean = []
    anova_table = None

    if not can_run_anova:
        logging.warning("\nWARNING: At least one group has only one data point. ANOVA and post-hoc tests will be skipped.")
    else:
        grouped_data = [group[metric].values for name, group in df.groupby(active_factors)]
        stat, p_levene = levene(*grouped_data)
        logging.info(f"\n--- Assumption Check: Homogeneity of Variances (Levene's Test) ---")
        logging.info(f"Levene's Test Statistic: {stat:.4f}, p-value: {p_levene:.4f}")
        if p_levene < 0.05:
            logging.warning("WARNING: The assumption of equal variances is violated. Interpret ANOVA results with caution.")
        else:
            logging.info("OK: The assumption of equal variances is met.")

        formula = f"{metric} ~ {' + '.join([f'C({factor})' for factor in active_factors])}"
        
        try:
            model = ols(formula, data=df).fit()

            create_diagnostic_plot(model, metric, output_dir)

            anova_table = sm.stats.anova_lm(model, typ=2)
            
            eta_sq = calculate_eta_squared(anova_table)
            f_value = anova_table.loc[anova_table.index[0], 'F']
            p_value = anova_table.loc[anova_table.index[0], 'PR(>F)']
            df_effect = int(anova_table.loc[anova_table.index[0], 'df'])
            df_residual = int(anova_table.loc['Residual', 'df'])

            summary_data = {
                'Metric': metric,
                'F-statistic': f"{f_value:.2f}",
                'df': f"({df_effect}, {df_residual})",
                'p-value': format_p_value(p_value).replace("p ", ""),
                'Eta Squared (η²)': f"{eta_sq:.2f}"
            }
            summary_df = pd.DataFrame([summary_data]).set_index('Metric')
            
            logging.info(f"\n--- Formatted ANOVA Summary ---")
            logging.info(f"\n{summary_df.to_string()}")
            
            logging.info("\n--- Raw ANOVA Table (for reference) ---")
            logging.info(f"\n{anova_table.to_string()}")
            
            significant_factors_raw = anova_table[anova_table['PR(>F)'] < 0.05].index.tolist()
            significant_factors_clean = [f.replace("C(", "").replace(")", "") for f in significant_factors_raw]

            if significant_factors_clean:
                logging.info(f"\nConclusion: Significant effect found for factor(s): {', '.join(significant_factors_clean)}")
                logging.info("\n--- Post-Hoc Analysis (Tukey's HSD) ---")
                for factor in significant_factors_clean:
                    logging.info(f"\nComparing levels for factor: '{factor}'")
                    tukey_result = pairwise_tukeyhsd(endog=df[metric], groups=df[factor], alpha=0.05)
                    logging.info(f"\n{tukey_result}")
                    
                    if factor == 'model':
                        generate_performance_tiers(df, metric, tukey_result)
            else:
                logging.info("\nConclusion: No factors had a statistically significant effect on this metric.")
                        
        except Exception as e:
            logging.error(f"\nERROR: Could not perform ANOVA. Reason: {e}")

    # --- Plotting Section (runs regardless of ANOVA success) ---
    # Simplified: Always plot all active factors for complete visualization.
    factors_to_plot = active_factors
    if factors_to_plot:
        logging.info("\n--- Generating Performance Plots ---")
    
    for factor in factors_to_plot:
        # If ANOVA was run, use the specific p-value. Otherwise, use NaN.
        plot_p_value = anova_table.loc[f'C({factor})', 'PR(>F)'] if anova_table is not None else float('nan')
        create_and_save_plot(df, metric, factor, plot_p_value, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Aggregate summaries and/or perform ANOVA on experiment results.")
    parser.add_argument(
        "input_path", 
        help="Path to a directory to aggregate, or to a pre-aggregated master CSV file."
    )
    parser.add_argument(
        "--master_filename",
        default="MASTER_ANOVA_DATASET.csv",
        help="Filename for the aggregated CSV (used only when input_path is a directory)."
    )
    args = parser.parse_args()

    # Setup logging first to capture all messages, including aggregation steps
    log_filepath = None # Will be set later
    logger = logging.getLogger()
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.setLevel(logging.INFO)
    
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(ch)

    # --- Determine input type and load data ---
    df = None
    master_csv_path = None

    if os.path.isdir(args.input_path):
        output_dir = os.path.abspath(args.input_path)
        df, master_csv_path = aggregate_and_load_data(output_dir, args.master_filename)
        if df is None: # Aggregation failed
            return 
    elif os.path.isfile(args.input_path):
        logging.info(f"FILE MODE: Loading data directly from {args.input_path}")
        output_dir = os.path.dirname(os.path.abspath(args.input_path))
        master_csv_path = args.input_path
        try:
            df = pd.read_csv(master_csv_path)
        except FileNotFoundError:
            logging.error(f"Error: The file was not found at '{master_csv_path}'")
            return
    else:
        logging.error(f"Error: The provided input path is not a valid file or directory: {args.input_path}")
        return

    # --- Setup file-based logging now that we have the output path ---
    log_filename = os.path.basename(master_csv_path).replace('.csv', '_analysis_log.txt')
    log_filepath = os.path.join(output_dir, log_filename)
    fh = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(fh)
    logging.info(f"Full analysis log is being saved to: {log_filepath}")


    # --- Proceed with Analysis ---
    factors = ['model', 'temperature', 'k', 'm']
    for factor in list(factors):
        if factor not in df.columns:
            factors.remove(factor)
        else:
            df[factor] = df[factor].astype(str)

    metrics = [
        'mean_mrr', 'mean_top_1_acc', 'mean_top_3_acc', 
        'mean_effect_size_r', 'mwu_stouffer_z', 'mwu_fisher_chi2'
    ]

    for metric in metrics:
        if metric in df.columns:
            perform_analysis(df, metric, factors, output_dir)
        else:
            logging.warning(f"\nWarning: Metric column '{metric}' not found in the CSV file. Skipping.")

    # Properly close the file handler to release the lock on the log file
    if fh:
        logger.removeHandler(fh)
        fh.close()

if __name__ == "__main__":
    main()

# === End of src/run_anova.py ===