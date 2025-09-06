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
            "-o", $tempFile
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
    Test-StepContinuity "Raw ADB Data" (Join-Path $SandboxDir "data/sources/adb_raw_export.txt") 1 "`t" $AllSubjects
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

    # Capture the output, but do not display it live. We will control the messaging.
    $rawOutput = & $prepareDataScript -Force -NoFinalReport -SilentHalt 2>&1
    $pipelinePart1ExitCode = $LASTEXITCODE
    
    Remove-Item Env:PROJECT_SANDBOX_PATH -ErrorAction SilentlyContinue

    # Check if this is an expected manual step halt or an actual failure
    # Manual halt occurs when we reach the Solar Fire step and the SF import file exists
    $sfImportFile = Join-Path $SandboxDir "data/intermediate/sf_data_import.txt"
    $isExpectedManualHalt = $pipelinePart1ExitCode -eq 1 -and (Test-Path $sfImportFile)

    if ($pipelinePart1ExitCode -eq 0) {
        Write-Host "`n--- Pipeline completed successfully. Test finished. ---" -ForegroundColor Green
        return
    } elseif ($pipelinePart1ExitCode -ne 0 -and -not $isExpectedManualHalt) {
        throw "Pipeline Part 1 failed with exit code $pipelinePart1ExitCode. Check output above for details."
    } elseif ($isExpectedManualHalt) {
        # Manually print the headers for the simulated steps for a clean log flow.
        $stepHeader9 = ">>> Step 9/13: Solar Fire Processing <<<"; $stepHeader10 = ">>> Step 10/13: Delineation Export <<<"; $stepHeader11 = ">>> Step 11/13: Neutralize Delineations <<<"
        Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader9 -ForegroundColor Blue; Write-Host "Simulating the manual Solar Fire import, calculation, and chart export process." -ForegroundColor Blue
        Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader10 -ForegroundColor Blue; Write-Host "Simulating the one-time Solar Fire delineation library export." -ForegroundColor Blue
        Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader11 -ForegroundColor Blue; Write-Host "Using pre-neutralized text from test assets." -ForegroundColor Blue
        
        Write-Host "`n--- Proceeding with simulation... ---"
        
        # Validate each completed step in Part 1
        Test-StepContinuity "Wikipedia Links" (Join-Path $SandboxDir "data/processed/adb_wiki_links.csv") 1 "," $AllSubjects
        Test-StepContinuity "Page Validation" (Join-Path $SandboxDir "data/reports/adb_validation_report.csv") 1 "," $AllSubjects
        Test-StepContinuity "Eligible Candidates" (Join-Path $SandboxDir "data/intermediate/adb_eligible_candidates.txt") 1 "`t" $FinalSubjects
        if ($TestProfile.ConfigOverrides["bypass_candidate_selection"] -ne "true") {
            Test-StepContinuity "Eminence Scores" (Join-Path $SandboxDir "data/foundational_assets/eminence_scores.csv") 1 "," $FinalSubjects
            Test-StepContinuity "OCEAN Scores" (Join-Path $SandboxDir "data/foundational_assets/ocean_scores.csv") 1 "," $FinalSubjects
        }
        Test-StepContinuity "Final Candidates" (Join-Path $SandboxDir "data/intermediate/adb_final_candidates.txt") 1 "`t" $FinalSubjects
        Test-StepContinuity "SF Import" $sfImportFile 3 "," $FinalSubjects
    }
    # --- 3. Harness Interventions & Manual Step Simulation ---
    if ($TestProfile.InterventionScript) { & $TestProfile.InterventionScript -SandboxDir $SandboxDir }
    Write-Host "`n--- HARNESS: Simulating manual Solar Fire export... ---" -ForegroundColor Magenta
    $idMap = @{}; Get-Content (Join-Path $SandboxDir "data/intermediate/sf_data_import.txt") | ForEach-Object { $f = $_.Split(',') | ForEach-Object { $_.Trim('"') }; if ($f.Length -ge 4) { $idMap[$f[0]] = $f[3] } }
    $destAssetDir = Join-Path $SandboxDir "data/foundational_assets"
    $chartExportContent = (@"
"Ernst (1900) Busch","22 Jan 1900","0:15","ID_BUSCH","-1:00","Kiel","Germany","54N20","010E08"; "Body Name","Body Abbr","Longitude";"Moon","Mon",189.002;"Sun","Sun",301.513;"Mercury","Mer",289.248;"Venus","Ven",332.342;"Mars","Mar",300.143;"Jupiter","Jup",244.946;"Saturn","Sat",270.067;"Uranus","Ura",251.194;"Neptune","Nep",84.700;"Pluto","Plu",74.934;"Ascendant","Asc",200.157;"Midheaven","MC",117.655
"Paul McCartney","18 Jun 1942","14:00","ID_MCCARTNEY","-2:00","Liverpool","United Kingdom","53N25","002W55"; "Body Name","Body Abbr","Longitude";"Moon","Mon",137.438;"Sun","Sun",86.608;"Mercury","Mer",78.361;"Venus","Ven",48.992;"Mars","Mar",122.680;"Jupiter","Jup",91.832;"Saturn","Sat",65.208;"Uranus","Ura",61.968;"Neptune","Nep",177.119;"Pluto","Plu",124.270;"Ascendant","Asc",175.307;"Midheaven","MC",83.737
"Jonathan Cainer","18 Dec 1957","8:00","ID_CAINER","+0:00","London","United Kingdom","51N30","000W10"; "Body Name","Body Abbr","Longitude";"Moon","Mon",229.370;"Sun","Sun",266.145;"Mercury","Mer",281.204;"Venus","Ven",308.785;"Mars","Mar",236.738;"Jupiter","Jup",206.650;"Saturn","Sat",257.858;"Uranus","Ura",131.237;"Neptune","Nep",214.121;"Pluto","Plu",152.279;"Ascendant","Asc",264.205;"Midheaven","MC",208.521
"@ -replace ";", "`r`n").Trim()
    foreach ($key in $idMap.Keys) { $chartExportContent = $chartExportContent -replace "ID_$($key.Split(' ')[-1].ToUpper())", $idMap[$key] }
    $chartExportContent | Set-Content -Path (Join-Path $destAssetDir "sf_chart_export.csv") -Encoding UTF8
    @"
*Quadrant Strong 1st
A focus on self-awareness and personal identity.
*Hemisphere Strong East
A self-motivated and independent nature.
*Aries Strong
Assertive and pioneering.
*Element Strong Water
Compassionate and caring with a strong intuitional nature.
*Mode Strong Cardinal
Enjoys challenge and action.
*Sun in Capricorn
Serious and responsible.
*Moon in Leo
A love for being the center of attention.
*Mercury in Sagittarius
A search for knowledge to expand the worldview.
*Venus in Sagittarius
A desire to share adventure with a partner.
*Mars in Aquarius
A drive to fight for just causes.
*Jupiter in Pisces
An intuitive search for truth.
*Saturn in Sagittarius
A potential commitment to higher education.
*Uranus in Leo
A seeking of freedom for individual expression.
*Neptune in Libra
An ability to view relationships holistically.
*Pluto in Leo
An ability to use power both positively and negatively.
*Ascendant in Virgo
A cautious approach to life.
*Midheaven in Gemini
A need for stimulation in professional life.
"@ | Set-Content -Path (Join-Path $destAssetDir "sf_delineations_library.txt") -Encoding UTF8
    Write-Host "  -> Placed simulated SF files into sandbox."
    Test-StepContinuity "SF Export" (Join-Path $destAssetDir "sf_chart_export.csv") 3 "," $FinalSubjects

    # --- 4. Execute Pipeline (Part 2): Resume and complete ---
    Write-Host "`n--- EXECUTING PIPELINE (Part 2): Resuming pipeline with simulated manual files... ---" -ForegroundColor Cyan
    $env:PROJECT_SANDBOX_PATH = $SandboxDir
    
    # The pipeline should automatically resume from where it left off
    # Use a hashtable for splatting to correctly handle switch parameters
    $resumeArgs = @{ NoFinalReport = $true; Resumed = $true }
    if ($Interactive) { 
        $resumeArgs.Interactive = $true 
    }

    # Capture and filter the output to suppress the final "success" banner
    $rawOutputP2 = & $prepareDataScript @resumeArgs 2>&1
    $pipelineOutputP2 = $rawOutputP2 | Where-Object { $_ -notmatch "Data Preparation Pipeline Completed Successfully" }
    $pipelineOutputP2 | ForEach-Object { Write-Host $_ }
    
    Remove-Item Env:PROJECT_SANDBOX_PATH -ErrorAction SilentlyContinue

    # --- 5. Final Verification ---
    Write-Host "`n--- VERIFYING: Checking final output... ---" -ForegroundColor Cyan
    $finalDbPath = Join-Path $SandboxDir "data/processed/personalities_db.txt"
    if (-not (Test-Path $finalDbPath)) { throw "FAIL: The final 'personalities_db.txt' file was not created." }
    Test-StepContinuity "Final Database" $finalDbPath 1 -SubjectsToCheck $FinalSubjects
    $lineCount = (Get-Content $finalDbPath).Length
    if ($lineCount -ne $TestProfile.ExpectedFinalLineCount) { throw "FAIL: Expected $($TestProfile.ExpectedFinalLineCount) lines, but found $lineCount." }
    Write-Host "`nPASS: The final 'personalities_db.txt' was created with the correct number of lines for this profile." -ForegroundColor Green
}
catch {
    throw "Layer 3 test workflow failed.`n$($_.Exception.Message)"
}