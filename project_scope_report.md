# Project Scope & Extent Report

**Generated on:** 2025-08-03

---

## 📄 Documents

-   **Total Files:** 11
-   **Total Estimated Pages:** ~150.1 (based on 37,537 words)

| File | Word Count | Estimated Pages |
|:---:|:---:|:---:|
| `CHANGELOG.md` | 7170 | ~28.7 |
| `CONTRIBUTING.md` | 1703 | ~6.8 |
| `LICENSE.md` | 5761 | ~23.0 |
| `README.md` | 282 | ~1.1 |
| `data/README.md` | 606 | ~2.4 |
| `docs/DOCUMENTATION.md` | 5419 | ~21.7 |
| `docs/DOCUMENTATION.template.md` | 5409 | ~21.6 |
| `docs/article_cover_letter.md` | 308 | ~1.2 |
| `docs/article_main_text.md` | 4475 | ~17.9 |
| `docs/article_supplementary_material.md` | 5680 | ~22.7 |
| `project_scope_report.md` | 724 | ~2.9 |
| **Total** | **37,537** | **~150.1** |


---

## 💻 Scripts

-   **Total Files:** 68
-   **Total Lines of Code:** 17,387

| File | Lines of Code |
|:---:|:---:|
| `audit_experiment.ps1` | 115 |
| `audit_study.ps1` | 286 |
| `migrate_experiment.ps1` | 195 |
| `migrate_study.ps1` | 208 |
| `new_experiment.ps1` | 132 |
| `process_study.ps1` | 237 |
| `repair_experiment.ps1` | 249 |
| `repair_study.ps1` | 221 |
| `scripts/build_docs.py` | 507 |
| `scripts/changelog_hook.py` | 29 |
| `scripts/convert_py_to_txt.py` | 248 |
| `scripts/docx_postprocessor.py` | 58 |
| `scripts/finalize_release.py` | 188 |
| `scripts/generate_scope_report.py` | 160 |
| `scripts/lint_file_headers.py` | 153 |
| `scripts/list_project_files.py` | 358 |
| `src/__init__.py` | 0 |
| `src/analyze_llm_performance.py` | 787 |
| `src/build_llm_queries.py` | 363 |
| `src/compile_experiment_results.py` | 97 |
| `src/compile_replication_results.py` | 136 |
| `src/compile_study_results.py` | 100 |
| `src/config_loader.py` | 246 |
| `src/experiment_manager.py` | 1226 |
| `src/filter_adb_candidates.py` | 174 |
| `src/generate_database.py` | 138 |
| `src/generate_replication_report.py` | 138 |
| `src/llm_prompter.py` | 423 |
| `src/orchestrate_replication.py` | 371 |
| `src/patch_old_experiment.py` | 86 |
| `src/prepare_sf_import.py` | 205 |
| `src/process_llm_responses.py` | 645 |
| `src/query_generator.py` | 438 |
| `src/replication_log_manager.py` | 210 |
| `src/restore_config.py` | 125 |
| `src/run_bias_analysis.py` | 155 |
| `src/study_analyzer.py` | 483 |
| `tests/Test-Harness.ps1` | 58 |
| `tests/__init__.py` | 0 |
| `tests/analyze_study.Tests.ps1` | 71 |
| `tests/audit_experiment.Tests.ps1` | 42 |
| `tests/conftest.py` | 37 |
| `tests/migrate_experiment.Tests.ps1` | 110 |
| `tests/run_all_ps_tests.ps1` | 70 |
| `tests/run_all_tests.py` | 203 |
| `tests/run_experiment.Tests.ps1` | 81 |
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
| `tests/update_experiment.Tests.ps1` | 74 |
| **Total** | **17,387** |


---

## 📊 Diagrams

-   **Total Files:** 20
-   **Total Complexity Score (Lines):** 649

| File | Complexity (Lines) |
|:---:|:---:|
| `docs/diagrams/arch_main_codebase.mmd` | 100 |
| `docs/diagrams/arch_prep_codebase.mmd` | 11 |
| `docs/diagrams/data_main_flow.mmd` | 97 |
| `docs/diagrams/data_prep_flow.mmd` | 41 |
| `docs/diagrams/flow_main_1_new_experiment.mmd` | 25 |
| `docs/diagrams/flow_main_2_audit_experiment.mmd` | 18 |
| `docs/diagrams/flow_main_3_repair_experiment.mmd` | 21 |
| `docs/diagrams/flow_main_4_migrate_experiment.mmd` | 23 |
| `docs/diagrams/flow_main_5_process_study.mmd` | 32 |
| `docs/diagrams/flow_main_7_audit_study.mmd` | 23 |
| `docs/diagrams/flow_main_8_repair_study.mmd` | 22 |
| `docs/diagrams/flow_main_9_migrate_study.mmd` | 23 |
| `docs/diagrams/flow_prep_pipeline.mmd` | 24 |
| `docs/diagrams/logic_main_experiment.mmd` | 20 |
| `docs/diagrams/logic_main_replication.mmd` | 39 |
| `docs/diagrams/logic_main_study.mmd` | 23 |
| `docs/diagrams/logic_prep_filtering.mmd` | 15 |
| `docs/diagrams/logic_prep_generation.mmd` | 13 |
| `docs/diagrams/logic_workflow_chooser.mmd` | 40 |
| `docs/diagrams/logic_workflow_chooser_study.mmd` | 39 |
| **Total** | **649** |


---

## 💾 Data Files

-   **Total Files:** 17
-   **Total Size:** 24,468.5 KB

| File | Size (KB) |
|:---:|:---:|
| `data/adb_filtered_5000.txt` | 1048.2 |
| `data/base_query.txt` | 1.3 |
| `data/country_codes.csv` | 3.6 |
| `data/eminence_scores.csv` | 199.6 |
| `data/filter_adb_raw.csv` | 494.5 |
| `data/foundational_assets/balance_thresholds.csv` | 0.1 |
| `data/foundational_assets/neutralized_delineations/balances_elements.csv` | 2.6 |
| `data/foundational_assets/neutralized_delineations/balances_hemispheres.csv` | 1.6 |
| `data/foundational_assets/neutralized_delineations/balances_modes.csv` | 0.9 |
| `data/foundational_assets/neutralized_delineations/balances_quadrants.csv` | 0.9 |
| `data/foundational_assets/neutralized_delineations/balances_signs.csv` | 1.8 |
| `data/foundational_assets/point_weights.csv` | 0.2 |
| `data/foundational_assets/sf_delineations_library.txt` | 871.8 |
| `data/personalities_db.txt` | 17611.3 |
| `data/sources/adb_raw_export.txt` | 3314.5 |
| `data/sources/sf_chart_import.csv` | 430.1 |
| `data/sources/sf_data_import.txt` | 485.5 |
| **Total** | **24,468.5** |