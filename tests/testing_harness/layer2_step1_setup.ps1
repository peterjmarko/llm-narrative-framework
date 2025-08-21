# Filename: tests/testing_harness/layer2_step1_setup.ps1
function Get-ProjectRoot {
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) { return $currentDir.Path }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml)."
}

$ProjectRoot = Get-ProjectRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "--- Layer 2: Data Pipeline Orchestration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 1: Automated Setup ---" -ForegroundColor Cyan

# Create the test directory and all required subdirectories
$testDir = "temp_mock_test"; New-Item -Path $testDir -ItemType Directory -Force | Out-Null
$srcDir = (Join-Path $testDir "src"); New-Item -Path $srcDir -ItemType Directory | Out-Null
@("sources", "reports", "processed", "intermediate", "foundational_assets/neutralized_delineations") | ForEach-Object { New-Item -Path (Join-Path $testDir "data/$_") -ItemType Directory -Force | Out-Null }

# Copy the orchestrator
Copy-Item -Path "prepare_data.ps1" -Destination $testDir

# Create all mock Python scripts
Set-Content -Path (Join-Path $srcDir "find_wikipedia_links.py") -Value 'from pathlib import Path; Path("data/processed/adb_wiki_links.csv").touch()'
Set-Content -Path (Join-Path $srcDir "select_eligible_candidates.py") -Value 'from pathlib import Path; Path("data/processed/adb_eligible_candidates.txt").touch()'
Set-Content -Path (Join-Path $srcDir "generate_eminence_scores.py") -Value 'from pathlib import Path; Path("data/foundational_assets/eminence_scores.csv").touch()'
Set-Content -Path (Join-Path $srcDir "generate_ocean_scores.py") -Value 'from pathlib import Path; Path("data/foundational_assets/ocean_scores.csv").touch()'
Set-Content -Path (Join-Path $srcDir "select_final_candidates.py") -Value 'from pathlib import Path; Path("data/processed/adb_final_candidates.txt").touch()'
Set-Content -Path (Join-Path $srcDir "prepare_sf_import.py") -Value 'from pathlib import Path; Path("data/intermediate/sf_data_import.txt").touch()'
Set-Content -Path (Join-Path $srcDir "neutralize_delineations.py") -Value 'from pathlib import Path; p = Path("data/foundational_assets/neutralized_delineations/aspects.csv"); p.parent.mkdir(exist_ok=True); p.touch()'
Set-Content -Path (Join-Path $srcDir "create_subject_db.py") -Value 'from pathlib import Path; Path("data/processed/subject_db.csv").touch()'
Set-Content -Path (Join-Path $srcDir "generate_personalities_db.py") -Value 'from pathlib import Path; Path("personalities_db.txt").touch()'

# Create the seed data files
Set-Content -Path (Join-Path $testDir "data/sources/adb_raw_export.txt") -Value "..."
Set-Content -Path (Join-Path $testDir "data/reports/adb_validation_report.csv") -Value "..."

Write-Host "`nMock test environment created successfully in 'temp_mock_test'." -ForegroundColor Green
Write-Host "Your next action is Step 2: Execute the Test Workflow." -ForegroundColor Yellow
Write-Host ""