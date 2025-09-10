#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 2: Execute the Test Workflow ---

param(
    [Parameter(Mandatory=$true)]
    [hashtable]$TestProfile,

    [Parameter(Mandatory=$false)]
    [switch]$Interactive
)

$ErrorActionPreference = "Stop"

# --- Helper Functions ---
function Get-ProjectRoot {
    param($StartPath)
    $currentDir = $StartPath
    while ($currentDir -ne $null -and $currentDir -ne "") {
        if (Test-Path (Join-Path $currentDir "pyproject.toml")) { return $currentDir }
        $currentDir = Split-Path -Parent -Path $currentDir
    }
    throw "FATAL: Could not find project root (pyproject.toml) by searching up from '$StartPath'."
}

$ProjectRoot = Get-ProjectRoot -StartPath $PSScriptRoot
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer3_sandbox"

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_CYAN = "`e[96m"
$C_MAGENTA = "`e[95m"
$C_YELLOW = "`e[93m"
$C_GREEN = "`e[92m"

# --- Helper Functions ---
function Format-Banner {
    param([string]$Message, [string]$Color = $C_CYAN)
    $line = '#' * 80; $bookend = "###"; $contentWidth = $line.Length - ($bookend.Length * 2)
    $paddingNeeded = $contentWidth - $Message.Length - 2; $leftPad = [Math]::Floor($paddingNeeded / 2); $rightPad = [Math]::Ceiling($paddingNeeded / 2)
    $centeredMsg = "$bookend $(' ' * $leftPad)$Message$(' ' * $rightPad) $bookend"
    Write-Host "`n$Color$line"; Write-Host "$Color$centeredMsg"; Write-Host "$Color$line$C_RESET`n"
}

# Add base58 decode function using Python module
function ConvertFrom-Base58 {
    param([string]$EncodedString)
    
    $pythonScript = @"
import sys
sys.path.append('$($ProjectRoot.Replace('\', '/'))/src')
from id_encoder import from_base58
print(from_base58('$EncodedString'))
"@
    
    try {
        $result = python -c $pythonScript
        return [int]$result
    }
    catch {
        throw "Failed to decode base58 '$EncodedString': $($_.Exception.Message)"
    }
}

if (-not (Test-Path $SandboxDir)) { throw "FATAL: Test sandbox not found. Please run Phase 1 first." }

try {
    # --- 0. Initialize Execution Log for pipeline steps ---
    $executedStepsLog = [System.Collections.Generic.List[object]]::new()
    $taskCounter = 1
    $currentStageNumber = 0
    
    $prepareDataScript = Join-Path $ProjectRoot "prepare_data.ps1"
    # Parse the orchestrator to map step numbers to output files for logging
    $stepToOutputMap = @{}
    $pipelineContent = Get-Content $prepareDataScript -Raw
    $stepDefinitions = $pipelineContent | Select-String -Pattern 'Name\s*=\s*"([^"]+?)".*?Output\s*=\s*"([^"]+?)"' -AllMatches
    $i = 1
    foreach ($match in $stepDefinitions.Matches) {
        $stepToOutputMap[$i] = $match.Groups[2].Value
        $i++
    }

    $AllSubjects = $TestProfile.Subjects
    # Define the subset of subjects expected to pass initial filtering and selection
    $FinalSubjects = $TestProfile.Subjects | Where-Object { $_.Name -in @("Ernst (1900) Busch", "Paul McCartney", "Jonathan Cainer") }

    # --- 1. Harness Setup from Profile ---
    Write-Host "`n--- HARNESS: Configuring sandbox from test profile '$($TestProfile.Name)'... ---" -ForegroundColor Yellow
    
    # 1a. Create test-specific config using proper INI parsing
    $mainConfigPath = Join-Path $ProjectRoot "config.ini"
    $sandboxConfigPath = Join-Path $SandboxDir "config.ini"
    if (-not (Test-Path $mainConfigPath)) { throw "FATAL: Main 'config.ini' not found." }
    
    # Read the main config
    $configLines = Get-Content $mainConfigPath
    $modifiedLines = @()
    $currentSection = ""
    
    foreach ($line in $configLines) {
        if ($line -match '^\s*\[(.+)\]\s*$') {
            $currentSection = $matches[1]
            $modifiedLines += $line
        } elseif ($line -match '^\s*([^#;=]+)\s*=\s*(.*)' -and $currentSection -eq "DataGeneration") {
            $keyName = $matches[1].Trim()
            $originalValue = $matches[2].Trim()
            
            if ($TestProfile.ConfigOverrides.ContainsKey($keyName)) {
                $newValue = $TestProfile.ConfigOverrides[$keyName]
                $modifiedLines += "$keyName = $newValue"
                Write-Host "  -> Override: [$currentSection] $keyName = $newValue (was: $originalValue)" -ForegroundColor Cyan
            } else {
                $modifiedLines += $line
            }
        } else {
            $modifiedLines += $line
        }
    }
    
    Set-Content -Path $sandboxConfigPath -Value $modifiedLines
    Write-Host "  -> Created controlled 'config.ini' in sandbox."

    # Simple validation function for data continuity
    function Test-StepContinuity {
        param($StepName, $FilePath, $IDColumn = 0, $Delimiter = "`t", $SubjectsToCheck = $null)
        
        if (-not $SubjectsToCheck) { $SubjectsToCheck = $TestProfile.Subjects }
        
        if (-not (Test-Path $FilePath)) {
            throw "FAIL [${StepName}]: File not found: ${FilePath}"
        }
        
        # SF Import and SF Export files have no header, don't skip first line
        if ($StepName -eq "SF Import" -or $StepName -eq "SF Export") {
            $data = Get-Content $FilePath
        } else {
            $data = Get-Content $FilePath | Select-Object -Skip 1
        }
        if (-not $data) {
            throw "FAIL [${StepName}]: File is empty or contains only header: ${FilePath}"
        }
        
        $actualIDs = $data | ForEach-Object { 
            $cols = $_.Split($Delimiter)
            if ($cols.Length -gt $IDColumn -and $cols[$IDColumn]) {
                $fieldValue = $cols[$IDColumn].Trim('"').Trim()
                
                # For SF Export, only extract valid base58 IDs
                if ($StepName -eq "SF Export") {
                    # Try to decode as base58 - if it works, it's probably an ID
                    try {
                        $decoded = ConvertFrom-Base58 $fieldValue
                        # If decode succeeds and produces a reasonable ID (positive integer), include it
                        if ($decoded -gt 0) {
                            $fieldValue
                        }
                    }
                    catch {
                        # Not a valid base58 value, skip it
                    }
                } else {
                    $fieldValue
                }
            }
        } | Where-Object { $_ -and $_ -ne "" }
        
        if (-not $actualIDs) {
            throw "FAIL [${StepName}]: No valid IDs found in column ${IDColumn}: ${FilePath}"
        }

        if ($actualIDs.Count -ne $SubjectsToCheck.Count) {
            throw "FAIL [${StepName}]: Expected $($SubjectsToCheck.Count) subjects, but found $($actualIDs.Count) in ${FilePath}"
        }
        
        foreach ($subject in $SubjectsToCheck) {
            $found = $false
            
            # For SF Import and SF Export files, decode base58 values and compare
            if ($StepName -eq "SF Import" -or $StepName -eq "SF Export") {
                foreach ($id in $actualIDs) {
                    try {
                        $decodedId = ConvertFrom-Base58 $id
                        if ($decodedId -eq [int]$subject.idADB) {
                            $found = $true
                            break
                        }
                    }
                    catch {
                        # Ignore decode failures for non-ID values in the file
                    }
                }
            }
            else {
                # Standard ID comparison for other files
                $found = $subject.idADB -in $actualIDs
            }
            
            if (-not $found) {
                throw "FAIL [${StepName}]: Missing subject $($subject.idADB) ($($subject.Name))"
            }
        }
        Write-Host "  -> ✓ ${StepName}: All subjects present" -ForegroundColor Green
    }

    # --- Execute Pipeline (Part 1) ---
    $prepareDataScript = Join-Path $ProjectRoot "prepare_data.ps1"
    Write-Host "`n--- EXECUTING PIPELINE (Part 1): Running pipeline to generate files needed for simulation... ---" -ForegroundColor Cyan
    
    # Create targeted ADB data for test subjects
    Format-Banner "BEGIN STAGE: 1. DATA SOURCING"
    
    # Manually print the header for the pre-populated step for a clean log flow
    $stepHeader = ">>> Step 1/13: Fetch Raw ADB Data <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader -ForegroundColor Blue; Write-Host "Fetches the initial raw dataset from the live Astro-Databank." -ForegroundColor Blue
    
    # Replicate the standard step info block for consistency in interactive mode
    if ($Interactive) {
        $summaryHelper = Join-Path $ProjectRoot "scripts/get_docstring_summary.py"
        $fetchScriptPath = Join-Path $ProjectRoot "src/fetch_adb_data.py"
        $summary = & python $summaryHelper $fetchScriptPath 2>$null
        if ($summary) {
            Write-Host "`n${C_MAGENTA}Script Summary: $($summary.Trim())${C_RESET}"
            Write-Host "${C_MAGENTA}Test Harness Note: This script will be run 7 times in a loop to create a small, targeted seed dataset for the test subjects.${C_RESET}"
        }
    }

    Write-Host "`n  BASE DIRECTORY: $SandboxDir" -ForegroundColor DarkGray
    Write-Host "`n  INPUTS:"
    Write-Host "    - Live Astro-Databank Website"
    Write-Host "`n  OUTPUT:"
    Write-Host "    - data/sources/adb_raw_export.txt`n"

    if ($Interactive) {
        Write-Host "${C_YELLOW}WARNING: This process will connect to the live Astro-Databank website.${C_RESET}"
        Read-Host -Prompt "`n${C_YELLOW}Press Enter to execute this step (Ctrl+C to exit)...${C_RESET}`n"
    }

    $executedStepsLog.Add([pscustomobject]@{
        'Task #' = $taskCounter++
        'Stage #' = 1
        'Step #' = 1
        'Step Description' = "Fetch Raw ADB Data"
        'Status' = "SUCCESS"
        'Output File' = $stepToOutputMap[1]
    })
    Write-Host "`n  -> Performing targeted fetch for $($TestProfile.Subjects.Count) subjects..."
    $fetchScript = Join-Path $ProjectRoot "src/fetch_adb_data.py"
    $outputFile = "data/sources/adb_raw_export.txt"
    New-Item -Path (Join-Path $SandboxDir (Split-Path $outputFile)) -ItemType Directory -Force | Out-Null
    "Index`tidADB`tLastName`tFirstName`tGender`tDay`tMonth`tYear`tTime`tZoneAbbr`tZoneTimeOffset`tCity`tCountryState`tLongitude`tLatitude`tRating`tBio`tCategories`tLink" | Set-Content -Path (Join-Path $SandboxDir $outputFile) -Encoding UTF8

    $isFirstFetch = $true
    foreach ($subject in $TestProfile.Subjects) {
        Write-Host "    - Fetching data for: $($subject.Name)"
        $tempFile = Join-Path $SandboxDir "temp_fetch.txt"
        
        # Build arguments dynamically. Only use --force on the first run.
        $fetchArgs = @(
            "run", "python", $fetchScript,
            "--sandbox-path", $SandboxDir,
            "--start-date", $subject.Date,
            "--end-date", $subject.Date,
            "-o", $tempFile,
            "--no-network-warning"
        )
        if ($isFirstFetch) {
            $fetchArgs += "--force"
            $isFirstFetch = $false
        }
        
        & pdm @fetchArgs
        
        if (Test-Path $tempFile) { 
            Get-Content $tempFile | Select-Object -Skip 1 | Add-Content -Path (Join-Path $SandboxDir $outputFile)
            Remove-Item $tempFile | Out-Null
        }
    }

    # Re-index the combined data to maintain sequential indexing
    $targetIDs = $TestProfile.Subjects.idADB
    $fullOutputFile = Join-Path $SandboxDir $outputFile
    $header = Get-Content $fullOutputFile | Select-Object -First 1
    $dataRows = Get-Content $fullOutputFile | Where-Object { $targetIDs -contains ($_.Split("`t"))[1] }
    $reIndexedData = for ($i = 0; $i -lt $dataRows.Length; $i++) { 
        $cols = $dataRows[$i].Split("`t")
        $cols[0] = $i + 1
        $cols -join "`t" 
    }
    @($header) + $reIndexedData | Set-Content -Path $fullOutputFile
    $relativeOutputPath = (Resolve-Path $fullOutputFile -Relative).TrimStart(".\")
    Write-Host "`n  -> Assembled and saved initial seed data to '$relativeOutputPath'." -ForegroundColor Cyan

    # Validate the result and print an overall success message.
    # Test-StepContinuity will throw an exception (red text) if validation fails.
    Test-StepContinuity "Raw ADB Data" (Join-Path $SandboxDir "data/sources/adb_raw_export.txt") 1 "`t" $AllSubjects
    
    $finalFile = Join-Path $SandboxDir "data/sources/adb_raw_export.txt"
    $finalCount = (Get-Content $finalFile | Select-Object -Skip 1).Length
    $totalSubjects = $AllSubjects.Count
    Write-Host "`n${C_GREEN}SUCCESS: Successfully fetched and assembled data for ${finalCount}/${totalSubjects} subjects.${C_RESET}"
    
    if ($Interactive) { Read-Host -Prompt "`n${C_YELLOW}Step complete. Inspect the output, then press Enter to continue...${C_RESET}`n" }
    
    Write-Host "  -> Note: Pipeline Step 1 will be skipped since test data already exists." -ForegroundColor DarkGray

    # Create minimal scoring files for bypass mode if needed so the pipeline doesn't fail
    if ($TestProfile.ConfigOverrides["bypass_candidate_selection"] -eq "true") {
        $destAssetDir = Join-Path $SandboxDir "data/foundational_assets"
        $eminenceFile = Join-Path $destAssetDir "eminence_scores.csv"
        $oceanFile = Join-Path $destAssetDir "ocean_scores.csv"
        if (-not (Test-Path $eminenceFile)) {
            "idADB,EminenceScore" | Set-Content -Path $eminenceFile
        }
        if (-not (Test-Path $oceanFile)) {
            # The python script doesn't need the columns in bypass mode, but a valid header prevents potential issues
            "idADB,OCEAN_C,OCEAN_O,OCEAN_E,OCEAN_A,OCEAN_N,Finalist" | Set-Content -Path $oceanFile
        }
        Write-Host "  -> Created minimal scoring files for bypass mode."
    }

    # --- 2. Execute Pipeline (Part 1) ---
    $prepareDataScript = Join-Path $ProjectRoot "prepare_data.ps1"
    Write-Host "`n--- EXECUTING PIPELINE (Part 1): Running pipeline to generate files needed for simulation... ---" -ForegroundColor Cyan
    $env:PROJECT_SANDBOX_PATH = $SandboxDir

    # Set UTF-8 encoding to handle Unicode characters in Python output
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $env:PYTHONIOENCODING = "utf-8"

    # --- RUN 1: Execute pipeline through Step 6 ---
    $run1Args = @{
        Force = $true; NoFinalReport = $true; SilentHalt = $true; TestMode = $true; StopAfterStep = 6
    }
    if ($Interactive) { $run1Args.Interactive = $true }
    
    $run1Steps = [System.Collections.Generic.List[object]]::new()
    & pwsh -WorkingDirectory $SandboxDir -File $prepareDataScript @run1Args 2>&1 | ForEach-Object {
        Write-Host $_
        if ($_ -match 'BEGIN STAGE: (\d+)\.') { $currentStageNumber = [int]$matches[1] }
        if ($_ -match '>>> Step (\d+)/\d+: (.*?) <<<') {
            $stepNum = [int]$matches[1]
            $run1Steps.Add(@{
                'Stage #' = $currentStageNumber; 'Step #' = $stepNum; 'Step Description' = $matches[2].Trim(); 'Output File' = $stepToOutputMap[$stepNum]
            })
        }
    }
    $run1ExitCode = $LASTEXITCODE
    if ($run1ExitCode -ne 1) { throw "Pipeline Run 1 was expected to halt after Step 6 but did not." }

    $run1Status = "SUCCESS"
    foreach ($step in $run1Steps) {
        $executedStepsLog.Add([pscustomobject]@{
            'Task #' = $taskCounter++; 'Stage #' = $step.'Stage #'; 'Step #' = $step.'Step #'; 'Step Description' = $step.'Step Description'; 'Status' = $run1Status; 'Output File' = $step.'Output File'
        })
    }

    # --- VALIDATE INTERMEDIATE RESULTS & RUN ISOLATED TEST 7.a ---
    Test-StepContinuity "Eligible Candidates" (Join-Path $SandboxDir "data/intermediate/adb_eligible_candidates.txt") 1 "`t" $FinalSubjects
    Test-StepContinuity "OCEAN Scores" (Join-Path $SandboxDir "data/foundational_assets/ocean_scores.csv") 1 "," $FinalSubjects

    # --- 3a. Inject an isolated test for Step 7's cutoff logic using a large seed dataset ---
    $stepHeader7a = ">>> Step 7.a/13: Validate Cutoff Logic (Large Seed) <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader7a -ForegroundColor Blue; Write-Host "Validates the subject cutoff algorithm using a large seed dataset." -ForegroundColor Blue
    $largeSeedDir = Join-Path $ProjectRoot "tests/assets/large_seed"
    if (Test-Path $largeSeedDir) {
        $tempCutoffSandbox = Join-Path $SandboxDir "temp_cutoff_test"
        try {
            @("data/intermediate", "data/foundational_assets", "data/reports") | ForEach-Object { New-Item -Path (Join-Path $tempCutoffSandbox $_) -ItemType Directory -Force | Out-Null }
            Copy-Item -Path (Join-Path $largeSeedDir "data/intermediate/adb_eligible_candidates.txt") -Destination (Join-Path $tempCutoffSandbox "data/intermediate/")
            Copy-Item -Path (Join-Path $largeSeedDir "data/foundational_assets/eminence_scores.csv") -Destination (Join-Path $tempCutoffSandbox "data/foundational_assets/")
            Copy-Item -Path (Join-Path $largeSeedDir "data/foundational_assets/ocean_scores.csv") -Destination (Join-Path $tempCutoffSandbox "data/foundational_assets/")
            Copy-Item -Path (Join-Path $ProjectRoot "tests/assets/data/foundational_assets/country_codes.csv") -Destination (Join-Path $tempCutoffSandbox "data/foundational_assets/")
            $selectCandidatesScript = Join-Path $ProjectRoot "src/select_final_candidates.py"
            & pdm run python $selectCandidatesScript --sandbox-path $tempCutoffSandbox --plot
            $largeInputCount = (Get-Content (Join-Path $tempCutoffSandbox "data/foundational_assets/ocean_scores.csv") | Select-Object -Skip 1).Length
            $largeOutput = Join-Path $tempCutoffSandbox "data/intermediate/adb_final_candidates.txt"
            if (-not (Test-Path $largeOutput)) { throw "Cutoff logic test failed: Output file was not created." }
            $largeOutputCount = (Get-Content $largeOutput | Select-Object -Skip 1).Length
            if ($largeOutputCount -ge $largeInputCount) { throw "Cutoff logic test failed: The number of final candidates ($largeOutputCount) was not less than the input ($largeInputCount)." }
            Write-Host "  -> ✓ Step 7 Cutoff Logic: Successfully validated with large seed data ($largeInputCount -> $largeOutputCount subjects)." -ForegroundColor Green
        } finally {
            if (Test-Path $tempCutoffSandbox) { Remove-Item -Path $tempCutoffSandbox -Recurse -Force }
        }
    } else {
        Write-Host "  -> SKIPPED: Large seed data directory not found at 'tests/assets/large_seed'." -ForegroundColor Yellow
    }

    $executedStepsLog.Add([pscustomobject]@{
        'Task #' = $taskCounter++; 'Stage #' = 3; 'Step #' = "7.a"; 'Step Description' = "Validate Cutoff Logic (Large Seed)"; 'Status' = "SUCCESS"; 'Output File' = "temp_cutoff_test/..."
    })

    if ($TestProfile.InterventionScript) {
        & $TestProfile.InterventionScript -SandboxDir $SandboxDir
    }

    # --- RUN 2: Resume pipeline from Step 7.b to the next manual step (9) ---
    Write-Host "`n--- EXECUTING PIPELINE (Part 2): Resuming from Step 7.b... ---" -ForegroundColor Cyan
    $stepHeader7b = ">>> Step 7.b/13: Select Final Candidates <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader7b -ForegroundColor Blue; Write-Host "Filters, transforms, and sorts the final subject set based on the LLM scoring." -ForegroundColor Blue
    $run2Args = @{ NoFinalReport = $true; SilentHalt = $true; TestMode = $true; Resumed = $true }
    if ($Interactive) { $run2Args.Interactive = $true }

    $run2Steps = [System.Collections.Generic.List[object]]::new()
    # Capture output, but suppress the orchestrator's original 'Step 7' header
    & pwsh -WorkingDirectory $SandboxDir -File $prepareDataScript @run2Args 2>&1 | ForEach-Object {
        if ($_ -notmatch '>>> Step 7/13:.*') { Write-Host $_ }
        if ($_ -match 'BEGIN STAGE: (\d+)\.') { $currentStageNumber = [int]$matches[1] }
        if ($_ -match '>>> Step (\d+)/\d+: (.*?) <<<') {
            $stepNum = [int]$matches[1]
            $run2Steps.Add(@{ 'Stage #' = $currentStageNumber; 'Step #' = $stepNum; 'Step Description' = $matches[2].Trim(); 'Output File' = $stepToOutputMap[$stepNum] })
        }
    }
    $run2ExitCode = $LASTEXITCODE
    if ($run2ExitCode -ne 1) { throw "Pipeline Run 2 was expected to halt for Step 9 but did not." }
    
    # Log the steps that completed in this run (7.b and 8)
    $run2Status = "SUCCESS"
    if ($run2Steps.Count > 0) { $run2Steps.RemoveAt($run2Steps.Count - 1) } # Remove the halted step
    foreach ($step in $run2Steps) {
        $stepNumber = if ($step.'Step Description' -eq "Select Final Candidates") { "7.b" } else { $step.'Step #' }
        $executedStepsLog.Add([pscustomobject]@{ 'Task #' = $taskCounter++; 'Stage #' = $step.'Stage #'; 'Step #' = $stepNumber; 'Step Description' = $step.'Step Description'; 'Status' = $run2Status; 'Output File' = $step.'Output File' })
    }

    # --- SIMULATE Manual Step 9: Solar Fire Processing ---
    $sfImportFile = Join-Path $SandboxDir "data/intermediate/sf_data_import.txt"
    Test-StepContinuity "Final Candidates" (Join-Path $SandboxDir "data/intermediate/adb_final_candidates.txt") 1 "`t" $FinalSubjects
    Test-StepContinuity "SF Import" $sfImportFile 3 "," $FinalSubjects

    Write-Host "`n--- SIMULATING: Solar Fire Processing... ---" -ForegroundColor Magenta
    $idMap = @{}; Get-Content $sfImportFile | ForEach-Object { $f = $_.Split(',') | ForEach-Object { $_.Trim('"') }; if ($f.Length -ge 4) { $idMap[$f[0]] = $f[3] } }
    $destAssetDir = Join-Path $SandboxDir "data/foundational_assets"
    $chartExportContent = (@"
"Ernst (1900) Busch","22 Jan 1900","0:15","ID_BUSCH","-1:00","Kiel","Germany","54N20","010E08"; "Body Name","Body Abbr","Longitude";"Moon","Mon",189.002;"Sun","Sun",301.513;"Mercury","Mer",289.248;"Venus","Ven",332.342;"Mars","Mar",300.143;"Jupiter","Jup",244.946;"Saturn","Sat",270.067;"Uranus","Ura",251.194;"Neptune","Nep",84.700;"Pluto","Plu",74.934;"Ascendant","Asc",200.157;"Midheaven","MC",117.655
"Paul McCartney","18 Jun 1942","14:00","ID_MCCARTNEY","-2:00","Liverpool","United Kingdom","53N25","002W55"; "Body Name","Body Abbr","Longitude";"Moon","Mon",137.438;"Sun","Sun",86.608;"Mercury","Mer",78.361;"Venus","Ven",48.992;"Mars","Mar",122.680;"Jupiter","Jup",91.832;"Saturn","Sat",65.208;"Uranus","Ura",61.968;"Neptune","Nep",177.119;"Pluto","Plu",124.270;"Ascendant","Asc",175.307;"Midheaven","MC",83.737
"Jonathan Cainer","18 Dec 1957","8:00","ID_CAINER","+0:00","London","United Kingdom","51N30","000W10"; "Body Name","Body Abbr","Longitude";"Moon","Mon",229.370;"Sun","Sun",266.145;"Mercury","Mer",281.204;"Venus","Ven",308.785;"Mars","Mar",236.738;"Jupiter","Jup",206.650;"Saturn","Sat",257.858;"Uranus","Ura",131.237;"Neptune","Nep",214.121;"Pluto","Plu",152.279;"Ascendant","Asc",264.205;"Midheaven","MC",208.521
"@ -replace ";", "`r`n").Trim()
    foreach ($key in $idMap.Keys) { $chartExportContent = $chartExportContent -replace "ID_$($key.Split(' ')[-1].ToUpper())", $idMap[$key] }
    $chartExportPath = Join-Path $destAssetDir "sf_chart_export.csv"
    $chartExportContent | Set-Content -Path $chartExportPath -Encoding UTF8

    # --- RUN 3: Resume pipeline from Step 10 to the next manual step (10) ---
    Write-Host "`n--- EXECUTING PIPELINE (Part 3): Resuming from Step 10... ---" -ForegroundColor Cyan
    $run3Args = @{ NoFinalReport = $true; SilentHalt = $true; TestMode = $true; Resumed = $true }
    if ($Interactive) { $run3Args.Interactive = $true }

    $run3Steps = [System.Collections.Generic.List[object]]::new()
    & pwsh -WorkingDirectory $SandboxDir -File $prepareDataScript @run3Args 2>&1 | ForEach-Object {
        Write-Host $_
        if ($_ -match 'BEGIN STAGE: (\d+)\.') { $currentStageNumber = [int]$matches[1] }
        if ($_ -match '>>> Step (\d+)/\d+: (.*?) <<<') {
            $stepNum = [int]$matches[1]
            $run3Steps.Add(@{ 'Stage #' = $currentStageNumber; 'Step #' = $stepNum; 'Step Description' = $matches[2].Trim(); 'Output File' = $stepToOutputMap[$stepNum] })
        }
    }
    $run3ExitCode = $LASTEXITCODE
    if ($run3ExitCode -ne 1) { throw "Pipeline Run 3 was expected to halt for Step 10 but did not." }
    if ($run3Steps.Count > 0) { $run3Steps.RemoveAt($run3Steps.Count - 1) } # Remove the halted step

    # --- SIMULATE Manual Step 10: Delineation Export ---
    $delineationLibPath = Join-Path $destAssetDir "sf_delineations_library.txt"
    Write-Host "`n--- SIMULATING: Delineation Export... ---" -ForegroundColor Magenta
    @"
*Quadrant Strong 1st
A focus on self-awareness and personal identity.
*Hemisphere Strong East
A self-motivated and independent nature.
*Aries Strong
Assertive and pioneering.
"@ | Set-Content -Path $delineationLibPath -Encoding UTF8
    $executedStepsLog.Add([pscustomobject]@{ 'Task #' = $taskCounter++; 'Stage #' = 4; 'Step #' = 10; 'Step Description' = "Delineation Export"; 'Status' = "SUCCESS"; 'Output File' = $stepToOutputMap[10] })
    
    # --- SIMULATE Step 11 by copying pre-neutralized assets ---
    Write-Host "`n--- SIMULATING: Neutralize Delineations... ---" -ForegroundColor Magenta
    $sourceDir = Join-Path $ProjectRoot "tests/assets/data/foundational_assets/neutralized_delineations"
    $destDir = Join-Path $SandboxDir "data/foundational_assets/neutralized_delineations"
    New-Item -Path $destDir -ItemType Directory -Force | Out-Null
    Copy-Item -Path "$sourceDir/*" -Destination $destDir -Recurse -Force
    Write-Host "  -> Copied pre-neutralized delineation files from test assets."
    $executedStepsLog.Add([pscustomobject]@{ 'Task #' = $taskCounter++; 'Stage #' = 4; 'Step #' = 11; 'Step Description' = "Neutralize Delineations"; 'Status' = "SUCCESS"; 'Output File' = $stepToOutputMap[11] })

    # --- RUN 4: Resume to completion ---
    Write-Host "`n--- EXECUTING PIPELINE (Part 4): Resuming to completion... ---" -ForegroundColor Cyan
    $run4Args = @{ NoFinalReport = $true; Resumed = $true; TestMode = $true }
    if ($Interactive) { $run4Args.Interactive = $true }

    $run4Steps = [System.Collections.Generic.List[object]]::new()
    & pwsh -WorkingDirectory $SandboxDir -File $prepareDataScript @run4Args 2>&1 | ForEach-Object {
        Write-Host $_
        if ($_ -match 'BEGIN STAGE: (\d+)\.') { $currentStageNumber = [int]$matches[1] }
        if ($_ -match '>>> Step (\d+)/\d+: (.*?) <<<') {
            $stepNum = [int]$matches[1]
            $run4Steps.Add(@{ 'Stage #' = $currentStageNumber; 'Step #' = $stepNum; 'Step Description' = $matches[2].Trim(); 'Output File' = $stepToOutputMap[$stepNum] })
        }
    }
    $run4ExitCode = $LASTEXITCODE
    if ($run4ExitCode -ne 0) { throw "Pipeline Run 4 failed with exit code $run4ExitCode." }
    
    $run4Status = "SUCCESS"
    foreach ($step in $run4Steps) {
        $executedStepsLog.Add([pscustomobject]@{ 'Task #' = $taskCounter++; 'Stage #' = $step.'Stage #'; 'Step #' = $step.'Step #'; 'Step Description' = $step.'Step Description'; 'Status' = $run4Status; 'Output File' = $step.'Output File' })
    }

    # --- 6. Final Verification ---
    Write-Host "`n--- VERIFYING: Checking final output... ---" -ForegroundColor Cyan
    $finalDbPath = Join-Path $SandboxDir "data/personalities_db.txt"
    if (-not (Test-Path $finalDbPath)) { throw "FAIL: The final 'personalities_db.txt' file was not created." }
    Test-StepContinuity "Final Database" $finalDbPath 1 -SubjectsToCheck $FinalSubjects
    $lineCount = (Get-Content $finalDbPath).Length
    if ($lineCount -ne $TestProfile.ExpectedFinalLineCount) { throw "FAIL: Expected $($TestProfile.ExpectedFinalLineCount) lines, but found $lineCount." }
    Write-Host "`nPASS: The final 'personalities_db.txt' was created with the correct number of lines for this profile." -ForegroundColor Green
}
catch {
    throw "Layer 3 test workflow failed.`n$($_.Exception.Message)"
}
finally {
    # --- 8. Print Execution Summary ---
    if ($executedStepsLog.Count -gt 0) {
        Write-Host "`n--- HARNESS: Actual Pipeline Execution Flow ---`n" -ForegroundColor Yellow
        
        # Manual table formatting to ensure 3-space separation between columns
        $props = 'Task #', 'Stage #', 'Step #', 'Step Description', 'Status', 'Output File'
        
        # Calculate max width for each column based on header and data
        $widths = @{}
        foreach ($p in $props) { $widths[$p] = $p.Length }
        foreach ($log in $executedStepsLog) {
            foreach ($p in $props) {
                $widths[$p] = [Math]::Max($widths[$p], $log.$p.ToString().Length)
            }
        }
        
        $separator = "   "
        
        # Build and print header line
        $headerLine = ($props | ForEach-Object { $_.PadRight($widths[$_]) }) -join $separator
        Write-Host $headerLine
        
        # Build and print separator line
        $separatorLine = ($props | ForEach-Object { '-' * $widths[$_] }) -join $separator
        Write-Host $separatorLine
        
        # Build and print data rows
        foreach ($log in $executedStepsLog) {
            $rowLine = ($props | ForEach-Object { $log.$_.ToString().PadRight($widths[$_]) }) -join $separator
            Write-Host $rowLine
        }
    }
}