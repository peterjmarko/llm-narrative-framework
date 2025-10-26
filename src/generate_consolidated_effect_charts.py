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
# Filename: src/generate_consolidated_effect_charts.py

"""
Generate Consolidated Effect Size Charts from Subset Analyses

This script parses CONSOLIDATED_ANALYSIS_LOG.txt and generates consolidated
effect size charts showing patterns across subsets (e.g., Goldilocks effect).

Features:
- Goldilocks chart: mapping_strategy effect across k levels
- Model heterogeneity: mapping_strategy effect across models
- Uses actual subset analysis results (not re-analyzed)
- Publication-ready: 300 DPI, professional styling

Usage:
    python scripts/analysis/generate_consolidated_effect_charts.py <anova_subsets_dir>
    
Example:
    python scripts/analysis/generate_consolidated_effect_charts.py output/studies/publication_run/anova_subsets
"""

import os
import sys
import re
import configparser
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Configuration
FACTOR_DISPLAY_NAMES = {
    'model': 'Model',
    'mapping_strategy': 'Mapping Strategy',
    'k': 'Group Size (k)',
    'm': 'Number of Trials (m)',
    'temperature': 'Temperature'
}

def load_config():
    """Load config.ini from project root."""
    current = Path(__file__).resolve().parent
    for _ in range(5):  # Search up to 5 levels
        config_path = current / 'config.ini'
        if config_path.exists():
            config = configparser.ConfigParser()
            config.read(config_path)
            return config
        current = current.parent
    return None

def parse_consolidated_log(log_path, target_metric='mean_mrr_lift'):
    """
    Parse CONSOLIDATED_ANALYSIS_LOG.txt to extract subset ANOVA results.
    
    Returns:
        dict: {subset_id: {metric: {factor: {eta_sq, p_value, f_stat}}}}
    """
    if not os.path.exists(log_path):
        print(f"Error: Log file not found: {log_path}", file=sys.stderr)
        return None
    
    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = {}
    
    # Split by subset analysis sections
    # Pattern: path contains "1.1_k7_analysis" or similar
    subset_pattern = r'([\d.]+_k\d+_analysis)|(model_comparison)'
    
    # Find all metric sections within subsets
    # Look for: "ANALYSIS FOR METRIC: 'MRR Lift (vs. Chance)'"
    metric_pattern = r"ANALYSIS FOR METRIC: '([^']+)'"
    
    # Find ANOVA tables
    # Pattern: C(factor)  sum_sq  df  F  PR(>F)  eta_sq  p-corr
    anova_pattern = r'C\((\w+)\)\s+([\d.e+-]+)\s+([\d.]+)\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)'
    
    # Split content into sections by diagnostic plot paths (marks subset boundaries)
    sections = re.split(r'-> Diagnostic plot saved.*?\\([\d.]+_k\d+_analysis|model_comparison)\\', content)
    
    current_subset = None
    current_metric = None
    
    for line in content.split('\n'):
        # Detect subset from header line (more reliable)
        subset_header_match = re.search(r'### SUBSET: ([\d.]+_k\d+_analysis|[\w_]+)', line)
        if subset_header_match:
            current_subset = subset_header_match.group(1)
            if current_subset not in results:
                results[current_subset] = {}
            current_metric = None  # Reset metric when entering new subset
            continue
        
        # Detect metric
        metric_match = re.search(metric_pattern, line)
        if metric_match and current_subset:
            current_metric = metric_match.group(1)
            if current_metric not in results[current_subset]:
                results[current_subset][current_metric] = {}
            continue
        
        # Extract ANOVA statistics (only if we have both subset and metric)
        # Skip interaction terms (lines with ":")
        if ':' in line:
            continue
        
        anova_match = re.search(anova_pattern, line)
        if anova_match and current_subset and current_metric:
            factor = anova_match.group(1)
            f_stat = float(anova_match.group(4))
            p_value = float(anova_match.group(5))
            eta_sq = float(anova_match.group(6)) * 100  # Convert to percentage
            
            # Ensure metric exists in the nested dict before assignment
            if current_metric not in results[current_subset]:
                results[current_subset][current_metric] = {}
            
            results[current_subset][current_metric][factor] = {
                'eta_sq': eta_sq,
                'p_value': p_value,
                'f_stat': f_stat
            }
    
    return results

def extract_goldilocks_data(parsed_data, primary_factor='mapping_strategy', target_metric='MRR Lift (vs. Chance)'):
    """
    Extract primary_factor effect sizes across k levels.
    
    Returns:
        dict: {k_value: {eta_sq, p_value, f_stat}}
    """
    goldilocks_data = {}
    
    # Find k subsets (1.1_k7_analysis, 1.2_k10_analysis, 1.3_k14_analysis)
    k_pattern = re.compile(r'[\d.]+_k(\d+)_analysis')
    
    for subset_id, metrics in parsed_data.items():
        k_match = k_pattern.search(subset_id)
        if not k_match:
            continue
        
        k_value = int(k_match.group(1))
        
        if target_metric in metrics and primary_factor in metrics[target_metric]:
            goldilocks_data[k_value] = metrics[target_metric][primary_factor]
    
    return goldilocks_data

def extract_model_heterogeneity_data(parsed_data, primary_factor='mapping_strategy', target_metric='MRR Lift (vs. Chance)'):
    """
    Extract primary_factor effect sizes across models.
    
    Returns:
        dict: {model_name: {eta_sq, p_value, f_stat}}
    """
    heterogeneity_data = {}
    
    # Find model subsets (pattern: model name in subset_id)
    # These will be from individual model subset analyses
    # For now, we'll skip this as it requires model-specific subset analyses
    # which may not be in the consolidated log
    
    # Alternative: Extract from model_comparison subset if it exists
    for subset_id, metrics in parsed_data.items():
        if 'model_comparison' in subset_id:
            if target_metric in metrics and primary_factor in metrics[target_metric]:
                # This would be the overall model effect, not per-model
                pass
    
    # TODO: This requires additional subset analyses per model
    # For now, return empty dict
    return heterogeneity_data

def generate_goldilocks_chart(data, output_path):
    """Generate the Goldilocks chart showing effect across k levels."""
    # Sort by k value
    k_values = sorted(data.keys())
    eta_squared = [data[k]['eta_sq'] for k in k_values]
    p_values = [data[k]['p_value'] for k in k_values]
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Determine colors - highlight the peak
    peak_idx = eta_squared.index(max(eta_squared))
    colors = ['#d3d3d3'] * len(k_values)
    colors[peak_idx] = '#4472C4'  # Blue for peak
    
    # Override with significance colors for non-peak bars
    for i, p in enumerate(p_values):
        if i != peak_idx:
            if p < 0.001:
                colors[i] = '#4472C4'
            elif p < 0.05:
                colors[i] = '#70AD47'
    
    # Create bars
    x_pos = np.arange(len(k_values))
    bars = ax.bar(x_pos, eta_squared, color=colors, edgecolor='black', 
                  linewidth=1.5, width=0.6)
    
    # Add value labels on bars
    for i, (k, eta, p) in enumerate(zip(k_values, eta_squared, p_values)):
        # Add eta-squared value
        label_y = eta + max(eta_squared) * 0.03
        ax.text(i, label_y, f'η² = {eta:.2f}%', ha='center', va='bottom', 
                fontsize=11, fontweight='bold')
        
        # Add significance indicator
        if p < 0.001:
            sig = '***'
        elif p < 0.01:
            sig = '**'
        elif p < 0.05:
            sig = '*'
        else:
            sig = 'ns'
        ax.text(i, max(eta_squared) * 0.02, sig, ha='center', va='bottom', 
                fontsize=12, fontweight='bold')
    
    # Formatting
    ax.set_xlabel('Group Size (k)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Effect Size (η²) for Mapping Strategy', fontsize=12, fontweight='bold')
    ax.set_title('Mapping Strategy Effect Across Group Size (k)', 
                 fontsize=13, fontweight='bold', pad=15)
    
    ax.set_xticks(x_pos)
    
    # Format x-axis labels
    labels = []
    for k in k_values:
        if k == 7:
            labels.append('k=7\n(Easy)')
        elif k == 10:
            labels.append('k=10\n(Medium)')
        elif k == 14:
            labels.append('k=14\n(Hard)')
        else:
            labels.append(f'k={k}')
    ax.set_xticklabels(labels)
    
    y_max = max(eta_squared) * 1.25
    ax.set_ylim(0, y_max)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.axhline(y=0, color='black', linewidth=0.8)
    
    # Add note about significance
    fig.text(0.99, 0.01, '*** p < .001, ** p < .01, * p < .05, ns = not significant', 
             ha='right', va='bottom', fontsize=9, style='italic')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Generated Goldilocks chart: {os.path.basename(output_path)}")
    return True

def generate_consolidated_charts(subsets_dir, config):
    """Generate all consolidated charts from CONSOLIDATED_ANALYSIS_LOG.txt"""
    log_path = os.path.join(subsets_dir, 'CONSOLIDATED_ANALYSIS_LOG.txt')
    
    if not os.path.exists(log_path):
        print(f"Error: CONSOLIDATED_ANALYSIS_LOG.txt not found in {subsets_dir}", file=sys.stderr)
        return []
    
    # Get configuration
    target_metric = 'MRR Lift (vs. Chance)'  # Default
    if config and config.has_option('EffectSizeCharts', 'subset_chart_metric'):
        metric_key = config.get('EffectSizeCharts', 'subset_chart_metric')
        # Map metric key to display name
        metric_map = {
            'mean_mrr_lift': 'MRR Lift (vs. Chance)',
            'mean_top_1_acc_lift': 'Top-1 Accuracy Lift (vs. Chance)',
            'mean_top_3_acc_lift': 'Top-3 Accuracy Lift (vs. Chance)'
        }
        target_metric = metric_map.get(metric_key, target_metric)
    
    print(f"\nParsing {os.path.basename(log_path)}...")
    print(f"Target metric: {target_metric}")
    
    # Parse log
    parsed_data = parse_consolidated_log(log_path, target_metric)
    
    if not parsed_data:
        print("Error: Could not parse consolidated log", file=sys.stderr)
        return []
    
    print(f"Found {len(parsed_data)} subset(s) in log")
    
    # Create output directory
    output_dir = os.path.join(subsets_dir, 'effect_sizes')
    os.makedirs(output_dir, exist_ok=True)
    
    generated_files = []
    
    # Get chart rules from config
    rules_str = ''
    if config and config.has_option('EffectSizeCharts', 'subset_consolidated_charts'):
        rules_str = config.get('EffectSizeCharts', 'subset_consolidated_charts')
    
    if not rules_str.strip():
        print("No consolidated charts configured in [EffectSizeCharts] subset_consolidated_charts")
        return []
    
    print("\nGenerating consolidated charts:")
    
    for rule in rules_str.split(','):
        rule = rule.strip()
        if not rule or ':' not in rule:
            continue
        
        primary, stratify = rule.split(':', 1)
        primary = primary.strip()
        stratify = stratify.strip()
        
        if stratify == 'k':
            # Goldilocks chart
            data = extract_goldilocks_data(parsed_data, primary, target_metric)
            
            if not data:
                print(f"  ⚠ Skipping {primary}_x_k.png (no data found)")
                continue
            
            output_path = os.path.join(output_dir, f'{primary}_x_k.png')
            success = generate_goldilocks_chart(data, output_path)
            
            if success:
                generated_files.append(output_path)
        
        elif stratify == 'model':
            # Model heterogeneity chart
            data = extract_model_heterogeneity_data(parsed_data, primary, target_metric)
            
            if not data:
                print(f"  ⚠ Skipping {primary}_x_model.png (requires model-specific subset analyses)")
                continue
            
            # TODO: Implement model heterogeneity chart generation
            # output_path = os.path.join(output_dir, f'{primary}_x_model.png')
            # success = generate_model_heterogeneity_chart(data, output_path)
    
    return generated_files

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/analysis/generate_consolidated_effect_charts.py <anova_subsets_dir>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  python scripts/analysis/generate_consolidated_effect_charts.py output/studies/publication_run/anova_subsets", file=sys.stderr)
        sys.exit(1)
    
    subsets_dir = sys.argv[1]
    
    if not os.path.exists(subsets_dir):
        print(f"Error: Directory not found: {subsets_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Load configuration
    config = load_config()
    if config:
        print("Loaded configuration from config.ini")
    else:
        print("Warning: config.ini not found, using defaults")
    
    # Generate charts
    print("\n" + "="*70)
    print("CONSOLIDATED EFFECT SIZE CHART GENERATION")
    print("="*70)
    
    generated_files = generate_consolidated_charts(subsets_dir, config)
    
    if not generated_files:
        print("\n✗ No charts generated", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"✓ Success! Generated {len(generated_files)} chart(s)")
    print(f"\nCharts saved to: {subsets_dir}/effect_sizes/")
    print("="*70)

if __name__ == '__main__':
    main()

# === End of src/generate_consolidated_effect_charts.py ===
