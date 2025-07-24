$templateFile = "docs\DOCUMENTATION.template.md"

# This is the exact same map used in the renaming script for consistency
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

if (-not (Test-Path $templateFile)) {
    Write-Error "Template file not found: $templateFile"
    exit 1
}

Write-Host "Updating references in: $templateFile"

# Read the entire file as a single string
$content = Get-Content -Path $templateFile -Raw

# Loop through the map and replace each old name with the new name
$renameMap.GetEnumerator() | ForEach-Object {
    if ($content.Contains($_.Key)) {
        $content = $content -replace $_.Key, $_.Value
        Write-Host " - Replaced '$($_.Key)' with '$($_.Value)'"
    }
}

# Write the modified content back to the file
Set-Content -Path $templateFile -Value $content

Write-Host "Reference updates complete." -ForegroundColor Green