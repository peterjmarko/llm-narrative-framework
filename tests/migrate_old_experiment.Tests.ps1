# Filename: tests/migrate_old_experiment.Tests.ps1

# This test script provides a Pester-free framework for testing migrate_old_experiment.ps1.
# It works by directly embedding the logic of the target script into a testable function
# and injecting mock implementations for external dependencies like filesystem commands
# and Python script execution.

# --- Test-Specific Global Variables and Helpers ---
$testFailures = 0
$totalTests = 0

# These global variables control the behavior of the mocks for each test case.
$script:mockPDMDetected = $true      # Controls Get-Command 'pdm' mock
$script:mockLASTEXITCODE_Global = 0  # Controls the simulated exit code of Python script calls
$script:capturedOutputByTestRun = @() # Captures all Write-Host output during a test run
$script:mockFileSystem = @{}         # Mocks the file system state for a given test

# --- Global Mock Functions (these override built-in PowerShell commands) ---

function global:Get-Command {
    param([string]$Name)
    if ($script:mockPDMDetected -and ($Name -eq "pdm")) {
        return "mock_pdm_command" # Simulate command found
    }
    return $null
}

function global:Resolve-Path {
    param([string]$Path)
    # For testing, we assume the path resolves to itself without change.
    return $Path
}

function global:Test-Path {
    param([string]$Path)
    # The key existence check is sufficient for our mock.
    return $script:mockFileSystem.ContainsKey($Path)
}

function global:Get-ChildItem {
    param([string]$Path, [string]$Filter, [switch]$Directory)

    $parentPath = $Path
    $matchingItems = @()

    foreach ($itemPath in $script:mockFileSystem.Keys) {
        if ($itemPath.StartsWith($parentPath) -and ($itemPath -ne $parentPath)) {
            $itemName = Split-Path -Path $itemPath -Leaf
            if ($Filter) {
                if ($itemName -like $Filter) {
                    $matchingItems += [pscustomobject]@{ FullName = $itemPath }
                }
            } else {
                 $matchingItems += [pscustomobject]@{ FullName = $itemPath }
            }
        }
    }
    return $matchingItems
}

function global:Remove-Item {
    param([string]$Path)
    # In the mock, we don't actually remove anything, but the script's Write-Host
    # calls confirm that this function would have been called.
}

# --- Testable Function encapsulating migrate_old_experiment.ps1's logic ---

function Test-MigrateExperimentMainLogic {
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true, Position = 0)]
        [string]$TargetDirectory
    )

    $script:capturedOutputByTestRun = @()
    $script:LASTEXITCODE = 0

    $originalWriteHost = Get-Command Write-Host -ErrorAction SilentlyContinue
    function Write-Host {
        param($Object, $ForegroundColor)
        if ($Object -is [PSCustomObject]) { $Object = $Object | Out-String -Stream }
        $script:capturedOutputByTestRun += $Object
    }
    
    $originalWriteError = Get-Command Write-Error -ErrorAction SilentlyContinue
    function Write-Error {
        param($Message)
        # Capture the error message as part of the output flow for simpler assertion
        $script:capturedOutputByTestRun += "ERROR: $($Message)"
    }

    try {
        # --- Start of migrate_old_experiment.ps1's content, adapted for testing ---

        # Auto-detect execution environment (uses global mocked Get-Command)
        $executable = "python"
        $prefixArgs = @()
        if (Get-Command pdm -ErrorAction SilentlyContinue) {
            Write-Host "PDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan
            $executable = "pdm"
            $prefixArgs = "run", "python"
        }
        else {
            Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow
        }

        # Function to execute a Python script using the detected executor, and check for errors
        function Invoke-PythonScript {
            param (
                [string]$StepName,
                [string]$ScriptName,
                [string[]]$Arguments
            )
            
            # Combine prefix arguments with the script and its arguments
            $finalArgs = $prefixArgs + $ScriptName + $Arguments

            Write-Host "[${StepName}] Executing: $executable $($finalArgs -join ' ')"
            
            # MOCK EXECUTION: Set exit code from global mock variable
            $script:LASTEXITCODE = $script:mockLASTEXITCODE_Global

            if ($LASTEXITCODE -ne 0) {
                throw "ERROR: Step '${StepName}' failed with exit code ${LASTEXITCODE}. Aborting migration."
            }
            
            Write-Host "Step '${StepName}' completed successfully."
            Write-Host ""
        }

        # Main Script Logic
        try {
            $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop
            
            Write-Host "`n######################################################"
            Write-Host "### Starting Data Migration for: '$($ResolvedPath)'"
            Write-Host "######################################################`n"

            # Step 1: Run patch_old_runs.py
            Invoke-PythonScript -StepName "1/4: Patch Configs" -ScriptName "src/patch_old_runs.py" -Arguments $ResolvedPath

            # Step 2: Run rebuild_reports.py
            Invoke-PythonScript -StepName "2/4: Rebuild Reports" -ScriptName "src/rebuild_reports.py" -Arguments $ResolvedPath

            # Step 3: Clean out old artifacts
            Write-Host "[3/4: Clean Artifacts] Cleaning up old and temporary files..."
            
            $filesToDelete = @("final_summary_results.csv", "batch_run_log.csv")
            foreach ($file in $filesToDelete) {
                $filePath = Join-Path -Path $ResolvedPath -ChildPath $file
                if (Test-Path $filePath) {
                    Write-Host " - Deleting old '$file'"
                    Remove-Item -Path $filePath -Force
                }
            }
            
            Write-Host " - Deleting '*.corrupted' reports and old 'analysis_inputs' directories..."
            Get-ChildItem -Path $ResolvedPath -Filter "run_*" -Directory | ForEach-Object {
                Get-ChildItem -Path $_.FullName -Filter "*.txt.corrupted" | Remove-Item -Force
                
                $analysisInputsPath = Join-Path -Path $_.FullName -ChildPath "analysis_inputs"
                if (Test-Path $analysisInputsPath) {
                    Remove-Item -Path $analysisInputsPath -Recurse -Force
                }
            }
            Write-Host "Step '3/4: Clean Artifacts' completed successfully."
            Write-Host ""

            # Step 4: Run replication_manager.py --reprocess
            Invoke-PythonScript -StepName "4/4: Final Reprocess" -ScriptName "src/replication_manager.py" -Arguments "--reprocess", $ResolvedPath
            
            Write-Host "######################################################"
            Write-Host "### Migration Finished Successfully! ###"
            Write-Host "######################################################`n"

        }
        catch {
            Write-Host "`n######################################################"
            Write-Host "### MIGRATION FAILED ###"
            Write-Host "######################################################"
            Write-Error $_.Exception.Message
            $script:LASTEXITCODE = 1
        }
        # --- End of migrate_old_experiment.ps1's content ---
    }
    finally {
        # Restore original functions
        Remove-Item function:Write-Host -ErrorAction SilentlyContinue
        Remove-Item function:Write-Error -ErrorAction SilentlyContinue
    }
    return $script:capturedOutputByTestRun
}


# --- Test Runner Function (reused from process_study.Tests.ps1) ---

function Run-Test {
    param(
        [string]$TestName,
        [ScriptBlock]$TestScriptBlock,
        [Array]$ExpectedOutputLines,
        [int]$ExpectedExitCode = 0
    )
    $script:totalTests++
    Write-Host "Running Test: $TestName" -ForegroundColor Cyan

    $script:capturedOutputByTestRun = @()
    $script:LASTEXITCODE = 0
    
    try {
        $TestScriptBlock.Invoke()
        $actualOutputLines = $script:capturedOutputByTestRun | ForEach-Object { "$_" }
        $actualExitCode = $script:LASTEXITCODE
    } catch {
        $actualOutputLines += "ERROR (Test harness caught): $($_.Exception.Message)"
        $actualExitCode = 1
    }

    $isOutputEqual = $true
    if ($actualOutputLines.Count -ne $ExpectedOutputLines.Count) {
        $isOutputEqual = $false
    } else {
        for ($i = 0; $i -lt $actualOutputLines.Count; $i++) {
            if ($actualOutputLines[$i] -ne $ExpectedOutputLines[$i]) {
                $isOutputEqual = $false
                break
            }
        }
    }

    if ($isOutputEqual -and ($actualExitCode -eq $ExpectedExitCode)) {
        Write-Host "PASS: $TestName`n" -ForegroundColor Green
    } else {
        $script:testFailures++
        Write-Host "FAIL: $TestName" -ForegroundColor Red
        Write-Host "  Expected Output ($($ExpectedOutputLines.Count) lines):" -ForegroundColor Yellow; $ExpectedOutputLines | ForEach-Object { Write-Host "    '$_'" }
        Write-Host "  Actual Output ($($actualOutputLines.Count) lines):" -ForegroundColor Yellow; $actualOutputLines | ForEach-Object { Write-Host "    '$_'" }
        if ($actualExitCode -ne $ExpectedExitCode) {
            Write-Host "  Expected Exit Code: $ExpectedExitCode, Actual: $actualExitCode" -ForegroundColor Yellow
        }
        Write-Host ""
    }
}

# --- TEST CASES ---

$targetDir = "C:\temp\old_study"

# Test 1: Successful run with PDM and all artifacts present for cleanup.
Run-Test "Successful run with PDM and artifacts to clean" {
    $script:mockPDMDetected = $true
    $script:mockLASTEXITCODE_Global = 0
    $script:mockFileSystem = @{
        "$targetDir" = $true;
        "$targetDir\final_summary_results.csv" = $true;
        "$targetDir\batch_run_log.csv" = $true;
        "$targetDir\run_001" = $true;
        "$targetDir\run_001\report.txt.corrupted" = $true;
        "$targetDir\run_001\analysis_inputs" = $true;
        "$targetDir\run_002" = $true;
        "$targetDir\run_002\analysis_inputs" = $true; # No corrupted file in this one
    }
    Test-MigrateExperimentMainLogic -TargetDirectory $targetDir
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "`n######################################################",
    "### Starting Data Migration for: 'C:\temp\old_study'",
    "######################################################`n",
    "[1/4: Patch Configs] Executing: pdm run python src/patch_old_runs.py C:\temp\old_study",
    "Step '1/4: Patch Configs' completed successfully.",
    "",
    "[2/4: Rebuild Reports] Executing: pdm run python src/rebuild_reports.py C:\temp\old_study",
    "Step '2/4: Rebuild Reports' completed successfully.",
    "",
    "[3/4: Clean Artifacts] Cleaning up old and temporary files...",
    " - Deleting old 'final_summary_results.csv'",
    " - Deleting old 'batch_run_log.csv'",
    " - Deleting '*.corrupted' reports and old 'analysis_inputs' directories...",
    "Step '3/4: Clean Artifacts' completed successfully.",
    "",
    "[4/4: Final Reprocess] Executing: pdm run python src/replication_manager.py --reprocess C:\temp\old_study",
    "Step '4/4: Final Reprocess' completed successfully.",
    "",
    "######################################################",
    "### Migration Finished Successfully! ###",
    "######################################################`n"
)

# Test 2: Failure during the first Python script call.
Run-Test "Failure during step 1 (Patch Configs)" {
    $script:mockPDMDetected = $true
    $script:mockLASTEXITCODE_Global = 1 # Simulate failure
    $script:mockFileSystem = @{ "$targetDir" = $true }
    Test-MigrateExperimentMainLogic -TargetDirectory $targetDir
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "`n######################################################",
    "### Starting Data Migration for: 'C:\temp\old_study'",
    "######################################################`n",
    "[1/4: Patch Configs] Executing: pdm run python src/patch_old_runs.py C:\temp\old_study",
    "`n######################################################",
    "### MIGRATION FAILED ###",
    "######################################################",
    "ERROR: ERROR: Step '1/4: Patch Configs' failed with exit code 1. Aborting migration."
) 1

# Test 3: Successful run without PDM.
Run-Test "Successful run without PDM" {
    $script:mockPDMDetected = $false # Simulate no PDM
    $script:mockLASTEXITCODE_Global = 0
    $script:mockFileSystem = @{
        "$targetDir" = $true;
        "$targetDir\final_summary_results.csv" = $true;
    }
    Test-MigrateExperimentMainLogic -TargetDirectory $targetDir
} @(
    "PDM not detected. Using standard 'python' command.",
    "`n######################################################",
    "### Starting Data Migration for: 'C:\temp\old_study'",
    "######################################################`n",
    "[1/4: Patch Configs] Executing: python src/patch_old_runs.py C:\temp\old_study",
    "Step '1/4: Patch Configs' completed successfully.",
    "",
    "[2/4: Rebuild Reports] Executing: python src/rebuild_reports.py C:\temp\old_study",
    "Step '2/4: Rebuild Reports' completed successfully.",
    "",
    "[3/4: Clean Artifacts] Cleaning up old and temporary files...",
    " - Deleting old 'final_summary_results.csv'",
    " - Deleting '*.corrupted' reports and old 'analysis_inputs' directories...",
    "Step '3/4: Clean Artifacts' completed successfully.",
    "",
    "[4/4: Final Reprocess] Executing: python src/replication_manager.py --reprocess C:\temp\old_study",
    "Step '4/4: Final Reprocess' completed successfully.",
    "",
    "######################################################",
    "### Migration Finished Successfully! ###",
    "######################################################`n"
)

# Test 4: Successful run on a clean directory with no old artifacts to delete.
Run-Test "Successful run with no artifacts to clean" {
    $script:mockPDMDetected = $true
    $script:mockLASTEXITCODE_Global = 0
    $script:mockFileSystem = @{
        "$targetDir" = $true;
        "$targetDir\run_001" = $true; # Directory exists but no deletable files within
    }
    Test-MigrateExperimentMainLogic -TargetDirectory $targetDir
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "`n######################################################",
    "### Starting Data Migration for: 'C:\temp\old_study'",
    "######################################################`n",
    "[1/4: Patch Configs] Executing: pdm run python src/patch_old_runs.py C:\temp\old_study",
    "Step '1/4: Patch Configs' completed successfully.",
    "",
    "[2/4: Rebuild Reports] Executing: pdm run python src/rebuild_reports.py C:\temp\old_study",
    "Step '2/4: Rebuild Reports' completed successfully.",
    "",
    "[3/4: Clean Artifacts] Cleaning up old and temporary files...",
    " - Deleting '*.corrupted' reports and old 'analysis_inputs' directories...",
    "Step '3/4: Clean Artifacts' completed successfully.",
    "",
    "[4/4: Final Reprocess] Executing: pdm run python src/replication_manager.py --reprocess C:\temp\old_study",
    "Step '4/4: Final Reprocess' completed successfully.", # <-- CORRECTED THIS LINE
    "",
    "######################################################",
    "### Migration Finished Successfully! ###",
    "######################################################`n"
)

# --- Final Test Summary ---
Write-Host "--- Test Summary ---" -ForegroundColor Blue
Write-Host "Tests Passed: $($totalTests - $testFailures)" -ForegroundColor Green
Write-Host "Tests Failed: $($testFailures)" -ForegroundColor Red
Write-Host "Total Tests: $($totalTests)" -ForegroundColor Blue

if ($testFailures -gt 0) { exit 1 } else { exit 0 }
