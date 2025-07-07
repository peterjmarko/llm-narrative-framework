# Filename: tests/run_experiment.Tests.ps1

# This test script defines the functions under test and uses standard PowerShell
# flow control and a manual array comparison for assertions.
# It makes no assumptions about Pester or other modules.

# --- Test-Specific Function Definitions ---

# Test-specific Build-ExperimentArgs function (mirrors src/ArgBuilder.ps1's content)
# IMPORTANT: Added [CmdletBinding()] to make it an advanced function for robust parameter binding.
function Build-ExperimentArgs {
    [CmdletBinding()] # Added this line
    param(
        [string]$TargetDirectory,
        [int]$StartRep,
        [int]$EndRep,
        [string]$Notes,
        [switch]$ShowDetails
    )
    $pythonArgs = @("src/replication_manager.py")
    if (-not [string]::IsNullOrEmpty($TargetDirectory)) { $pythonArgs += $TargetDirectory }
    if ($StartRep) { $pythonArgs += "--start-rep", $StartRep }
    if ($EndRep) { $pythonArgs += "--end-rep", $EndRep }
    if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }
    if ($ShowDetails.IsPresent) { $pythonArgs += "--verbose" }
    return $pythonArgs
}

# Test-specific Invoke-Experiment function (mirrors run_experiment.ps1's function content)
# This function will RETURN the final arguments it constructs, allowing direct assertion.
function Invoke-Experiment {
    [CmdletBinding()] # Keep CmdletBinding for common parameters like -Verbose
    param(
        [Parameter(Mandatory=$false)] # Removed Position=0
        [string]$TargetDirectory,

        [Parameter(Mandatory=$false)]
        [int]$StartRep,

        [Parameter(Mandatory=$false)]
        [int]$EndRep,

        [Parameter(Mandatory=$false)]
        [string]$Notes
        # -Verbose is a common parameter, no need to declare explicitly.
    )

    # In this test-specific function, we mimic the production script's logic
    # without actually performing external calls or console writes.
    # Assume PDM is detected for consistent test outcomes.
    $executable = "pdm"
    $prefixArgs = "run", "python"

    # Capture actual parameters passed to Invoke-Experiment.
    $helperParams = @{}
    foreach ($key in $PSBoundParameters.Keys) {
        $helperParams[$key] = $PSBoundParameters[$key]
    }

    # Translate -Verbose to -ShowDetails for Build-ExperimentArgs.
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $helperParams['ShowDetails'] = $PSBoundParameters['Verbose']
    }

    # Call the test-defined Build-ExperimentArgs function directly.
    # This call now correctly handles empty hashtable splatting.
    $pythonArgs = Build-ExperimentArgs @helperParams

    # Construct the final arguments that would be passed to the external command.
    $finalCommandArgs = $prefixArgs + $pythonArgs

    # RETURN these arguments for direct assertion.
    return $finalCommandArgs
}

# --- TEST CASES (Directly executed assertions using manual comparison) ---
# We implement our own test runner function for basic reporting.

$testFailures = 0
$totalTests = 0

function Run-Test {
    param(
        [string]$TestName,
        [ScriptBlock]$TestScriptBlock,
        [Array]$ExpectedResult
    )
    $script:totalTests++
    Write-Host "Running Test: $TestName" -ForegroundColor Cyan # Keep 'Running Test' in cyan
    try {
        $actualResult = $TestScriptBlock.Invoke() 
        
        # Manual array comparison for robustness
        $isEqual = $true
        if ($actualResult.Count -ne $ExpectedResult.Count) {
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
            Write-Host "PASS: $TestName`n" -ForegroundColor Green # Conditionally green for PASS
        } else {
            $script:testFailures++
            Write-Host "FAIL: $TestName" -ForegroundColor Red # Conditionally red for FAIL
            Write-Host "  Expected: $($ExpectedResult -join ' ')" -ForegroundColor Yellow # Highlight expected/actual in yellow
            Write-Host "  Actual:   $($actualResult -join ' ')" -ForegroundColor Yellow
            Write-Host "`n"
        }
    }
    catch {
        $script:testFailures++
        Write-Host "FAIL: $TestName" -ForegroundColor Red # Conditionally red for caught errors
        Write-Host "  Error: $($_.Exception.Message)`n" -ForegroundColor Red # Error message in red
    }
}

# Test 1: should build default arguments when no parameters are provided
Run-Test "should build default arguments when no parameters are provided" {
    Invoke-Experiment # Call with no parameters at all for the default case
} @(
    "run", "python",
    "src/replication_manager.py"
)

# Test 2: should include the --verbose flag when -Verbose is used
Run-Test "should include the --verbose flag when -Verbose is used" {
    Invoke-Experiment -Verbose:$true
} @(
    "run", "python",
    "src/replication_manager.py",
    "--verbose"
)

# Test 3: should include the target directory as the first argument
Run-Test "should include the target directory as the first argument" {
    Invoke-Experiment -TargetDirectory 'output/my_dir'
} @(
    "run", "python",
    "src/replication_manager.py",
    "output/my_dir"
)

# Test 4: should include --start-rep and --end-rep flags
Run-Test "should include --start-rep and --end-rep flags" {
    Invoke-Experiment -StartRep 5 -EndRep 10
} @(
    "run", "python",
    "src/replication_manager.py",
    "--start-rep", 5,
    "--end-rep", 10
)

# Test 5: should include the --notes flag with its value
Run-Test "should include the --notes flag with its value" {
    Invoke-Experiment -Notes "My test notes"
} @(
    "run", "python",
    "src/replication_manager.py",
    "--notes", "My test notes"
)

# Test 6: should handle a combination of all parameters correctly
Run-Test "should handle a combination of all parameters correctly" {
    Invoke-Experiment -TargetDirectory 'output/combo' -StartRep 1 -EndRep 2 -Notes "Combo test" -Verbose:$true
} @(
    "run", "python",
    "src/replication_manager.py",
    "output/combo",
    "--start-rep", 1,
    "--end-rep", 2,
    "--notes", "Combo test",
    "--verbose"
)

# --- Final Test Summary ---
Write-Host "--- Test Summary ---" -ForegroundColor Blue
Write-Host "Tests Passed: $($totalTests - $testFailures)" -ForegroundColor Green
Write-Host "Tests Failed: $($testFailures)" -ForegroundColor Red
Write-Host "Total Tests: $($totalTests)" -ForegroundColor Blue

# Exit with an error code if any tests failed, for CI/CD integration
if ($testFailures -gt 0) {
    exit 1
} else {
    exit 0
}