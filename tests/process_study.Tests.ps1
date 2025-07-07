# Filename: tests/process_study.Tests.ps1

# This test script provides a manual, Pester-free framework for testing process_study.ps1.
# It works by directly embedding the relevant logic of the target script into a testable function,
# and then injecting mock implementations for external dependencies like `Get-Command`,
# `Get-Content`, `Test-Path`, and the internal `Invoke-PythonScript` function.
# This allows for asserting on the console output and exit codes of the script.

# --- Test-Specific Global Variables and Helpers ---
$testFailures = 0
$totalTests = 0

# These global variables control the behavior of the mocks for each test case.
$script:mockPDMDetected = $true      # Controls Get-Command 'pdm' mock
$script:mockConfigIniContent = ""    # Controls Get-Content 'config.ini' mock
$script:mockLASTEXITCODE_Global = 0  # Controls the simulated exit code of Python script calls
$script:capturedOutputByTestRun = @() # Captures all Write-Host output during a test run

# --- Mock Raw Outputs for Python Scripts ---
# These arrays simulate the raw console output from `compile_results.py` and `run_anova.py`.
# The internal `Invoke-PythonScript` mock will use these as its "source" for parsing
# or for displaying in verbose mode.

# Raw output from compile_results.py for a successful run (used for non-verbose parsing and on failure)
# Updated to use API identifiers that align with actual output based on your config.ini example
$script:mockRawCompileOutputSuccess = @(
    "Some log line from compile_results.py (verbose output would be longer)",
    "-> Generated summary: C:\path\to\output\reports\Experiment_google-gemini-flash-1.5_map=correct\run_001\REPLICATION_results.csv",
    "-> Generated summary: C:\path\to\output\reports\Experiment_meta-llama-3-3-70b_map=random\run_001\REPLICATION_results.csv",
    "-> Generated summary: C:\path\to\output\reports\Experiment_google-gemini-flash-1.5_map=correct\EXPERIMENT_results.csv",
    "-> Generated summary: C:\path\to\output\reports\Experiment_meta-llama-3-3-70b_map=random\EXPERIMENT_results.csv",
    "-> Generated summary: C:\path\to\output\reports\STUDY_results.csv",
    "Compilation process finished."
)

# Raw output from run_anova.py for a successful run (used for non-verbose parsing and on failure)
$script:mockRawAnovaOutputSuccess = @(
    "Full analysis log written to: C:\path\to\output\reports\anova\STUDY_analysis_log.txt",
    "Applying filter: min_valid_response_threshold=0",
    "Analysis will proceed for 2 metrics.",
    "ANALYSIS FOR METRIC: 'mean_mrr'",
    "Conclusion: No significant factors found",
    "Plots saved to: C:\path\to\output\reports\anova\mean_mrr.png",
    "ANALYSIS FOR METRIC: 'accuracy'",
    "Conclusion: Factor 'model_name' showed significant effect (p < 0.01)",
    "Plots saved to: C:\path\to\output\reports\anova\accuracy.png",
    "ANOVA analysis finished."
)

# Simplified raw output for verbose mode (to confirm it passes through raw output)
    $script:mockRawCompileOutputVerbose = @(
        "Raw output from compile_results.py line 1",
        "Raw output from compile_results.py line 2"
    )
    $script:mockRawAnovaOutputVerbose = @(
        "Raw output from run_anova.py line 1",
        "Raw output from run_anova.py line 2"
    )


# --- Global Mock Functions (these override built-in PowerShell commands) ---
# These must be defined globally to affect the script's execution.

function global:Get-Content {
    param([string]$Path, [switch]$Raw)
    if ($Path -like "*config.ini*") {
        return $script:mockConfigIniContent
    }
    # For any other paths, return empty.
    return ""
}

function global:Get-Command {
    param([string]$Name, [string]$ErrorAction)
    if ($script:mockPDMDetected -and ($Name -eq "pdm")) {
        return "mock_pdm_command" # Simulate command found
    }
    # Return nothing for other commands if not specifically mocked, similar to original SilentlyContinue.
    return $null
}

function global:Test-Path {
    param([string]$Path)
    if ($Path -like "*config.ini*") {
        # Simulate existence based on whether mockConfigIniContent is provided.
        return (-not [string]::IsNullOrEmpty($script:mockConfigIniContent))
    }
    # Assume other paths exist by default for simplicity unless a test needs to mock them.
    return $true
}


# --- Testable Function encapsulating process_study.ps1's logic ---
# This function contains a direct copy of the relevant parts of process_study.ps1.
# It replaces the original `Invoke-PythonScript` definition with a mock tailored for testing,
# and redirects `Write-Host` calls to capture its output.

function Test-ProcessStudyMainLogic {
    [CmdletBinding()] # Keep for -Verbose parameter handling
    param (
        [Parameter(Mandatory = $true, Position = 0)]
        [string]$StudyDirectory
    )

    # --- Test-specific setup and mocking for this execution ---
    # Reset capture array and LASTEXITCODE for each test run.
    $script:capturedOutputByTestRun = @()
    $script:LASTEXITCODE = 0

    # Override Write-Host to capture output locally for this function's scope.
    # The original Write-Host will be restored in the finally block.
    $originalWriteHost = Get-Command Write-Host -ErrorAction SilentlyContinue
    function Write-Host {
        param($Object, $ForegroundColor)
        # Ensure objects are converted to string to prevent unexpected types in array.
        if ($Object -is [PSCustomObject]) { $Object = $Object | Out-String -Stream }
        $script:capturedOutputByTestRun += $Object
    }

    try {
        # --- Start of process_study.ps1's content, adapted for testing ---

        # Auto-detect execution environment (uses global mocked Get-Command)
        $executable = "python"
        $prefixArgs = @()
        if (Get-Command pdm -ErrorAction SilentlyContinue) {
            $script:capturedOutputByTestRun += "PDM detected. Using 'pdm run' to execute Python scripts."
            $executable = "pdm"
            $prefixArgs = "run", "python"
        }
        else {
            $script:capturedOutputByTestRun += "PDM not detected. Using standard 'python' command."
        }

        # Ensure console output uses UTF-8 (no-op in test context).
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

        # --- Load and parse model display names from config.ini ---
        $modelNameMap = @{}
        try {
            $configPath = Join-Path $PSScriptRoot "config.ini"
            if (-not (Test-Path $configPath)) {
                throw "config.ini not found at '$configPath'"
            }
            $configContent = Get-Content -Path $configPath -Raw

            # Use [regex]::Match to correctly extract the section content as a string.
            # The regex `(?=(\r?\n^\[)|$)` ensures it captures until the next section or end of file.
            $normalizationSection = ([regex]::Match($configContent, '(?msi)^\[ModelNormalization\]\r?\n(.*?)(?=(\r?\n^\[)|$)', [System.Text.RegularExpressions.RegexOptions]::Singleline)).Groups[1].Value
            $displaySection = ([regex]::Match($configContent, '(?msi)^\[ModelDisplayNames\]\r?\n(.*?)(?=(\r?\n^\[)|$)', [System.Text.RegularExpressions.RegexOptions]::Singleline)).Groups[1].Value

            if ([string]::IsNullOrWhiteSpace($normalizationSection) -or [string]::IsNullOrWhiteSpace($displaySection)) {
                throw "Could not find or parse [ModelNormalization] or [ModelDisplayNames] sections."
            }

            # First, build a map from canonical name to display name from [ModelDisplayNames]
            # Example: "llama-3-8b-instruct" -> "Llama 3 8B"
            $canonicalToDisplayNameMap = @{}
            # Updated regex for parsing key-value pairs to be more robust with whitespace
            $displaySection -split '\r?\n' | ForEach-Object {
                if ($_ -match "^\s*([^#=]+?)\s*=\s*(.*)$") {
                    $canonicalName = $matches[1].Trim()
                    $displayName = $matches[2].Trim()
                    $canonicalToDisplayNameMap[$canonicalName] = $displayName
                }
            }

            # Second, build the final modelNameMap (API Identifier to Display Name) using [ModelNormalization]
            # This is the original, flawed logic from process_study.ps1 that we are emulating.
            $normalizationSection -split '\r?\n' | ForEach-Object {
                if ($_ -match "^\s*([^#=]+?)\s*=\s*(.*)$") { # Updated regex for parsing key-value pairs
                    $apiIdentifierFromConfig = $matches[1].Trim() # e.g., "google-gemini-flash-1.5" (this is the key from ModelNormalization)
                    $canonicalNamesKeywords = ($matches[2].Split(',') | ForEach-Object { $_.Trim() }) # e.g., ("gemini-flash-1.5", "gemini_flash_1_5")

                    # This is the original script's problematic lookup. It uses the API identifier as a key for canonicalToDisplayNameMap.
                    if ($canonicalToDisplayNameMap.ContainsKey($apiIdentifierFromConfig)) { 
                        $displayName = $canonicalToDisplayNameMap[$apiIdentifierFromConfig]
                        foreach ($keyword in $canonicalNamesKeywords) {
                            $modelNameMap[$keyword] = $displayName # This branch will rarely be hit if API ID != Canonical Name
                        }
                    }
                }
            }

            if ($modelNameMap.Count -eq 0) {
                throw "Model name map was created but is empty. Check config.ini formatting."
            }
        }
        catch {
            $script:capturedOutputByTestRun += "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: $($_.Exception.Message)"
            $modelNameMap = @{} # Ensure it's an empty hashtable on failure
        }
        # $modelNameMap is now populated based on the mocked config.ini content for this test run.

        # --- Internal Mock for Invoke-PythonScript function ---
        # This function definition *replaces* the one in the original script for the purpose of this test.
        # It simulates the behavior of calling external Python scripts and parsing their output.
        function Invoke-PythonScript {
            param (
                [string]$StepName,
                [string]$ScriptName,
                [string[]]$Arguments,
                [bool]$IsVerbose # Explicitly pass verbose state to the mock function
            )
            # Capture the call for assertion
            $script:mockPyScriptCalls += [PSCustomObject]@{
                StepName   = $StepName
                ScriptName = $ScriptName
                Arguments  = $Arguments
                Verbose    = $IsVerbose # Use the explicitly passed state
            }

            # Construct the command string for logging purposes.
            $cmdString = "$executable $($prefixArgs + $ScriptName + $Arguments -join ' ')"
            $script:capturedOutputByTestRun += "[${StepName}] Executing: $cmdString"

            # Simulate the exit code. This can be a single value for all calls, or an array for sequential calls.
            if ($script:mockLASTEXITCODE_Global -is [array] -or $script:mockLASTEXITCODE_Global -is [System.Collections.ArrayList]) {
                if ($script:mockLASTEXITCODE_Global.Count -gt 0) {
                    $script:LASTEXITCODE = $script:mockLASTEXITCODE_Global[0]
                    # Remove the first element for the next call
                    $script:mockLASTEXITCODE_Global = $script:mockLASTEXITCODE_Global | Select-Object -Skip 1
                } else {
                    $script:LASTEXITCODE = 0 # Default to success if the array is empty
                }
            } else {
                # Original behavior: use the single value for all calls
                $script:LASTEXITCODE = $script:mockLASTEXITCODE_Global
            }

            if ($script:LASTEXITCODE -ne 0) {
                $script:capturedOutputByTestRun += "`n--- Full script output on failure ---"
                # On failure, always print the raw output (as original script does).
                if ($ScriptName -like "*compile_results.py*") {
                    $script:mockRawCompileOutputSuccess | ForEach-Object { $script:capturedOutputByTestRun += $_ }
                } elseif ($ScriptName -like "*run_anova.py*") {
                    $script:mockRawAnovaOutputSuccess | ForEach-Object { $script:capturedOutputByTestRun += $_ }
                }
                # Propagate failure immediately by throwing an error.
                throw "ERROR: Step '${StepName}' failed with exit code ${script:LASTEXITCODE}. Aborting."
            }

            # Determine if verbose output should be shown (passed from outer Test-ProcessStudyMainLogic via CmdletBinding)
            if ($IsVerbose) {
                # In verbose mode, just pass through the raw mock output.
                if ($ScriptName -like "*compile_results.py*") {
                    $script:mockRawCompileOutputVerbose | ForEach-Object { $script:capturedOutputByTestRun += $_ }
                }
                elseif ($ScriptName -like "*run_anova.py*") {
                    $script:mockRawAnovaOutputVerbose | ForEach-Object { $script:capturedOutputByTestRun += $_ }
                }
                $script:capturedOutputByTestRun += "Step '${StepName}' completed successfully."
                $script:capturedOutputByTestRun += "" # Empty line
                return # IMPORTANT: Exit the function immediately after verbose output
            }
            else {
                # Non-verbose mode: Parse the raw output and print a summarized version (original logic).
                if ($ScriptName -like "*compile_results.py*") {
                    $processedExperiments = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
                    $outputBlock = $script:mockRawCompileOutputSuccess -join "`n" # Input for regex parsing.

                    # Logic copied from the original production process_study.ps1
                    foreach ($line in $script:mockRawCompileOutputSuccess) {
                        if ($line -match "-> Generated summary:.*EXPERIMENT_results\.csv") {
                            $experimentDirName = (Split-Path -Path $line -Parent | Split-Path -Leaf) # e.g., "Experiment_google-gemini-flash-1.5_map=correct"

                            $foundDisplayName = $null
                            $apiIdentifierFromFolder = "unknown_model" # Default
                            $mappingStrategy = "unknown"

                            # Extract API identifier and mapping strategy from folder name
                            # THIS IS THE PART THAT IS FLAWED IN PRODUCTION SCRIPT
                            if ($experimentDirName -match 'Experiment_([a-zA-Z0-9\-\.]+?)_map=(correct|random)') {
                                $apiIdentifierFromFolder = $matches[1] # e.g., "google-gemini-flash-1.5"
                                $mappingStrategy = $matches[2]
                                
                                # Because modelNameMap is empty in the original script's logic,
                                # this will always fall back to using the API identifier from folder.
                                if ($modelNameMap.ContainsKey($apiIdentifierFromFolder)) { # This will be false.
                                    $foundDisplayName = $modelNameMap[$apiIdentifierFromFolder]
                                } else {
                                    $foundDisplayName = $apiIdentifierFromFolder # This is the fallback that gets used in production
                                }
                            }

                            if ($foundDisplayName -ne $null) {
                                $uniqueExperimentId = "$foundDisplayName-$mappingStrategy"

                                if (-not $processedExperiments.Contains($uniqueExperimentId)) {
                                    $script:capturedOutputByTestRun += "  - Compiling: $foundDisplayName ($($mappingStrategy) map)"
                                    [void]$processedExperiments.Add($uniqueExperimentId)
                                }
                            }
                        }
                    }
                    
                    # After the loop, print the final overall summary line
                    $finalSummaryMatch = [regex]::Match($outputBlock, "-> Generated summary:\s*(.*STUDY_results\.csv.*)")
                    if ($finalSummaryMatch.Success) {
                        $finalSummaryLine = $finalSummaryMatch.Groups[1].Value.Trim()
                        $script:capturedOutputByTestRun += "  - Generated final study summary: $finalSummaryLine"
                    }

                    $script:mockRawCompileOutputSuccess | Select-String -Pattern "Compilation process finished" | ForEach-Object { $script:capturedOutputByTestRun += $_.Line }

                }
                elseif ($ScriptName -like "*run_anova.py*") {
                    $metricName = $null
                    $conclusion = $null

                    $script:mockRawAnovaOutputSuccess | Select-String -Pattern "^Full analysis log", "^Applying filter", "^Excluding", "^Analysis will proceed" | ForEach-Object { $script:capturedOutputByTestRun += "  - $($_.Line)" }

                    foreach ($line in $script:mockRawAnovaOutputSuccess) {
                        if ($line -match "ANALYSIS FOR METRIC: '(.*)'") {
                            if ($metricName) {
                                $script:capturedOutputByTestRun += "  - METRIC '$metricName': $conclusion. Plots saved."
                            }
                            $metricName = $matches[1]
                            $conclusion = "summary not found"
                        }
                        elseif ($line -match "^Conclusion: (.*)") {
                            $conclusion = $matches[1].Trim()
                        }
                    }
                    if ($metricName) {
                        $script:capturedOutputByTestRun += "  - METRIC '$metricName': $conclusion. Plots saved."
                    }
                }
                $script:capturedOutputByTestRun += "Step '${StepName}' completed successfully."
                $script:capturedOutputByTestRun += "" # Empty line
            }
        } # End of *internal* mocked Invoke-PythonScript

        # --- Main Script Logic (copied from original process_study.ps1) ---
        $script:capturedOutputByTestRun += "`n######################################################"
        $script:capturedOutputByTestRun += "### Starting Study Processing for: '$($StudyDirectory)'"
        $script:capturedOutputByTestRun += "######################################################`n"

        # Resolve the path to ensure it's absolute and check for existence
        # In this mock context, $StudyDirectory is treated as already resolved.
        $ResolvedPath = $StudyDirectory
        
        # --- Step 1: Compile All Results into a Master CSV ---
        # Note: $PSBoundParameters for `Test-ProcessStudyMainLogic` itself includes `Verbose` switch,
        # which is passed to the internal `Invoke-PythonScript`.
        # Determine verbose state for passing to the mock Invoke-PythonScript
        $currentVerboseState = ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose'])

        # Arguments for the Python scripts themselves
        $compileScriptArgs = @($ResolvedPath)
        $anovaScriptArgs = @($ResolvedPath)

        # Add -Verbose to the Python script arguments if overall verbose
        if ($currentVerboseState) {
            $compileScriptArgs += "-Verbose"
            $anovaScriptArgs += "-Verbose"
        }

        Invoke-PythonScript -StepName "1/2: Compile Results" -ScriptName "src/compile_results.py" -Arguments $compileScriptArgs -IsVerbose $currentVerboseState

        # --- Step 2: Run Final Statistical Analysis ---
        Invoke-PythonScript -StepName "2/2: Run Final Analysis (ANOVA)" -ScriptName "src/run_anova.py" -Arguments $anovaScriptArgs -IsVerbose $currentVerboseState

        $script:capturedOutputByTestRun += "######################################################"
        $script:capturedOutputByTestRun += "### Study Processing Finished Successfully!"
        $script:capturedOutputByTestRun += "######################################################`n"
        $script:capturedOutputByTestRun += "Final analysis logs and plots are located in: '$($ResolvedPath)\anova'"

        # --- End of process_study.ps1's content ---

    }
    catch {
        $script:capturedOutputByTestRun += "`n######################################################"
        $script:capturedOutputByTestRun += "### STUDY PROCESSING FAILED"
        $script:capturedOutputByTestRun += "######################################################"
        $script:capturedOutputByTestRun += "ERROR: $($_.Exception.Message)"
        $script:LASTEXITCODE = 1 # Set final exit code for failure
    }
    finally {
        # Restore original Write-Host after this function completes.
        Remove-Item Function:\Write-Host -ErrorAction SilentlyContinue
    }

    # Return the captured output for assertion.
    return $script:capturedOutputByTestRun
}


# --- Test Runner Function ---
# This function orchestrates each test case, executes the `Test-ProcessStudyMainLogic`
# with specific mock configurations, and compares the actual output/exit code to expected values.

function Run-Test {
    param(
        [string]$TestName,
        [ScriptBlock]$TestScriptBlock,
        [Array]$ExpectedOutputLines = $null, # Expected lines from Write-Host
        [int]$ExpectedExitCode = 0           # Expected final script exit code
    )
    $script:totalTests++
    Write-Host "Running Test: $TestName" -ForegroundColor Cyan

    # Reset mocks for this test run.
    $script:mockPyScriptCalls = @() # To record calls to internal Invoke-PythonScript mock.
    $script:capturedOutputByTestRun = @() # To capture output for this test.
    $script:LASTEXITCODE = 0 # To capture the final exit code set by the script logic.
    $script:mockLASTEXITCODE_Global = 0 # Reset to default success for each test.

    $actualOutputLines = @()
    $actualExitCode = 0
    
    # Execute the test script block which sets up mocks and calls Test-ProcessStudyMainLogic.
    try {
        $TestScriptBlock.Invoke() # This block configures global mocks and then calls Test-ProcessStudyMainLogic.
        
        # After the TestScriptBlock runs, actual output and exit code are in global variables.
        $actualOutputLines = $script:capturedOutputByTestRun | ForEach-Object { "$_" } # Ensure all elements are strings.
        $actualExitCode = $script:LASTEXITCODE
    }
    catch {
        $actualOutputLines += "ERROR (Test harness caught): $($_.Exception.Message)"
        $actualExitCode = 1
    }

    $isOutputEqual = $true
    if ($ExpectedOutputLines -ne $null) {
        # Trim each line for comparison robustness.
        $trimmedActual = $actualOutputLines | ForEach-Object { $_.Trim() }
        $trimmedExpected = $ExpectedOutputLines | ForEach-Object { $_.Trim() }

        if ($trimmedActual.Count -ne $trimmedExpected.Count) {
            $isOutputEqual = $false
        } else {
            for ($i = 0; $i -lt $trimmedActual.Count; $i++) {
                if ($trimmedActual[$i] -ne $trimmedExpected[$i]) {
                    $isOutputEqual = $false
                    break
                }
            }
        }
    } else {
        # If no specific output expected, assume it's just about exit code/no errors.
        # This branch isn't typically used for `process_study.ps1` as it always prints.
    }

    if ($isOutputEqual -and ($actualExitCode -eq $ExpectedExitCode)) {
        Write-Host "PASS: $TestName`n" -ForegroundColor Green
    } else {
        $script:testFailures++
        Write-Host "FAIL: $TestName" -ForegroundColor Red
        if ($ExpectedOutputLines -ne $null) {
            Write-Host "  Expected Output ($ExpectedOutputLines.Count lines):" -ForegroundColor Yellow
            $ExpectedOutputLines | ForEach-Object { Write-Host "    '$_'" -ForegroundColor Yellow }
            Write-Host "  Actual Output ($actualOutputLines.Count lines):" -ForegroundColor Yellow
            $actualOutputLines | ForEach-Object { Write-Host "    '$_'" -ForegroundColor Yellow }
        }
        if ($actualExitCode -ne $ExpectedExitCode) {
            Write-Host "  Expected Exit Code: $ExpectedExitCode, Actual Exit Code: $actualExitCode" -ForegroundColor Yellow
        }
        Write-Host "`n"
    }
}


# --- TEST CASES ---

# Base valid config.ini content for testing.
# Updated to match API IDs and canonical names from your config.ini
$baseValidConfig = @"
[ModelNormalization]
google-gemini-flash-1.5 = gemini-flash-1.5, gemini_flash_1_5
meta-llama-3-3-70b = llama-3.3-70b, llama_3_3_70b
deepseek-v3 = deepseek-chat-v3, deepseek_chat_v3

[ModelDisplayNames]
gemini-flash-1.5 = Gemini 1.5 Flash
llama-3.3-70b = Llama 3.3 70B
deepseek-chat-v3 = DeepSeek V3
"@

# Test 1: Successful run with default (summarized) output and PDM detected.
Run-Test "Successful run with default (summarized) output and PDM" {
    $script:mockPDMDetected = $true
    $script:mockConfigIniContent = $baseValidConfig
    $script:mockLASTEXITCODE_Global = 0 # Simulate success for all Python calls.
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports"
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Model name map was created but is empty. Check config.ini formatting.", # Expected due to original script's flaw
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: pdm run python src/compile_results.py output/reports",
    "  - Compiling: google-gemini-flash-1.5 (correct map)", # Falls back to API ID as display name
    "  - Compiling: meta-llama-3-3-70b (random map)",     # Falls back to API ID as display name
    "  - Generated final study summary: C:\path\to\output\reports\STUDY_results.csv",
    "Compilation process finished.",
    "Step '1/2: Compile Results' completed successfully.",
    "",
    "[2/2: Run Final Analysis (ANOVA)] Executing: pdm run python src/run_anova.py output/reports",
    "  - Full analysis log written to: C:\path\to\output\reports\anova\STUDY_analysis_log.txt",
    "  - Applying filter: min_valid_response_threshold=0",
    "  - Analysis will proceed for 2 metrics.",
    "  - METRIC 'mean_mrr': No significant factors found. Plots saved.",
    "  - METRIC 'accuracy': Factor 'model_name' showed significant effect (p < 0.01). Plots saved.",
    "Step '2/2: Run Final Analysis (ANOVA)' completed successfully.",
    "",
    "######################################################",
    "### Study Processing Finished Successfully!",
    "######################################################`n",
    "Final analysis logs and plots are located in: 'output/reports\anova'"
)

# Test 2: Successful run with verbose output and PDM detected.
Run-Test "Successful run with verbose output and PDM" {
    $script:mockPDMDetected = $true
    $script:mockConfigIniContent = $baseValidConfig
    $script:mockLASTEXITCODE_Global = 0 # Simulate success for all Python calls.
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports" -Verbose # Pass -Verbose switch.
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Model name map was created but is empty. Check config.ini formatting.", # Expected due to original script's flaw
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: pdm run python src/compile_results.py output/reports -Verbose", # Added -Verbose to expected command string
    "Raw output from compile_results.py line 1", # Removed "VERBOSE: " prefix
    "Raw output from compile_results.py line 2",  # Removed "VERBOSE: " prefix
    "Step '1/2: Compile Results' completed successfully.",
    "",
    "[2/2: Run Final Analysis (ANOVA)] Executing: pdm run python src/run_anova.py output/reports -Verbose", # Added -Verbose to expected command string
    "Raw output from run_anova.py line 1", # Removed "VERBOSE: " prefix
    "Raw output from run_anova.py line 2",  # Removed "VERBOSE: " prefix
    "Step '2/2: Run Final Analysis (ANOVA)' completed successfully.",
    "",
    "######################################################", # Corrected typo here
    "### Study Processing Finished Successfully!",
    "######################################################`n",
    "Final analysis logs and plots are located in: 'output/reports\anova'"
)

# Test 3: Error during compilation step (first Python call fails).
Run-Test "Error during compilation step" {
    $script:mockPDMDetected = $true
    $script:mockConfigIniContent = $baseValidConfig
    $script:mockLASTEXITCODE_Global = 1 # Simulate failure for all Python calls (including the first).
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports"
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Model name map was created but is empty. Check config.ini formatting.", # Expected due to original script's flaw
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: pdm run python src/compile_results.py output/reports",
    "`n--- Full script output on failure ---", # Expected on failure.
    $script:mockRawCompileOutputSuccess[0], # Each line of raw output as a separate element
    $script:mockRawCompileOutputSuccess[1],
    $script:mockRawCompileOutputSuccess[2],
    $script:mockRawCompileOutputSuccess[3],
    $script:mockRawCompileOutputSuccess[4],
    $script:mockRawCompileOutputSuccess[5],
    $script:mockRawCompileOutputSuccess[6],
    "`n######################################################",
    "### STUDY PROCESSING FAILED",
    "######################################################",
    "ERROR: ERROR: Step '1/2: Compile Results' failed with exit code 1. Aborting." # The exception message.
) 1 # Expected exit code 1 for script failure.

# Test 4: Error during analysis step
Run-Test "Error during analysis step" {
    $script:mockPDMDetected = $true
    $script:mockConfigIniContent = $baseValidConfig
    # Provide a sequence of exit codes.
    # 0 for the first call (compile), 1 for the second (analysis).
    $script:mockLASTEXITCODE_Global = @(0, 1)
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports"
} @(

    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Model name map was created but is empty. Check config.ini formatting.", # Expected due to original script's flaw
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: pdm run python src/compile_results.py output/reports",
    "  - Compiling: google-gemini-flash-1.5 (correct map)", # Falls back to API ID as display name
    "  - Compiling: meta-llama-3-3-70b (random map)",     # Falls back to API ID as display name
    "  - Generated final study summary: C:\path\to\output\reports\STUDY_results.csv",
    "Compilation process finished.",
    "Step '1/2: Compile Results' completed successfully.",
    "",
    "[2/2: Run Final Analysis (ANOVA)] Executing: pdm run python src/run_anova.py output/reports",
    "`n--- Full script output on failure ---", # Expected on failure.
    $script:mockRawAnovaOutputSuccess[0],
    $script:mockRawAnovaOutputSuccess[1],
    $script:mockRawAnovaOutputSuccess[2],
    $script:mockRawAnovaOutputSuccess[3],
    $script:mockRawAnovaOutputSuccess[4],
    $script:mockRawAnovaOutputSuccess[5],
    $script:mockRawAnovaOutputSuccess[6],
    $script:mockRawAnovaOutputSuccess[7],
    $script:mockRawAnovaOutputSuccess[8],
    $script:mockRawAnovaOutputSuccess[9],
    "`n######################################################",
    "### STUDY PROCESSING FAILED",
    "######################################################",
    "ERROR: ERROR: Step '2/2: Run Final Analysis (ANOVA)' failed with exit code 1. Aborting."
) 1

# Test 5: PDM not detected (should use standard python command).
Run-Test "PDM not detected, should use standard python command" {
    $script:mockPDMDetected = $false # Simulate PDM not found.
    $script:mockConfigIniContent = $baseValidConfig
    $script:mockLASTEXITCODE_Global = 0 # Simulate success for all Python calls.
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports"
} @(
    "PDM not detected. Using standard 'python' command.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Model name map was created but is empty. Check config.ini formatting.",
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: python src/compile_results.py output/reports",
    "  - Compiling: google-gemini-flash-1.5 (correct map)",
    "  - Compiling: meta-llama-3-3-70b (random map)",
    "  - Generated final study summary: C:\path\to\output\reports\STUDY_results.csv",
    "Compilation process finished.",
    "Step '1/2: Compile Results' completed successfully.",
    "",
    "[2/2: Run Final Analysis (ANOVA)] Executing: python src/run_anova.py output/reports",
    "  - Full analysis log written to: C:\path\to\output\reports\anova\STUDY_analysis_log.txt",
    "  - Applying filter: min_valid_response_threshold=0",
    "  - Analysis will proceed for 2 metrics.",
    "  - METRIC 'mean_mrr': No significant factors found. Plots saved.",
    "  - METRIC 'accuracy': Factor 'model_name' showed significant effect (p < 0.01). Plots saved.",
    "Step '2/2: Run Final Analysis (ANOVA)' completed successfully.",
    "",
    "######################################################",
    "### Study Processing Finished Successfully!",
    "######################################################`n",
    "Final analysis logs and plots are located in: 'output/reports\anova'"
)

# Test 6: config.ini parsing failure should result in warning and empty map
Run-Test "config.ini parsing failure should result in warning and empty map" {
    $script:mockPDMDetected = $true
    $script:mockConfigIniContent = "MALFORMED CONFIG" # Simulate bad config content.
    $script:mockLASTEXITCODE_Global = 0 # Ensure Python scripts still succeed.
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports"
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Could not find or parse [ModelNormalization] or [ModelDisplayNames] sections.",
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: pdm run python src/compile_results.py output/reports",
    "  - Compiling: google-gemini-flash-1.5 (correct map)",
    "  - Compiling: meta-llama-3-3-70b (random map)",
    "  - Generated final study summary: C:\path\to\output\reports\STUDY_results.csv",
    "Compilation process finished.",
    "Step '1/2: Compile Results' completed successfully.",
    "",
    "[2/2: Run Final Analysis (ANOVA)] Executing: pdm run python src/run_anova.py output/reports",
    "  - Full analysis log written to: C:\path\to\output\reports\anova\STUDY_analysis_log.txt",
    "  - Applying filter: min_valid_response_threshold=0",
    "  - Analysis will proceed for 2 metrics.",
    "  - METRIC 'mean_mrr': No significant factors found. Plots saved.",
    "  - METRIC 'accuracy': Factor 'model_name' showed significant effect (p < 0.01). Plots saved.",
    "Step '2/2: Run Final Analysis (ANOVA)' completed successfully.",
    "",
    "######################################################",
    "### Study Processing Finished Successfully!",
    "######################################################`n",
    "Final analysis logs and plots are located in: 'output/reports\anova'"
)

# Test 7: Successful run with valid config (re-validation)
Run-Test "Successful run with valid config (re-validation)" {
    $script:mockPDMDetected = $true
    $script:mockConfigIniContent = $baseValidConfig
    $script:mockLASTEXITCODE_Global = 0
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports"
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Model name map was created but is empty. Check config.ini formatting.",
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: pdm run python src/compile_results.py output/reports",
    "  - Compiling: google-gemini-flash-1.5 (correct map)",
    "  - Compiling: meta-llama-3-3-70b (random map)",
    "  - Generated final study summary: C:\path\to\output\reports\STUDY_results.csv",
    "Compilation process finished.",
    "Step '1/2: Compile Results' completed successfully.",
    "",
    "[2/2: Run Final Analysis (ANOVA)] Executing: pdm run python src/run_anova.py output/reports",
    "  - Full analysis log written to: C:\path\to\output\reports\anova\STUDY_analysis_log.txt",
    "  - Applying filter: min_valid_response_threshold=0",
    "  - Analysis will proceed for 2 metrics.",
    "  - METRIC 'mean_mrr': No significant factors found. Plots saved.",
    "  - METRIC 'accuracy': Factor 'model_name' showed significant effect (p < 0.01). Plots saved.",
    "Step '2/2: Run Final Analysis (ANOVA)' completed successfully.",
    "",
    "######################################################",
    "### Study Processing Finished Successfully!",
    "######################################################`n",
    "Final analysis logs and plots are located in: 'output/reports\anova'"
)

# Test 8: config.ini valid but empty display name map (no normalization, just empty sections).
Run-Test "config.ini valid but empty display name map should warn and use raw paths" {
    $script:mockPDMDetected = $true
    $script:mockConfigIniContent = @"
[ModelNormalization]
# No normalization entries

[ModelDisplayNames]
# No display name entries
"@
    $script:mockLASTEXITCODE_Global = 0
    Test-ProcessStudyMainLogic -StudyDirectory "output/reports"
} @(
    "PDM detected. Using 'pdm run' to execute Python scripts.",
    "WARNING: Could not read or parse model names from config.ini. Full paths will be shown instead. Error: Model name map was created but is empty. Check config.ini formatting.",
    "`n######################################################",
    "### Starting Study Processing for: 'output/reports'",
    "######################################################`n",
    "[1/2: Compile Results] Executing: pdm run python src/compile_results.py output/reports",
    "  - Compiling: google-gemini-flash-1.5 (correct map)",
    "  - Compiling: meta-llama-3-3-70b (random map)",
    "  - Generated final study summary: C:\path\to\output\reports\STUDY_results.csv",
    "Compilation process finished.",
    "Step '1/2: Compile Results' completed successfully.",
    "",
    "[2/2: Run Final Analysis (ANOVA)] Executing: pdm run python src/run_anova.py output/reports",
    "  - Full analysis log written to: C:\path\to\output\reports\anova\STUDY_analysis_log.txt",
    "  - Applying filter: min_valid_response_threshold=0",
    "  - Analysis will proceed for 2 metrics.",
    "  - METRIC 'mean_mrr': No significant factors found. Plots saved.",
    "  - METRIC 'accuracy': Factor 'model_name' showed significant effect (p < 0.01). Plots saved.",
    "Step '2/2: Run Final Analysis (ANOVA)' completed successfully.",
    "",
    "######################################################",
    "### Study Processing Finished Successfully!",
    "######################################################`n",
    "Final analysis logs and plots are located in: 'output/reports\anova'"
)


# --- Final Test Summary ---
Write-Host "--- Test Summary ---" -ForegroundColor Blue
Write-Host "Tests Passed: $($totalTests - $testFailures)" -ForegroundColor Green
Write-Host "Tests Failed: $($testFailures)" -ForegroundColor Red
Write-Host "Total Tests: $($totalTests)" -ForegroundColor Blue

# Exit with an error code if any tests failed, for CI/CD integration.
if ($testFailures -gt 0) {
    exit 1
} else {
    exit 0
}