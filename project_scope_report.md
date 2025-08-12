# Project Scope & Extent Report

**Generated on:** 2025-08-12

---

## 📄 Documents

-   **Total Files:** 13
-   **Total Estimated Pages:** ~161.7 (based on 40,433 words)

| File | Word Count | Estimated Pages |
|:---:|:---:|:---:|
| `CHANGELOG.md` | 9864 | ~39.5 |
| `CONTRIBUTING.md` | 2316 | ~9.3 |
| `LICENSE.md` | 5761 | ~23.0 |
| `README.md` | 375 | ~1.5 |
| `ROADMAP.md` | 751 | ~3.0 |
| `config/changelog_template.md` | 34 | ~0.1 |
| `data/README_DATA.md` | 972 | ~3.9 |
| `docs/DOCUMENTATION.md` | 6041 | ~24.2 |
| `docs/DOCUMENTATION.template.md` | 6031 | ~24.1 |
| `docs/article_cover_letter.md` | 308 | ~1.2 |
| `docs/article_main_text.md` | 4648 | ~18.6 |
| `docs/article_supplementary_material.md` | 2521 | ~10.1 |
| `project_scope_report.md` | 811 | ~3.2 |
| **Total** | **40,433** | **~161.7** |


---

## 💻 Scripts

-   **Total Files:** 83
-   **Total Lines of Code:** 22,630

| File | Lines of Code |
|:---:|:---:|
| `audit_experiment.ps1` | 115 |
| `audit_study.ps1` | 286 |
| `migrate_experiment.ps1` | 195 |
| `migrate_study.ps1` | 209 |
| `new_experiment.ps1` | 132 |
| `process_study.ps1` | 237 |
| `repair_experiment.ps1` | 249 |
| `repair_study.ps1` | 222 |
| `scripts/build_docs.py` | 507 |
| `scripts/changelog_hook.py` | 46 |
| `scripts/convert_py_to_txt.py` | 248 |
| `scripts/docx_postprocessor.py` | 62 |
| `scripts/finalize_release.py` | 188 |
| `scripts/generate_scope_report.py` | 204 |
| `scripts/inspect_adb_categories.py` | 90 |
| `scripts/lint_docstrings.py` | 162 |
| `scripts/lint_file_headers.py` | 270 |
| `scripts/list_project_files.py` | 303 |
| `scripts/validate_import_file.py` | 79 |
| `src/__init__.py` | 0 |
| `src/analyze_llm_performance.py` | 787 |
| `src/analyze_research_patterns.py` | 93 |
| `src/build_llm_queries.py` | 365 |
| `src/compile_experiment_results.py` | 97 |
| `src/compile_replication_results.py` | 136 |
| `src/compile_study_results.py` | 100 |
| `src/config_loader.py` | 246 |
| `src/create_subject_db.py` | 203 |
| `src/experiment_manager.py` | 1226 |
| `src/fetch_adb_data.py` | 413 |
| `src/filter_adb_candidates.py` | 326 |
| `src/generate_eminence_scores.py` | 479 |
| `src/generate_ocean_scores.py` | 714 |
| `src/generate_personalities_db.py` | 191 |
| `src/generate_replication_report.py` | 138 |
| `src/id_encoder.py` | 48 |
| `src/llm_prompter.py` | 423 |
| `src/neutralize_delineations.py` | 415 |
| `src/orchestrate_replication.py` | 371 |
| `src/patch_eminence_scores.py` | 105 |
| `src/patch_old_experiment.py` | 86 |
| `src/prepare_sf_import.py` | 161 |
| `src/process_llm_responses.py` | 645 |
| `src/query_generator.py` | 438 |
| `src/replication_log_manager.py` | 210 |
| `src/restore_config.py` | 125 |
| `src/run_bias_analysis.py` | 155 |
| `src/select_eligible_candidates.py` | 151 |
| `src/select_final_candidates.py` | 140 |
| `src/study_analyzer.py` | 483 |
| `src/validate_adb_data.py` | 1639 |
| `src/validate_country_codes.py` | 131 |
| `tests/Test-Harness.ps1` | 75 |
| `tests/__init__.py` | 0 |
| `tests/analyze_study.Tests.ps1` | 70 |
| `tests/audit_experiment.Tests.ps1` | 61 |
| `tests/conftest.py` | 37 |
| `tests/migrate_experiment.Tests.ps1` | 109 |
| `tests/run_all_ps_tests.ps1` | 88 |
| `tests/run_all_tests.py` | 203 |
| `tests/run_experiment.Tests.ps1` | 99 |
| `tests/test_aggregate_experiments.py` | 104 |
| `tests/test_analyze_llm_performance.py` | 591 |
| `tests/test_bayes.py` | 51 |
| `tests/test_build_docs.py` | 214 |
| `tests/test_build_llm_queries.py` | 289 |
| `tests/test_config_loader.py` | 184 |
| `tests/test_convert_py_to_txt.py` | 324 |
| `tests/test_experiment_manager.py` | 401 |
| `tests/test_list_project_files.py` | 585 |
| `tests/test_llm_prompter.py` | 426 |
| `tests/test_orchestrate_replication.py` | 622 |
| `tests/test_patch_old_experiment.py` | 127 |
| `tests/test_process_llm_responses.py` | 911 |
| `tests/test_query_generator.py` | 253 |
| `tests/test_replication_log_manager.py` | 162 |
| `tests/test_restore_config.py` | 145 |
| `tests/test_robustness.py` | 114 |
| `tests/test_run_bias_analysis.py` | 135 |
| `tests/test_run_llm_sessions.py` | 628 |
| `tests/test_smoke.py` | 198 |
| `tests/test_study_analyzer.py` | 287 |
| `tests/update_experiment.Tests.ps1` | 93 |
| **Total** | **22,630** |


---

## 📊 Diagrams

-   **Total Files:** 27
-   **Total Complexity Score (Lines):** 838

| File | Complexity (Lines) |
|:---:|:---:|
| `docs/diagrams/arch_main_codebase.mmd` | 82 |
| `docs/diagrams/arch_prep_codebase.mmd` | 26 |
| `docs/diagrams/data_main_flow.mmd` | 82 |
| `docs/diagrams/data_prep_flow_1_sourcing.mmd` | 32 |
| `docs/diagrams/data_prep_flow_2_scoring.mmd` | 33 |
| `docs/diagrams/data_prep_flow_3_generation.mmd` | 49 |
| `docs/diagrams/flow_main_1_new_experiment.mmd` | 25 |
| `docs/diagrams/flow_main_2_audit_experiment.mmd` | 18 |
| `docs/diagrams/flow_main_3_repair_experiment.mmd` | 21 |
| `docs/diagrams/flow_main_4_migrate_experiment.mmd` | 23 |
| `docs/diagrams/flow_main_5_process_study.mmd` | 32 |
| `docs/diagrams/flow_main_6_new_study.mmd` | 3 |
| `docs/diagrams/flow_main_7_audit_study.mmd` | 23 |
| `docs/diagrams/flow_main_8_repair_study.mmd` | 22 |
| `docs/diagrams/flow_main_9_migrate_study.mmd` | 23 |
| `docs/diagrams/flow_prep_pipeline.mmd` | 38 |
| `docs/diagrams/logic_main_experiment.mmd` | 20 |
| `docs/diagrams/logic_main_replication.mmd` | 39 |
| `docs/diagrams/logic_main_study.mmd` | 23 |
| `docs/diagrams/logic_prep_eligible_candidates.mmd` | 19 |
| `docs/diagrams/logic_prep_eminence_scoring.mmd` | 34 |
| `docs/diagrams/logic_prep_final_candidates.mmd` | 16 |
| `docs/diagrams/logic_prep_generation.mmd` | 13 |
| `docs/diagrams/logic_prep_neutralization.mmd` | 39 |
| `docs/diagrams/logic_prep_ocean_scoring.mmd` | 24 |
| `docs/diagrams/logic_workflow_chooser.mmd` | 40 |
| `docs/diagrams/logic_workflow_chooser_study.mmd` | 39 |
| **Total** | **838** |


---

## 💾 Data Files

-   **Total Files:** 30
-   **Total Size:** 23,874.1 KB

| File | Size (KB) |
|:---:|:---:|
| `data/base_query.txt` | 1.3 |
| `data/config/adb_research_categories.json` | 1.7 |
| `data/foundational_assets/adb_category_map.csv` | 16.0 |
| `data/foundational_assets/balance_thresholds.csv` | 0.1 |
| `data/foundational_assets/country_codes.csv` | 3.6 |
| `data/foundational_assets/eminence_scores.csv` | 280.9 |
| `data/foundational_assets/eminence_scores_summary.txt` | 1.1 |
| `data/foundational_assets/neutralized_delineations/balances_elements.csv` | 2.0 |
| `data/foundational_assets/neutralized_delineations/balances_hemispheres.csv` | 1.3 |
| `data/foundational_assets/neutralized_delineations/balances_modes.csv` | 0.8 |
| `data/foundational_assets/neutralized_delineations/balances_quadrants.csv` | 0.5 |
| `data/foundational_assets/neutralized_delineations/balances_signs.csv` | 1.9 |
| `data/foundational_assets/neutralized_delineations/points_in_signs.csv` | 32.7 |
| `data/foundational_assets/ocean_scores.csv` | 276.5 |
| `data/foundational_assets/point_weights.csv` | 0.2 |
| `data/foundational_assets/sf_chart_export.csv` | 2826.8 |
| `data/foundational_assets/sf_delineations_library.txt` | 871.8 |
| `data/intermediate/adb_eligible_candidates.txt` | 2503.2 |
| `data/intermediate/adb_final_candidates.txt` | 1899.5 |
| `data/intermediate/ocean_scores_discarded.csv` | 56.1 |
| `data/intermediate/sf_data_import.txt` | 524.7 |
| `data/personalities_db.txt` | 8303.9 |
| `data/processed/subject_db.csv` | 1448.2 |
| `data/reports/adb_validation_report.csv` | 1169.7 |
| `data/reports/adb_validation_summary.txt` | 0.8 |
| `data/reports/missing_eminence_scores.txt` | 0.0 |
| `data/reports/missing_ocean_scores.txt` | 70.3 |
| `data/reports/missing_sf_subjects.csv` | 256.0 |
| `data/reports/ocean_scores_summary.txt` | 6.4 |
| `data/sources/adb_raw_export.txt` | 3316.1 |
| **Total** | **23,874.1** |