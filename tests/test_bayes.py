import pandas as pd
import pingouin as pg
import numpy as np
import traceback

print("--- Running Bayesian Diagnostic Script v2.0 ---")

try:
    data = {
        'mapping_strategy': ['correct'] * 180 + ['random'] * 180,
        'value': list(np.random.normal(1.0, 0.1, 180)) + list(np.random.normal(0.98, 0.1, 180))
    }
    df = pd.DataFrame(data)
    print("Sample data created successfully.")

    group1 = df[df['mapping_strategy'] == 'correct']['value']
    group2 = df[df['mapping_strategy'] == 'random']['value']
    print(f"Group 1 (correct) has {len(group1)} values. Mean: {group1.mean():.3f}")
    print(f"Group 2 (random) has {len(group2)} values. Mean: {group2.mean():.3f}")

    print("Attempting Bayesian T-Test...")
    # Use pg.ttest(), which correctly takes data arrays and returns a result
    # that includes the Bayes Factor (BF10).
    bf_result = pg.ttest(group1, group2, paired=False)
    
    print("\n--- Bayesian Analysis Result ---")
    print(bf_result)
    # Extract the BF10 value and explicitly cast it to a float
    bf10 = float(bf_result['BF10'].iloc[0])
    print(f"\nSuccessfully extracted Bayes Factor (BF₁₀): {bf10:.3f}")

except Exception:
    print(f"\n--- SCRIPT FAILED ---")
    # This will print the full error traceback
    traceback.print_exc()

print("\n--- Diagnostic Complete ---")