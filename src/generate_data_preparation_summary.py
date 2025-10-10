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
# Filename: src/generate_data_preparation_summary.py

"""
Generates a comprehensive Data Preparation Pipeline Summary Report.

This script reads all existing reports from the data preparation pipeline and creates
a unified overview that provides end-to-end visibility into the pipeline status,
performance, and results.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Report configuration
PIPELINE_SUMMARY_PATH = "data/reports/data_preparation_pipeline_summary.txt"
PIPELINE_COMPLETION_INFO = "data/reports/pipeline_completion_info.json"

def load_pipeline_completion_info() -> Dict:
    """Loads the pipeline completion information from JSON."""
    try:
        with open(PIPELINE_COMPLETION_INFO, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_validation_summary() -> Dict:
    """Loads validation statistics from the validation summary report."""
    try:
        with open("data/reports/adb_validation_summary.txt", 'r') as f:
            content = f.read()
        
        # Parse the key statistics from the text report
        stats = {}
        for line in content.split('\n'):
            if "Total Records in Report:" in line:
                stats['total_records'] = int(line.split(':')[1].strip().replace(',', ''))
            elif "Valid Records:" in line:
                valid_part = line.split(':')[1].strip()
                stats['valid_records'] = int(valid_part.split('(')[0].strip().replace(',', ''))
            elif "Failed Records:" in line:
                failed_part = line.split(':')[1].strip()
                stats['failed_records'] = int(failed_part.split('(')[0].strip().replace(',', ''))
        return stats
    except FileNotFoundError:
        return {}

def load_eminence_summary() -> Dict:
    """Loads eminence scoring statistics from the eminence summary report."""
    try:
        with open("data/reports/eminence_scores_summary.txt", 'r') as f:
            content = f.read()
        
        stats = {}
        for line in content.split('\n'):
            if "Total Scored:" in line:
                stats['total_scored'] = int(line.split(':')[1].strip().replace(',', ''))
            elif "Total in Source:" in line:
                stats['total_in_source'] = int(line.split(':')[1].strip().replace(',', ''))
            elif "Mean:" in line:
                stats['mean_score'] = float(line.split(':')[1].strip())
        return stats
    except FileNotFoundError:
        return {}

def load_ocean_summary() -> Dict:
    """Loads OCEAN scoring statistics from the OCEAN summary report."""
    try:
        with open("data/reports/ocean_scores_summary.txt", 'r') as f:
            content = f.read()
        
        stats = {}
        for line in content.split('\n'):
            if "Total Scored:" in line:
                stats['total_scored'] = int(line.split(':')[1].strip().replace(',', ''))
            elif "Total in Source:" in line:
                stats['total_in_source'] = int(line.split(':')[1].strip().replace(',', ''))
        return stats
    except FileNotFoundError:
        return {}

def load_cutoff_analysis() -> Dict:
    """Loads cutoff parameter analysis results."""
    result = {}
    
    # Load CSV data if available
    try:
        df = pd.read_csv("data/reports/cutoff_parameter_analysis_results.csv")
        # Find the optimal parameters (minimum error)
        optimal_row = df.loc[df['Error'].idxmin()]
        result.update({
            'optimal_start_point': int(optimal_row['Start Point']),
            'optimal_smoothing_window': int(optimal_row['Smoothing Window']),
            'optimal_predicted_cutoff': int(optimal_row['Predicted Cutoff']),
            'optimal_error': int(optimal_row['Error']),
            'csv_available': True
        })
    except FileNotFoundError:
        result['csv_available'] = False
    
    # Try to extract cutoff from the variance curve analysis image
    try:
        # This is a simple text extraction approach
        # In a real implementation, you might use OCR to read the image
        # For now, we'll check if the file exists and note that manual extraction is needed
        variance_file = Path("data/reports/variance_curve_analysis.png")
        if variance_file.exists():
            result['variance_analysis_available'] = True
            # In a real implementation, you would extract the "Final Cutoff (4954)" text
            # For now, we'll just note that the file exists
            result['final_cutoff_from_image'] = "Manual extraction required"
        else:
            result['variance_analysis_available'] = False
    except Exception:
        result['variance_analysis_available'] = False
    
    return result

def count_missing_subjects(missing_file_path: str) -> int:
    """Counts the number of missing subjects from a missing subjects report."""
    try:
        with open(missing_file_path, 'r') as f:
            content = f.read()
        
        # Count non-header, non-empty lines
        lines = content.strip().split('\n')
        count = 0
        for line in lines:
            # Skip header lines and empty lines
            if not line.startswith('-') and not line.startswith('=') and line.strip():
                # Skip if it looks like a header
                if not any(keyword in line.lower() for keyword in ['subjects missed', 'none', 'subjects not attempted']):
                    count += 1
        return count
    except FileNotFoundError:
        return 0

def check_file_existence() -> Dict:
    """Checks for the existence of key pipeline output files."""
    files_to_check = [
        "data/sources/adb_raw_export.txt",
        "data/processed/adb_wiki_links.csv",
        "data/reports/adb_validation_report.csv",
        "data/intermediate/adb_eligible_candidates.txt",
        "data/foundational_assets/eminence_scores.csv",
        "data/foundational_assets/ocean_scores.csv",
        "data/intermediate/adb_final_candidates.txt",
        "data/intermediate/sf_data_import.txt",
        "data/foundational_assets/sf_delineations_library.txt",
        "data/foundational_assets/sf_chart_export.csv",
        "data/processed/subject_db.csv",
        "data/personalities_db.txt"
    ]
    
    existence = {}
    for file_path in files_to_check:
        existence[file_path] = Path(file_path).exists()
    
    return existence

def load_candidate_qualification_info() -> Dict:
    """Loads information about the candidate qualification process."""
    try:
        eligible_path = "data/intermediate/adb_eligible_candidates.txt"
        if Path(eligible_path).exists():
            with open(eligible_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Skip header line and count data records
                next(f)  # Skip header
                eligible_count = sum(1 for line in f if line.strip())
            return {'eligible_count': eligible_count}
        return {'eligible_count': 0}
    except Exception:
        return {'eligible_count': 0}


def load_final_candidates_info() -> Dict:
    """Loads information about the final candidates after cutoff."""
    try:
        final_path = "data/intermediate/adb_final_candidates.txt"
        if Path(final_path).exists():
            with open(final_path, 'r', encoding='utf-8', errors='ignore') as f:
                final_count = sum(1 for line in f if line.strip())
            return {'final_count': final_count}
        return {'final_count': 0}
    except Exception:
        return {'final_count': 0}

def calculate_pipeline_metrics(completion_info: Dict, validation_stats: Dict,
                              eminence_stats: Dict, ocean_stats: Dict) -> Dict:
    """Calculates overall pipeline metrics."""
    metrics = {
        'overall_completion_rate': 0.0,
        'overall_completion_count': 0,
        'overall_completion_total': 0,
        'data_quality_score': 0.0,
        'data_quality_count': 0,
        'data_quality_total': 0,
        'bottlenecks': [],
        'missing_subjects': {
            'eminence': 0,
            'ocean': 0,
            'sf_export': 0
        }
    }
    
    # Calculate overall completion rate based on LLM scoring steps
    # This represents the percentage of eligible candidates successfully processed
    
    # First try to get the completion rate from completion info
    completion_rates = []
    if 'eminence_scores' in completion_info:
        completion_rates.append(completion_info['eminence_scores']['completion_rate'])
        # Get the counts from completion info if available
        metrics['overall_completion_count'] = completion_info['eminence_scores'].get('subjects_processed', 0)
        metrics['overall_completion_total'] = completion_info['eminence_scores'].get('total_in_source', 0)
    
    if 'ocean_scores' in completion_info:
        completion_rates.append(completion_info['ocean_scores']['completion_rate'])
        # Update with OCEAN data if available (should be the same pool)
        metrics['overall_completion_count'] = completion_info['ocean_scores'].get('subjects_processed', 0)
        metrics['overall_completion_total'] = completion_info['ocean_scores'].get('total_in_source', 0)
    
    # Calculate the completion rate
    if completion_rates:
        metrics['overall_completion_rate'] = sum(completion_rates) / len(completion_rates)
    elif metrics['overall_completion_total'] > 0:
        # Calculate from raw counts if completion info is not available
        metrics['overall_completion_rate'] = (metrics['overall_completion_count'] / metrics['overall_completion_total']) * 100
    
    # If we still don't have valid counts, try to get them from the summary files
    if metrics['overall_completion_count'] == 0 and metrics['overall_completion_total'] == 0:
        if eminence_stats:
            metrics['overall_completion_count'] = eminence_stats.get('total_scored', 0)
            metrics['overall_completion_total'] = eminence_stats.get('total_in_source', 0)
            if metrics['overall_completion_total'] > 0:
                metrics['overall_completion_rate'] = (metrics['overall_completion_count'] / metrics['overall_completion_total']) * 100
    
    # Calculate data quality score based on validation success rate
    # This represents the percentage of raw records that passed Wikipedia validation
    if validation_stats:
        metrics['data_quality_count'] = validation_stats.get('valid_records', 0)
        metrics['data_quality_total'] = validation_stats.get('total_records', 1)
        quality_score = (metrics['data_quality_count'] / metrics['data_quality_total']) * 100
        metrics['data_quality_score'] = quality_score
    
    # Get missing subjects counts from completion info (more accurate than file parsing)
    if 'eminence_scores' in completion_info:
        metrics['missing_subjects']['eminence'] = completion_info['eminence_scores'].get('missing_count', 0)
        if completion_info['eminence_scores'].get('missing_count', 0) > 0:
            metrics['bottlenecks'].append("Eminence scoring has missing subjects")
    
    if 'ocean_scores' in completion_info:
        metrics['missing_subjects']['ocean'] = completion_info['ocean_scores'].get('missing_count', 0)
        if completion_info['ocean_scores'].get('missing_count', 0) > 0:
            metrics['bottlenecks'].append("OCEAN scoring has missing subjects")
    
    # Count missing subjects from SF export file (fallback method)
    metrics['missing_subjects']['sf_export'] = count_missing_subjects("data/reports/missing_sf_subjects.csv")
    
    return metrics

def load_final_database_info() -> Dict:
    """Loads information about the final subject database."""
    try:
        db_path = "data/processed/subject_db.csv"
        if Path(db_path).exists():
            df = pd.read_csv(db_path)
            return {
                'total_subjects': len(df),
                'file_exists': True,
                'file_size_mb': Path(db_path).stat().st_size / (1024 * 1024)
            }
        return {'file_exists': False}
    except Exception:
        return {'file_exists': False}

def load_delineation_info() -> Dict:
    """Loads information about the delineation library and neutralized files."""
    info = {
        'source_library_exists': False,
        'neutralized_files': {},
        'total_neutralized_files': 0
    }
    
    # Check for source delineation library
    if Path("data/foundational_assets/sf_delineations_library.txt").exists():
        info['source_library_exists'] = True
    
    # Check for neutralized delineations directory
    neutralized_dir = Path("data/foundational_assets/neutralized_delineations")
    if neutralized_dir.exists():
        expected_files = [
            "balances_elements.csv",
            "balances_hemispheres.csv",
            "balances_modes.csv",
            "balances_quadrants.csv",
            "balances_signs.csv",
            "points_in_signs.csv"
        ]
        
        for file_name in expected_files:
            file_path = neutralized_dir / file_name
            if file_path.exists():
                try:
                    line_count = sum(1 for _ in open(file_path, 'r', encoding='utf-8') if _.strip())
                    info['neutralized_files'][file_name] = {
                        'exists': True,
                        'line_count': line_count
                    }
                    info['total_neutralized_files'] += 1
                except Exception:
                    info['neutralized_files'][file_name] = {'exists': False}
            else:
                info['neutralized_files'][file_name] = {'exists': False}
    
    return info

def generate_pipeline_summary_report() -> str:
    """Generates the complete data preparation pipeline summary report."""
    # Load all report data
    completion_info = load_pipeline_completion_info()
    validation_stats = load_validation_summary()
    eminence_stats = load_eminence_summary()
    ocean_stats = load_ocean_summary()
    cutoff_analysis = load_cutoff_analysis()
    file_existence = check_file_existence()
    final_db_info = load_final_database_info()
    delineation_info = load_delineation_info()
    candidate_info = load_candidate_qualification_info()
    final_candidates_info = load_final_candidates_info()
    
    # Calculate overall metrics
    metrics = calculate_pipeline_metrics(completion_info, validation_stats, eminence_stats, ocean_stats)
    
    # Build the report
    report_lines = []
    banner = "=" * 80
    report_lines.extend([
        banner,
        "DATA PREPARATION PIPELINE SUMMARY REPORT".center(80),
        banner,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "--- OVERALL PIPELINE STATUS ---",
        f"Overall Completion Rate: {metrics['overall_completion_rate']:.1f}% ({metrics['overall_completion_count']:,}/{metrics['overall_completion_total']:,})",
        f"Data Quality Score: {metrics['data_quality_score']:.1f}% ({metrics['data_quality_count']:,}/{metrics['data_quality_total']:,})",
        "",
        "Notes:",
        f"• Overall Completion Rate: Percentage of eligible candidates successfully processed by LLM scoring",
        f"• Data Quality Score: Percentage of raw records that passed Wikipedia validation",
    ])
    
    # Get candidate counts
    eligible_candidates = candidate_info.get('eligible_count', 0)
    final_candidates = final_candidates_info.get('final_count', 0)
    valid_records = validation_stats.get('valid_records', 0)
    
    # STAGE 1: DATA SOURCING
    report_lines.extend([
        "",
        "================================================================================",
        "STAGE 1: DATA SOURCING".center(80),
        "================================================================================",
        "",
        "This stage fetches the initial raw dataset from the live Astro-Databank database.",
        "",
        "--- DATA FLOW ---",
        f"Live Astro-Databank Website",
        f"  ↓ ({validation_stats.get('total_records', 'Unknown'):,} total records)",
        f"Raw ADB Export",
        "",
        "--- SOURCING METRICS ---",
        f"Total Records Retrieved: {validation_stats.get('total_records', 'Unknown'):,}",
        f"Source File: data/sources/adb_raw_export.txt",
        "",
    ])
    
    # STAGE 2: CANDIDATE QUALIFICATION
    report_lines.extend([
        "",
        "================================================================================",
        "STAGE 2: CANDIDATE QUALIFICATION".center(80),
        "================================================================================",
        "",
        "This stage filters the raw ADB data through Wikipedia validation and deterministic",
        "filters to create a pool of eligible candidates for LLM scoring.",
        "",
        "--- DATA FLOW ---",
        f"Raw ADB Export",
        f"  ↓ ({validation_stats.get('total_records', 'Unknown'):,} total)",
        f"Wikipedia Validation",
        f"  ↓ ({validation_stats.get('valid_records', 'Unknown'):,} passed, {validation_stats.get('failed_records', 'Unknown'):,} failed)",
        f"Deterministic Filters",
        f"  ↓ ({eligible_candidates:,} eligible)",
        f"Eligible Candidates Pool",
        "",
        "--- QUALIFICATION METRICS ---",
        f"Data Quality Score: {metrics['data_quality_score']:.1f}% ({metrics['data_quality_count']:,}/{metrics['data_quality_total']:,})",
        f"  - Percentage of raw records that passed Wikipedia validation",
        "",
    ])
    
    if eligible_candidates < validation_stats.get('valid_records', 0):
        filtered_out = validation_stats.get('valid_records', 0) - eligible_candidates
        report_lines.extend([
            f"Additional Filters Applied:",
            f"  - {filtered_out:,} candidates filtered out by deterministic criteria",
            f"  - See data/intermediate/adb_eligible_candidates.txt for resulting pool"
        ])
    
    # STAGE 3: CANDIDATE SELECTION
    report_lines.extend([
        "",
        "================================================================================",
        "STAGE 3: CANDIDATE SELECTION".center(80),
        "================================================================================",
        "",
        "This stage uses LLM-based scoring to assess eminence and personality traits,",
        "then applies a cutoff algorithm to select the final research cohort.",
        "",
        "--- DATA FLOW ---",
        f"Eligible Candidates Pool",
        f"  ↓ ({eligible_candidates:,} candidates)",
        f"Eminence Scoring (LLM)",
        f"  ↓ ({eminence_stats.get('total_scored', 'Unknown'):,} scored, {metrics['missing_subjects']['eminence']:,} missing)",
        f"OCEAN Scoring (LLM)",
        f"  ↓ ({ocean_stats.get('total_scored', 'Unknown'):,} scored, {metrics['missing_subjects']['ocean']:,} missing)",
        f"Cutoff Algorithm",
        f"  ↓ ({final_candidates:,} selected)",
        f"Final Candidates Cohort",
        "",
        "--- SELECTION METRICS ---",
        f"Overall Completion Rate: {metrics['overall_completion_rate']:.1f}% ({metrics['overall_completion_count']:,}/{metrics['overall_completion_total']:,})",
        f"  - Percentage of eligible candidates successfully processed by LLM scoring",
        "",
    ])
    
    if eminence_stats:
        report_lines.extend([
            f"Eminence Scoring:",
            f"  - Mean Score: {eminence_stats.get('mean_score', 'Unknown'):.2f}",
            f"  - Success Rate: {(eminence_stats.get('total_scored', 0) / eminence_stats.get('total_in_source', 1) * 100):.1f}%",
        ])
    
    if final_candidates < eligible_candidates:
        cutoff_filtered = eligible_candidates - final_candidates
        selection_percentage = (final_candidates / eligible_candidates * 100) if eligible_candidates > 0 else 0
        report_lines.extend([
            f"Cutoff Selection:",
            f"  - {cutoff_filtered:,} candidates filtered by cutoff algorithm",
            f"  - Top {selection_percentage:.1f}% of eligible candidates selected",
            f"  - See data/reports/cutoff_parameter_analysis_results.csv for methodology"
        ])
    
    # STAGE 4: PROFILE GENERATION
    report_lines.extend([
        "",
        "================================================================================",
        "STAGE 4: PROFILE GENERATION".center(80),
        "================================================================================",
        "",
        "This stage processes the final candidates through Solar Fire for astrological calculations",
        "and LLM-based text neutralization to create the final research databases.",
        "",
        "--- DATA FLOW ---",
        f"Final Candidates Cohort",
        f"  ↓ ({final_candidates:,} candidates)",
        f"Solar Fire Processing (Manual)",
        f"  ↓ Chart calculations and export",
        f"Delineation Neutralization (LLM)",
        f"  ↓ {delineation_info.get('total_neutralized_files', 0)}/6 files neutralized",
        f"Final Research Databases",
        "",
        "--- GENERATION METRICS ---",
    ])
    
    if final_db_info.get('file_exists', False):
        final_subjects = final_db_info.get('total_subjects', 0)
        report_lines.extend([
            f"Subject Database: ✓ Complete",
            f"  - Total Subjects: {final_subjects:,}",
            f"  - File Size: {final_db_info.get('file_size_mb', 0):.2f} MB",
            f"  - Location: data/processed/subject_db.csv",
        ])
        
        # Explain the difference between final candidates and final database
        if final_subjects < final_candidates:
            difference = final_candidates - final_subjects
            report_lines.extend([
                f"  - Reduction: {difference:,} subjects lost during processing"
            ])
    else:
        report_lines.extend([
            f"Subject Database: ✗ Missing",
            f"  - Location: data/processed/subject_db.csv"
        ])
    
    # Add delineation library status
    if delineation_info.get('source_library_exists', False):
        report_lines.extend([
            f"Delineation Library: ✓ Available",
            f"  - Neutralized Files: {delineation_info.get('total_neutralized_files', 0)}/6 generated",
            f"  - Location: data/foundational_assets/neutralized_delineations/",
        ])
        
        # Add details about each neutralized file
        if delineation_info.get('neutralized_files'):
            report_lines.append("  - Files:")
            for file_name, file_info in delineation_info['neutralized_files'].items():
                status = "✓" if file_info.get('exists', False) else "✗"
                line_count = file_info.get('line_count', 0) if file_info.get('exists', False) else 0
                report_lines.append(f"    {status} {file_name} ({line_count} lines)")
    else:
        report_lines.extend([
            f"Delineation Library: ✗ Missing",
            f"  - Location: data/foundational_assets/sf_delineations_library.txt"
        ])
    
    # Add cutoff analysis details within Stage 2
    cutoff_file = "data/reports/cutoff_parameter_analysis_results.csv"
    if Path(cutoff_file).exists():
        # Load cutoff analysis details
        try:
            df = pd.read_csv(cutoff_file)
            optimal_row = df.loc[df['Error'].idxmin()]
            optimal_cutoff = int(optimal_row['Predicted Cutoff'])
            
            report_lines.extend([
                "",
                "--- CUTOFF ANALYSIS DETAILS ---",
                f"Optimal Cutoff Value: {optimal_cutoff:,}",
                f"Analysis File: data/reports/variance_curve_analysis.png",
                f"Analysis Method: Variance curve analysis across eminence score thresholds",
                "",
                "Note: This cutoff analysis was performed during a previous run of the pipeline ",
                f"and may not reflect the current dataset of {final_db_info.get('total_subjects', 0):,} subjects.",
                "The analysis file serves as documentation of the methodology used for cohort selection."
            ])
        except Exception:
            # Fallback if CSV can't be read
            report_lines.extend([
                "",
                "--- CUTOFF ANALYSIS DETAILS ---",
                f"Location: {cutoff_file}",
                f"Note: Analysis was performed on a different dataset and serves as methodological reference"
            ])
    
    # Add issues and recommendations section
    report_lines.extend([
        "",
        "================================================================================",
        "PIPELINE HEALTH & RECOMMENDATIONS".center(80),
        "================================================================================",
        "",
        "--- IDENTIFIED ISSUES ---",
    ])
    
    if metrics['bottlenecks']:
        for bottleneck in metrics['bottlenecks']:
            report_lines.append(f"⚠️  {bottleneck}")
    else:
        report_lines.append("✓ No critical issues detected")
    
    # Add stage-specific recommendations
    report_lines.extend([
        "",
        "--- RECOMMENDATIONS BY STAGE ---",
        "",
        "Stage 1 - Data Sourcing:",
        "  • Verify raw data integrity in data/sources/adb_raw_export.txt",
        "  • Check for any data fetching anomalies or incomplete records",
        "",
        "Stage 2 - Candidate Qualification:",
        "  • Review data/reports/adb_validation_report.csv for failed validation patterns",
        "  • Check data/intermediate/adb_eligible_candidates.txt for filter effectiveness",
        "",
        "Stage 3 - Candidate Selection:",
    ])
    
    if metrics['missing_subjects']['eminence'] > 0 or metrics['missing_subjects']['ocean'] > 0:
        report_lines.extend([
            f"  • Re-run scoring for missing subjects: {metrics['missing_subjects']['eminence'] + metrics['missing_subjects']['ocean']} total",
            f"  • Command: pdm run prep-data -StartWithStep 5  # For eminence scoring",
            f"  • Command: pdm run prep-data -StartWithStep 6  # For OCEAN scoring",
        ])
    else:
        report_lines.extend([
            "  • ✓ All eligible candidates successfully scored",
        ])
    
    report_lines.extend([
        "",
        "Stage 4 - Profile Generation:",
    ])
    
    if not final_db_info.get('file_exists', False):
        report_lines.extend([
            "  • Complete Solar Fire export process (manual step required)",
            "  • Verify chart export file is in the correct location",
        ])
    else:
        final_subjects = final_db_info.get('total_subjects', 0)
        if final_subjects < final_candidates:
            difference = final_candidates - final_subjects
            report_lines.extend([
                f"  • Investigate loss of {difference:,} subjects during processing",
            ])
        else:
            report_lines.extend([
                "  • ✓ Profile generation completed successfully",
            ])
    
    # Add file existence status
    report_lines.extend([
        "",
        "--- PIPELINE OUTPUT FILES STATUS ---",
    ])
    
    # Group files by stage
    stages = {
        "Data Sourcing": ["data/sources/adb_raw_export.txt"],
        "Candidate Qualification": [
            "data/processed/adb_wiki_links.csv",
            "data/reports/adb_validation_report.csv",
            "data/intermediate/adb_eligible_candidates.txt"
        ],
        "Candidate Selection": [
            "data/foundational_assets/eminence_scores.csv",
            "data/foundational_assets/ocean_scores.csv",
            "data/intermediate/adb_final_candidates.txt"
        ],
        "Profile Generation": [
            "data/intermediate/sf_data_import.txt",
            "data/foundational_assets/sf_delineations_library.txt",
            "data/foundational_assets/sf_chart_export.csv",
            "data/processed/subject_db.csv",
            "data/personalities_db.txt"
        ]
    }
    
    for stage, files in stages.items():
        report_lines.append(f"\n{stage}:")
        for file_path in files:
            status = "✓" if file_existence.get(file_path, False) else "✗"
            filename = file_path.split('/')[-1]
            report_lines.append(f"  {status} {filename}")
    
    # Add file references
    report_lines.extend([
        "",
        "--- DETAILED REPORTS ---",
        "  • Validation Summary: data/reports/adb_validation_summary.txt",
        "  • Validation Details: data/reports/adb_validation_report.csv",
        "  • Eminence Summary: data/reports/eminence_scores_summary.txt",
        "  • OCEAN Summary: data/reports/ocean_scores_summary.txt",
        "  • Cutoff Analysis: data/reports/cutoff_parameter_analysis_results.csv (separate analysis)",
        "  • Missing Data: data/reports/missing_*_scores.txt",
        "",
        "--- USAGE NOTES ---",
        "This report can be regenerated at any time using:",
        "  python src/generate_data_preparation_summary.py",
        "",
        banner
    ])
    
    return "\n".join(report_lines)

def main():
    """Main function to generate the data preparation pipeline summary report."""
    parser = argparse.ArgumentParser(
        description="Generate a comprehensive summary report for the data preparation pipeline."
    )
    parser.add_argument("--output", default=PIPELINE_SUMMARY_PATH,
                       help="Output path for the pipeline summary report.")
    args = parser.parse_args()
    
    # Ensure the reports directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    # Generate the report
    report_content = generate_pipeline_summary_report()
    
    # Write to file and console
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    # Create a console-safe version with ASCII characters
    console_safe_content = report_content.replace('✓', '[OK]').replace('✗', '[MISSING]').replace('⚠', '[WARNING]')
    
    try:
        print(console_safe_content)
        print(f"\nData preparation pipeline summary report saved to: {args.output}")
    except UnicodeEncodeError:
        # Final fallback - just print the success message
        print(f"Data preparation pipeline summary report saved to: {args.output}")
        print("View the file to see the full report with special characters.")

if __name__ == "__main__":
    main()

# === End of src/generate_data_preparation_summary.py ===
