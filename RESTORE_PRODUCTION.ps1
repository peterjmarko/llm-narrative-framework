# 🚨 EMERGENCY RESTORATION SCRIPT - ALL SRC/ FILES
Write-Host "🚨 EMERGENCY RESTORATION - RESTORING ALL SRC/ FROM BACKUPS"
Write-Host "="*55

# Remove read-only protection from ALL src/ files
$allSrcFiles = Get-ChildItem "src\*.py" -File
Write-Host "🔓 Unlocking $($allSrcFiles.Count) files..."

foreach ($file in $allSrcFiles) {
    Set-ItemProperty -Path $file.FullName -Name IsReadOnly -Value $false
    Write-Host "🔓 Unlocked: $($file.Name)"
}

# Restore specific files from backups (only ones we have backups for)
if (Test-Path "src\analyze_llm_performance.py.backup") {
    Copy-Item "src\analyze_llm_performance.py.backup" "src\analyze_llm_performance.py" -Force
    Write-Host "✅ Restored: analyze_llm_performance.py"
}

if (Test-Path "src\compile_study_results.py.backup") {
    Copy-Item "src\compile_study_results.py.backup" "src\compile_study_results.py" -Force  
    Write-Host "✅ Restored: compile_study_results.py"
}

Write-Host "`n⚠️  NOTE: Only files with .backup versions were restored!"
Write-Host "⚠️  Other files remain unlocked for manual review"

Write-Host "`nTo re-protect all src/ files, run:"
Write-Host "Get-ChildItem 'src\*.py' | ForEach-Object { Set-ItemProperty -Path `$_.FullName -Name IsReadOnly -Value `$true }"
