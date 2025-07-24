$diagramsDir = "docs\diagrams"

$renameMap = @{
    "analysis_log_format.txt"                   = "format_analysis_log.txt"
    "architecture_data_flow.mmd"                = "view_data_flow.mmd"
    "architecture_experimental_logic.mmd"       = "logic_experimental.mmd"
    "architecture_workflow_1_run_experiment.mmd" = "flow_1_run_experiment.mmd"
    "architecture_workflow_2_audit_experiment.mmd" = "flow_2_audit_experiment.mmd"
    "architecture_workflow_3_update_experiment.mmd" = "flow_3_update_experiment.mmd"
    "architecture_workflow_4_migrate_data.mmd"  = "flow_4_migrate_data.mmd"
    "architecture_workflow_5_audit_study.mmd"   = "flow_5_audit_study.mmd"
    "architecture_workflow_6_analyze_study.mmd" = "flow_6_analyze_study.mmd"
    "architecture_workflow_7_update_study.mmd"  = "flow_7_update_study.mmd"
    "codebase_architecture.mmd"                 = "view_codebase.mmd"
    "decision_tree_workflow.mmd"                = "logic_workflow_chooser.mmd"
    "directory_structure.txt"                   = "view_directory_structure.txt"
    "replication_report_format.txt"             = "format_replication_report.txt"
}

$renameMap.GetEnumerator() | ForEach-Object {
    $oldPath = Join-Path $diagramsDir $_.Key
    $newPath = Join-Path $diagramsDir $_.Value
    if (Test-Path $oldPath) {
        Rename-Item -Path $oldPath -NewName $_.Value
        Write-Host "Renamed '$($_.Key)' to '$($_.Value)'" -ForegroundColor Green
    }
    else {
        Write-Host "Source file not found: '$($_.Key)'" -ForegroundColor Yellow
    }
}

Write-Host "Renaming complete."