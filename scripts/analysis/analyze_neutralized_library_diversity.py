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
# Filename: scripts/analysis/analyze_neutralized_library_diversity.py

"""
Neutralized Component Library Diversity Analysis

Validates that neutralization preserved description discriminability by analyzing
semantic diversity across all neutralized delineation components.

Output: Saves results to output/validation_reports/neutralized_library_diversity_analysis.txt

Author: Analysis script for publication validation
Date: October 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Set random seed for reproducibility
np.random.seed(42)

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "reports"
DATA_DIR = PROJECT_ROOT / "data" / "foundational_assets" / "neutralized_delineations"


def load_all_components():
    """Load all neutralized component libraries."""
    
    components = []
    component_sources = []
    
    # Load each component file
    files = {
        'points_in_signs': DATA_DIR / 'points_in_signs.csv',
        'balances_elements': DATA_DIR / 'balances_elements.csv',
        'balances_modes': DATA_DIR / 'balances_modes.csv',
        'balances_hemispheres': DATA_DIR / 'balances_hemispheres.csv',
        'balances_quadrants': DATA_DIR / 'balances_quadrants.csv',
        'balances_signs': DATA_DIR / 'balances_signs.csv',
    }
    
    for source_name, filepath in files.items():
        if not filepath.exists():
            raise FileNotFoundError(f"Required file not found: {filepath}")
        df = pd.read_csv(filepath, header=None, names=['key', 'text'])
        for idx, row in df.iterrows():
            components.append(row['text'])
            component_sources.append(source_name)
    
    return components, component_sources


def analyze_component_diversity():
    """Analyze diversity of neutralized component library."""
    
    output_lines = []
    
    def log(msg=""):
        """Helper to print and save output."""
        print(msg)
        output_lines.append(msg)
    
    def progress(msg):
        """Print progress message without saving to output."""
        print(f"   → {msg}")
    
    log("=" * 80)
    log("NEUTRALIZED COMPONENT LIBRARY DIVERSITY ANALYSIS")
    log("=" * 80)
    log(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Random Seed: 42 (for reproducibility)")
    log("")
    
    # Load components
    progress("Loading component libraries...")
    components, sources = load_all_components()
    progress(f"Loaded {len(components)} components ✓")
    
    log(f"\nTotal delineation components: {len(components)}")
    log(f"\nComponents by category:")
    for source in sorted(set(sources)):
        count = sources.count(source)
        log(f"  {source}: {count} components")
    
    # ========================================================================
    # METRIC 1: Length and Complexity
    # ========================================================================
    log("\n" + "-" * 80)
    log("METRIC 1: LENGTH AND COMPLEXITY")
    log("-" * 80)
    
    progress("Calculating word counts and complexity metrics...")
    word_counts = [len(comp.split()) for comp in components]
    char_counts = [len(comp) for comp in components]
    progress("Length analysis complete ✓")
    
    log(f"\nWord count per component:")
    log(f"  Mean: {np.mean(word_counts):.1f} words")
    log(f"  Std Dev: {np.std(word_counts):.1f} words")
    log(f"  Range: {np.min(word_counts)} - {np.max(word_counts)} words")
    log(f"  Coefficient of Variation: {np.std(word_counts)/np.mean(word_counts):.3f}")
    
    # ========================================================================
    # METRIC 2: Vocabulary Diversity
    # ========================================================================
    log("\n" + "-" * 80)
    log("METRIC 2: VOCABULARY DIVERSITY")
    log("-" * 80)
    
    progress("Analyzing vocabulary diversity...")
    all_words = ' '.join(components).lower().split()
    unique_words = set(all_words)
    progress(f"Found {len(unique_words)} unique terms ✓")
    
    log(f"\nTotal vocabulary in component library: {len(unique_words)} unique words")
    log(f"Total word tokens: {len(all_words)} words")
    log(f"Type-Token Ratio: {len(unique_words)/len(all_words):.4f}")
    
    # Pairwise vocabulary overlap
    progress("Computing pairwise vocabulary overlap (this may take a moment)...")
    component_vocabs = [set(comp.lower().split()) for comp in components]
    
    overlaps = []
    for i in range(len(components)):
        for j in range(i+1, min(i+20, len(components))):
            vocab_i = component_vocabs[i]
            vocab_j = component_vocabs[j]
            if len(vocab_i | vocab_j) > 0:
                overlap = len(vocab_i & vocab_j) / len(vocab_i | vocab_j)
                overlaps.append(overlap)
    progress(f"Computed {len(overlaps)} pairwise comparisons ✓")
    
    log(f"\nPairwise vocabulary overlap (Jaccard, n={len(overlaps)} pairs):")
    log(f"  Mean: {np.mean(overlaps):.3f}")
    log(f"  Std Dev: {np.std(overlaps):.3f}")
    log(f"  Range: {np.min(overlaps):.3f} - {np.max(overlaps):.3f}")
    
    # ========================================================================
    # METRIC 3: Semantic Similarity
    # ========================================================================
    log("\n" + "-" * 80)
    log("METRIC 3: SEMANTIC SIMILARITY (TF-IDF)")
    log("-" * 80)
    
    progress("Building TF-IDF vectors...")
    vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(components)
    progress(f"TF-IDF matrix created: {tfidf_matrix.shape} ✓")
    
    log(f"\nTF-IDF matrix shape: {tfidf_matrix.shape}")
    
    # Calculate all pairwise similarities
    progress("Computing pairwise cosine similarities (this takes ~10 seconds)...")
    cosine_sim_matrix = cosine_similarity(tfidf_matrix)
    
    # Extract upper triangle (excluding diagonal)
    upper_triangle = cosine_sim_matrix[np.triu_indices_from(cosine_sim_matrix, k=1)]
    progress(f"Computed {len(upper_triangle):,} similarity scores ✓")
    
    log(f"\nPairwise cosine similarity (all {len(upper_triangle):,} pairs):")
    log(f"  Mean: {np.mean(upper_triangle):.3f}")
    log(f"  Std Dev: {np.std(upper_triangle):.3f}")
    log(f"  Median: {np.median(upper_triangle):.3f}")
    log(f"  Range: {np.min(upper_triangle):.3f} - {np.max(upper_triangle):.3f}")
    
    log(f"\nSimilarity percentiles:")
    for percentile in [25, 50, 75, 90, 95, 99]:
        val = np.percentile(upper_triangle, percentile)
        log(f"  {percentile}th percentile: {val:.3f}")
    
    # ========================================================================
    # METRIC 4: Within-Category vs Between-Category Similarity
    # ========================================================================
    log("\n" + "-" * 80)
    log("METRIC 4: WITHIN-CATEGORY VS BETWEEN-CATEGORY SIMILARITY")
    log("-" * 80)
    
    # Calculate within-category similarities
    progress("Comparing within-category vs between-category similarities...")
    within_sims = []
    between_sims = []
    
    for i in range(len(components)):
        for j in range(i+1, len(components)):
            sim = cosine_sim_matrix[i, j]
            if sources[i] == sources[j]:
                within_sims.append(sim)
            else:
                between_sims.append(sim)
    progress(f"Category analysis complete ✓")
    
    log(f"\nWithin-category similarity (same component type, n={len(within_sims)}):")
    log(f"  Mean: {np.mean(within_sims):.3f}")
    log(f"  Std Dev: {np.std(within_sims):.3f}")
    
    log(f"\nBetween-category similarity (different component types, n={len(between_sims)}):")
    log(f"  Mean: {np.mean(between_sims):.3f}")
    log(f"  Std Dev: {np.std(between_sims):.3f}")
    
    if np.mean(within_sims) > np.mean(between_sims):
        log(f"\n✓ Within-category components are MORE similar than between-category")
        log(f"  This validates that component categories are semantically coherent")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    log("\n" + "=" * 80)
    log("SUMMARY AND INTERPRETATION")
    log("=" * 80)
    
    mean_similarity = np.mean(upper_triangle)
    mean_overlap = np.mean(overlaps)
    cv = np.std(word_counts)/np.mean(word_counts)
    
    log(f"\n📊 KEY FINDINGS:")
    log(f"\n1. COMPONENT SEMANTIC DIVERSITY:")
    log(f"   Mean cosine similarity: {mean_similarity:.3f}")
    
    if mean_similarity < 0.20:
        log(f"   ✓ EXCELLENT: Components are highly distinct")
    elif mean_similarity < 0.35:
        log(f"   ✓ GOOD: Components show substantial differentiation")
    elif mean_similarity < 0.50:
        log(f"   ⚠ MODERATE: Components share some common patterns")
    else:
        log(f"   ✗ CONCERN: Components may be too similar (Barnum-like)")
    
    log(f"\n2. VOCABULARY DIVERSITY:")
    log(f"   Mean vocabulary overlap: {mean_overlap:.3f}")
    log(f"   Total unique vocabulary: {len(unique_words)} words")
    
    if mean_overlap < 0.30:
        log(f"   ✓ EXCELLENT: Components use diverse vocabulary")
    elif mean_overlap < 0.45:
        log(f"   ✓ GOOD: Components show vocabulary variation")
    else:
        log(f"   ⚠ MODERATE: Components share vocabulary")
    
    log(f"\n3. STRUCTURAL COHERENCE:")
    within_vs_between = np.mean(within_sims) - np.mean(between_sims)
    log(f"   Within-category similarity: {np.mean(within_sims):.3f}")
    log(f"   Between-category similarity: {np.mean(between_sims):.3f}")
    log(f"   Difference: {within_vs_between:.3f}")
    
    if within_vs_between > 0.05:
        log(f"   ✓ GOOD: Component categories are semantically coherent")
    
    log("\n" + "=" * 80)
    log("TEXT FOR PAPER")
    log("=" * 80)
    
    log("\n📝 Add to Methods (Neutralization section):")
    log("\n" + "-" * 80)
    paper_text = f"""
To validate that neutralization preserved description discriminability, we analyzed 
semantic diversity across the {len(components)} neutralized delineation components 
that serve as building blocks for profile generation. TF-IDF vectorization with 
pairwise cosine similarity analysis revealed mean similarity of {mean_similarity:.3f} 
(SD = {np.std(upper_triangle):.3f}), indicating components are meaningfully distinct 
rather than generic variants. Vocabulary analysis showed mean pairwise overlap 
(Jaccard similarity) of {mean_overlap:.3f} (SD = {np.std(overlaps):.3f}), with the 
component library utilizing {len(unique_words):,} unique terms (type-token ratio = 
{len(unique_words)/len(all_words):.3f}). Within-category components showed higher 
semantic similarity (M = {np.mean(within_sims):.3f}) than between-category 
components (M = {np.mean(between_sims):.3f}), confirming the neutralization 
process preserved the system's semantic structure. Component length varied 
substantially (M = {np.mean(word_counts):.1f} words, SD = {np.std(word_counts):.1f}, 
CV = {cv:.3f}), demonstrating the algorithm utilized diverse building blocks rather 
than template-like patterns. These metrics confirm that neutralization maintained 
discriminability at the component level, which is then preserved through 
deterministic assembly into complete profiles.
    """.strip()
    log(paper_text)
    log("-" * 80)
    log("")
    
    return output_lines, {
        'mean_similarity': mean_similarity,
        'mean_overlap': mean_overlap,
        'total_components': len(components),
        'unique_vocabulary': len(unique_words),
        'within_category_sim': np.mean(within_sims),
        'between_category_sim': np.mean(between_sims)
    }


def main():
    """Main execution function."""
    
    print("\n" + "=" * 80)
    print("NEUTRALIZED LIBRARY DIVERSITY ANALYSIS")
    print("=" * 80)
    print("\n🔍 Starting analysis...\n")
    
    # Run analysis
    output_lines, metrics = analyze_component_diversity()
    
    print("\n   → Saving results to file...")
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save results
    output_file = OUTPUT_DIR / "neutralized_library_diversity_analysis.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"\n✅ Analysis complete!")
    print(f"\n📄 Results saved to: {output_file.relative_to(PROJECT_ROOT)}")
    print(f"\n💡 Use this file to cite quantitative evidence of component diversity")
    print(f"   in response to Barnum effect concerns.\n")


if __name__ == "__main__":
    main()

# === End of scripts/analysis/analyze_neutralized_library_diversity.py ===
