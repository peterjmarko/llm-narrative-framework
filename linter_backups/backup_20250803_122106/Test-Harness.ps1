# Filename: tests/Test-Harness.ps1
# Description: A shared, bare-bones test harness for PowerShell scripts.

# --- Global Test Counters ---
# Use the script scope to ensure these variables are accessible within this file.
$script:testFailures = 0
$script:totalTests = 0

# --- Reusable Test Runner Function ---
function Run-Test {
    param(
        [string]$TestName,
        [ScriptBlock]$TestScriptBlock,
        [System.Collections.IEnumerable]$ExpectedResult
    )
    $script:totalTests++
    Write-Host "Running Test: $TestName" -ForegroundColor Cyan

    try {
        $actualResult = $TestScriptBlock.Invoke()

        # Robust array comparison
        $isEqual = $true
        if (($actualResult -isnot [System.Collections.IEnumerable]) -or ($ExpectedResult -isnot [System.Collections.IEnumerable]) -or ($actualResult.Count -ne $ExpectedResult.Count)) {
            $isEqual = $false
        } else {
            for ($i = 0; $i -lt $actualResult.Count; $i++) {
                if ($actualResult[$i] -ne $ExpectedResult[$i]) {
                    $isEqual = $false
                    break
                }
            }
        }

        if ($isEqual) {
            Write-Host "PASS: $TestName`n" -ForegroundColor Green
        } else {
            $script:testFailures++
            Write-Host "FAIL: $TestName" -ForegroundColor Red
            Write-Host "  Expected: $($ExpectedResult -join ' ')" -ForegroundColor Yellow
            Write-Host "  Actual:   $($actualResult -join ' ')" -ForegroundColor Yellow
            Write-Host "`n"
        }
    }
    catch {
        $script:testFailures++
        Write-Host "FAIL: $TestName" -ForegroundColor Red
        Write-Host "  Error: $($_.Exception.Message)`n" -ForegroundColor Red
    }
}

# --- Function to Print Summary and Set Exit Code ---
# This will be called at the end of each individual test script.
function Finalize-Test-Run {
    Write-Host "--- Test Summary ---" -ForegroundColor Blue
    Write-Host "Tests Passed: $($script:totalTests - $script:testFailures)" -ForegroundColor Green
    Write-Host "Tests Failed: $($script:testFailures)" -ForegroundColor Red
    Write-Host "Total Tests: $($script:totalTests)" -ForegroundColor Blue

    if ($script:testFailures -gt 0) {
        # This command sets the exit code for the current PowerShell process
        # without immediately terminating the entire shell, which is more robust.
        $host.SetShouldExit(1)
    }
}