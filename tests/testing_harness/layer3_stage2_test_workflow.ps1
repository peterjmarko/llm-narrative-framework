#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 2: Execute the Test Workflow ---

param(
    [Parameter(Mandatory=$false)]
    [switch]$Interactive
)

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer3_sandbox"
$relativeSandboxDir = (Resolve-Path $SandboxDir -Relative).TrimStart('.\')
$ErrorActionPreference = "Stop"

function Invoke-PipelineStep {
    param(
        [string]$ScriptName,
        [string]$Description,
        [string[]]$InputFiles,
        [string[]]$OutputFiles,
        [scriptblock]$Action
    )
    
    if ($Interactive) {
        $script:stepCounter = if ($script:stepCounter) { $script:stepCounter + 1 } else { 1 }
        $stepHeader = ">>> Step $($script:stepCounter): $ScriptName <<<"
        Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
        Write-Host $stepHeader -ForegroundColor Blue
        Write-Host $Description -ForegroundColor Blue
        Write-Host "`n  INPUTS:"
        $InputFiles | ForEach-Object {
            if ($_ -match "[\\/]") {
                Write-Host "    - $(Join-Path $relativeSandboxDir $_)"
            } else {
                Write-Host "    - $_"
            }
        }
        Write-Host "`n  OUTPUTS:"
        $OutputFiles | ForEach-Object {
            if ($_ -match "[\\/]") {
                Write-Host "    - $(Join-Path $relativeSandboxDir $_)"
            } else {
                Write-Host "    - $_"
            }
        }
        Write-Host "" # Add a blank line for spacing
        Read-Host -Prompt "Press Enter to execute this step (Ctrl+C to exit)..."
    }

    & $Action

    if ($Interactive) {
        Write-Host "" # Add a blank line for spacing
        Read-Host -Prompt "Step complete. Inspect the output files, then press Enter to continue (Ctrl+C to exit)..."
    }
}

if (-not (Test-Path $SandboxDir)) { throw "FATAL: Test sandbox not found. Please run Stage 1 first." }

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Stage 2: Execute the Test Workflow ---" -ForegroundColor Cyan

try {

    $fetchScript = Join-Path $ProjectRoot "src/fetch_adb_data.py"
    $outputFile = "data/sources/adb_raw_export.txt"

    # --- 1. Targeted Live Fetch ---
    Invoke-PipelineStep `
        -ScriptName "fetch_adb_data.py (Targeted Fetch)" `
        -Description "Performs a targeted live fetch from Astro-Databank to create the initial seed dataset." `
        -InputFiles @("Live Astro-Databank Website") `
        -OutputFiles @($outputFile) `
        -Action {
            Write-Host "`n--- Performing targeted live fetch for 7 test subjects... ---" -ForegroundColor Yellow
            
            New-Item -Path (Split-Path $outputFile) -ItemType Directory -Force | Out-Null
    "Index`tidADB`tLastName`tFirstName`tGender`tDay`tMonth`tYear`tTime`tZoneAbbr`tZoneTimeOffset`tCity`tCountryState`tLongitude`tLatitude`tRating`tBio`tCategories`tLink" | Set-Content -Path (Join-Path $SandboxDir $outputFile) -Encoding UTF8
    
    $subjects = @(
        # Control Group (Known Good)
        @{ Name = "Ernst (1900) Busch";          idADB = "52735";  Date = "1900-01-22" },
        @{ Name = "Paul McCartney";              idADB = "9129";   Date = "1942-06-18" },
        @{ Name = "Jonathan Cainer";             idADB = "42399";  Date = "1957-12-18" },
        # Failure Group (Targeted Failures)
        @{ Name = "Philip, Duke of Edinburgh";   idADB = "215";    Date = "1921-06-10" }, # Name Mismatch
        @{ Name = "Suicide: Gunshot 14259";      idADB = "14259";  Date = "1967-11-19" }, # Research Entry
        @{ Name = "Jonathan Renna";              idADB = "94360";  Date = "1979-04-28" }, # No Wikipedia Link Found
        @{ Name = "Romário Marques";             idADB = "101097"; Date = "1989-07-20" }  # Non-English Link (Simulated)
    )

    foreach ($subject in $subjects) {
        Write-Host "  -> Fetching data for $($subject.Name)..."
        $tempOutputFile = Join-Path $SandboxDir "temp_fetch_output.txt"
        
        # Run the fetch script. It may not create the output file if no subjects are found.
        pdm run python $fetchScript --sandbox-path $SandboxDir --start-date $subject.Date --end-date $subject.Date -o $tempOutputFile --force
        
        # Only process the temp file if the fetch script successfully created it.
        if (Test-Path $tempOutputFile) {
            $fetchedContent = Get-Content $tempOutputFile | Select-Object -Skip 1
            if ($fetchedContent) {
                Add-Content -Path (Join-Path $SandboxDir $outputFile) -Value $fetchedContent
            }
            Remove-Item $tempOutputFile
        } else {
            # This is an expected outcome for subjects that cannot be found.
            Write-Host "  -> NOTE: No data fetched for this subject (temp file not created)." -ForegroundColor Gray
        }
    }

    # CRITICAL: Filter the aggregated data to only our test subjects before proceeding.
    Write-Host "`n--- Filtering aggregated data to target subjects... ---" -ForegroundColor Yellow
    $targetIDs = $subjects.idADB
    
    $fullOutputFile = Join-Path $SandboxDir $outputFile
    $header = Get-Content $fullOutputFile | Select-Object -First 1
    $dataRows = Get-Content $fullOutputFile | Select-Object -Skip 1
    
    # Filter rows where the second column (idADB) is one of our target IDs.
    $filteredData = $dataRows | Where-Object { $targetIDs -contains ($_.Split("`t"))[1] }

    # Re-index the final filtered data to be sequential.
    $reIndexedData = for ($i = 0; $i -lt $filteredData.Length; $i++) {
        $line = $filteredData[$i]
        $columns = $line.Split("`t")
        $columns[0] = $i + 1
        $columns -join "`t"
    }
    
    # Construct the final content as a single array of strings for robust file writing.
    $finalContent = @($header) + $reIndexedData
    Set-Content -Path $fullOutputFile -Value $finalContent

    $displayPath = (Join-Path $PWD $fullOutputFile).Replace("$ProjectRoot" + [System.IO.Path]::DirectorySeparatorChar, "")
    $finalRecordCount = $reIndexedData.Length

    Write-Host "`n--- Final Output ---" -ForegroundColor Yellow
    Write-Host " - Raw data export saved to: $displayPath" -ForegroundColor Cyan
    $keyMetric = "Created initial dataset with $finalRecordCount subjects"
    Write-Host "`nSUCCESS: $keyMetric. Initial data fetch completed successfully. ✨`n" -ForegroundColor Green
        }

    # --- 2. Run the Automated Pipeline Scripts Sequentially ---
    Write-Host "`n--- Running automated data pipeline scripts... ---" -ForegroundColor Yellow
    
    # --- HARNESS INTERVENTION: Provide static data files... ---
    Write-Host "`n--- HARNESS INTERVENTION: Providing static data files... ---" -ForegroundColor Magenta
    $sourceAssetDir = Join-Path $ProjectRoot "data/foundational_assets"
    $destAssetDir = Join-Path $SandboxDir "data/foundational_assets"
    New-Item -Path $destAssetDir -ItemType Directory -Force | Out-Null
    Copy-Item -Path (Join-Path $sourceAssetDir "country_codes.csv") -Destination $destAssetDir
    Write-Host "  -> Copied 'country_codes.csv' into the sandbox."
    # The category map is created by the fetch script, but the link finder also needs it.
    # We must copy the master version into the sandbox to ensure it's available.
    Copy-Item -Path (Join-Path $sourceAssetDir "adb_category_map.csv") -Destination $destAssetDir
    Write-Host "  -> Copied 'adb_category_map.csv' into the sandbox."
    Copy-Item -Path (Join-Path $sourceAssetDir "point_weights.csv") -Destination $destAssetDir
    Write-Host "  -> Copied 'point_weights.csv' into the sandbox."
    Copy-Item -Path (Join-Path $sourceAssetDir "balance_thresholds.csv") -Destination $destAssetDir
    Write-Host "  -> Copied 'balance_thresholds.csv' into the sandbox."

    $scriptsToRun = @(
        "src/find_wikipedia_links.py",
        "src/validate_wikipedia_pages.py",
        "src/select_eligible_candidates.py",
        "src/generate_eminence_scores.py",
        "src/generate_ocean_scores.py",
        "src/select_final_candidates.py",
        "src/prepare_sf_import.py"
    )
    # Define file paths relative to the project root for clarity
    $adbRaw = "data/sources/adb_raw_export.txt"
    $wikiLinks = "data/processed/adb_wiki_links.csv"
    $validationReport = "data/reports/adb_validation_report.csv"
    $eligibleCandidates = "data/intermediate/adb_eligible_candidates.txt"
    $eminenceScores = "data/foundational_assets/eminence_scores.csv"
    $oceanScores = "data/foundational_assets/ocean_scores.csv"
    $finalCandidates = "data/intermediate/adb_final_candidates.txt"
    $sfImport = "data/intermediate/sf_data_import.txt"

    # Sequentially call each script
    Invoke-PipelineStep `
        -ScriptName "find_wikipedia_links.py" `
        -Description "Finds a best-guess Wikipedia URL for each subject." `
        -InputFiles @($adbRaw) `
        -OutputFiles @($wikiLinks) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/find_wikipedia_links.py") --sandbox-path $SandboxDir --force
        }

    Invoke-PipelineStep `
        -ScriptName "validate_wikipedia_pages.py" `
        -Description "Validates each Wikipedia page for content and language. Includes a harness intervention to inject known failures." `
        -InputFiles @($wikiLinks) `
        -OutputFiles @($validationReport) `
        -Action {
            # --- HARNESS INTERVENTION: Injecting validation failures... ---
            Write-Host "`n--- HARNESS INTERVENTION: Injecting validation failures... ---" -ForegroundColor Magenta
            $hirohitoID = "215"; $marquesID = "101097"; $rennaID = "94360"
            $modifiedLinks = (Get-Content (Join-Path $SandboxDir $wikiLinks)) | ForEach-Object {
                if ($_ -match ",$($hirohitoID),") { $_ } 
                elseif ($_ -match ",$($marquesID),") { $_ -replace "https://en.wikipedia.org/wiki/Rom%C3%A1rio", "https://fr.wikipedia.org/wiki/Rom%C3%A1rio" } 
                elseif ($_ -match ",$($rennaID),") { $_ -replace 'http[^,]*', '' } 
                else { $_ }
            }
            Set-Content -Path (Join-Path $SandboxDir $wikiLinks) -Value $modifiedLinks
            Write-Host "  -> Injected Non-English URL and No Link Found failures."
            pdm run python (Join-Path $ProjectRoot "src/validate_wikipedia_pages.py") --sandbox-path $SandboxDir --force
        }

    Invoke-PipelineStep `
        -ScriptName "select_eligible_candidates.py" `
        -Description "Performs initial data quality checks to create a pool of eligible candidates." `
        -InputFiles @($adbRaw, $validationReport) `
        -OutputFiles @($eligibleCandidates) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/select_eligible_candidates.py") --sandbox-path $SandboxDir --force
        }

    Invoke-PipelineStep `
        -ScriptName "generate_eminence_scores.py" `
        -Description "Generates a calibrated eminence score for each eligible candidate." `
        -InputFiles @($eligibleCandidates) `
        -OutputFiles @($eminenceScores) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/generate_eminence_scores.py") --sandbox-path $SandboxDir --force
        }

    Invoke-PipelineStep `
        -ScriptName "generate_ocean_scores.py" `
        -Description "Generates OCEAN scores and determines the final dataset size." `
        -InputFiles @($eminenceScores) `
        -OutputFiles @($oceanScores) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/generate_ocean_scores.py") --sandbox-path $SandboxDir --force
        }

    Invoke-PipelineStep `
        -ScriptName "select_final_candidates.py" `
        -Description "Filters, transforms, and sorts the final subject set." `
        -InputFiles @($eligibleCandidates, $oceanScores, $eminenceScores) `
        -OutputFiles @($finalCandidates) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/select_final_candidates.py") --sandbox-path $SandboxDir --force
        }

    Invoke-PipelineStep `
        -ScriptName "prepare_sf_import.py" `
        -Description "Formats the final subject list for import into Solar Fire." `
        -InputFiles @($finalCandidates) `
        -OutputFiles @($sfImport) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/prepare_sf_import.py") --sandbox-path $SandboxDir --force
        }

    # Checkpoint removed for cleaner logs. The next script's success implies this one worked.
    
    # --- 3. Dynamic Simulation of Manual Steps ---
    Write-Host "`n--- Simulating Manual Solar Fire Export Steps... ---" -ForegroundColor Cyan
    $importFile = Join-Path $SandboxDir "data/intermediate/sf_data_import.txt"
    if (-not (Test-Path $importFile)) { throw "The pipeline did not generate the required '$importFile'." }
    
    # Read the real subject data from the import file to map names to Base58 IDs.
    # The file is a custom CQD format without a header.
    $idMap = @{}
    Get-Content $importFile | ForEach-Object {
        # Split by comma, then trim quotes from each field.
        $fields = $_.Split(',') | ForEach-Object { $_.Trim('"') }
        if ($fields.Length -ge 4) {
            $fullName = $fields[0]
            $idBase58 = $fields[3]
            $idMap[$fullName] = $idBase58
        }
    }

    # Dynamically build the chart export content by injecting the pipeline-generated IDs
    # into the static data template. This correctly simulates Solar Fire preserving the ID
    # in the ZoneAbbr field (the 4th column).
    $chartExportTemplate = @"
"Ernst (1900) Busch","22 Jan 1900","0:15","GgE","-1:00","Kiel","Germany","54N20","010E08"
"Body Name","Body Abbr","Longitude"
"Moon","Mon",189.002773188323
"Sun","Sun",301.513598193159
"Mercury","Mer",289.248528421009
"Venus","Ven",332.342534743509
"Mars","Mar",300.14360125414
"Jupiter","Jup",244.946087801883
"Saturn","Sat",270.067157735933
"Uranus","Ura",251.194346406787
"Neptune","Nep",84.700115342572
"Pluto","Plu",74.9347017635718
"Ascendant","Asc",200.157701309649
"Midheaven","MC",117.655107001904
"Paul McCartney","18 Jun 1942","14:00","3iQ","-2:00","Liverpool","United Kingdom","53N25","002W55"
"Body Name","Body Abbr","Longitude"
"Moon","Mon",137.438858568153
"Sun","Sun",86.6089647184063
"Mercury","Mer",78.3619044521025
"Venus","Ven",48.9928134036616
"Mars","Mar",122.680126156477
"Jupiter","Jup",91.8328603367092
"Saturn","Sat",65.2086841766147
"Uranus","Ura",61.9683695784129
"Neptune","Nep",177.119163816018
"Pluto","Plu",124.270643292912
"Ascendant","Asc",175.307794560545
"Midheaven","MC",83.7374557581678
"Jonathan Cainer","18 Dec 1957","8:00","Dc2","+0:00","London","United Kingdom","51N30","000W10"
"Body Name","Body Abbr","Longitude"
"Moon","Mon",229.370851563549
"Sun","Sun",266.145556757779
"Mercury","Mer",281.20483470234
"Venus","Ven",308.785844073593
"Mars","Mar",236.738903155823
"Jupiter","Jup",206.650855079643
"Saturn","Sat",257.858299542065
"Uranus","Ura",131.237454535687
"Neptune","Nep",214.121770736189
"Pluto","Plu",152.279804607712
"Ascendant","Asc",264.205084618065
"Midheaven","MC",208.52161206082
"@
    
    # Replace the placeholder ZoneAbbr values with the actual Base58 IDs.
    $finalContent = $chartExportTemplate -replace '"GgE"', "`"$($idMap['Ernst (1900) Busch'])`""
    $finalContent = $finalContent -replace '"3iQ"', "`"$($idMap['Paul McCartney'])`""
    $finalContent = $finalContent -replace '"Dc2"', "`"$($idMap['Jonathan Cainer'])`""

    $assetDir = Join-Path $SandboxDir "data/foundational_assets"
    $finalContent | Set-Content -Path (Join-Path $assetDir "sf_chart_export.csv") -Encoding UTF8
    Write-Host "  -> Dynamically generated 'sf_chart_export.csv'."

    # Write the minimal static delineations library
    $delineationsContent = @"
*Quadrant Strong 1st
A focus on self-awareness and personal identity.
*Hemisphere Strong East
A self-motivated and independent nature.
*Aries Strong
Assertive and pioneering.
*Element Strong Water
Compassionate and caring with a strong intuitional nature. Values personal relationships, often taking on a caretaker role.
*Mode Strong Cardinal
Enjoys challenge and action, and becomes frustrated with no recourse for change.
*Sun in Capricorn
Serious and responsible, with a strong awareness of the 'right way of doing things'.
*Moon in Leo
A love for being the center of attention, particularly in the lives of loved ones.
*Mercury in Sagittarius
A search for knowledge to expand the worldview.
*Venus in Sagittarius
A desire to share adventure with a partner, from ideas to physical activities.
*Mars in Aquarius
A drive to fight for just causes. Unpredictable, with group leadership potential.
*Jupiter in Pisces
An intuitive search for truth. A champion of the underdog.
*Saturn in Sagittarius
A potential commitment to higher education and a strict moral code.
*Uranus in Leo
A seeking of freedom for individual expression.
*Neptune in Libra
An ability to view human relationships from a spiritual, holistic viewpoint.
*Pluto in Leo
An ability to use power both positively and negatively.
*Ascendant in Virgo
A cautious approach, preferring to wait for comfort before pursuing a purpose.
*Midheaven in Gemini
A need for stimulation and activity in professional life.
"@
    $delineationsContent | Set-Content -Path (Join-Path $assetDir "sf_delineations_library.txt") -Encoding UTF8
    Write-Host "  -> Wrote minimal 'sf_delineations_library.txt'."

    # --- 4. Run Final Pipeline Scripts ---
    # Define final set of paths
    $sfChartExport = "data/foundational_assets/sf_chart_export.csv"
    $sfDelineations = "data/foundational_assets/sf_delineations_library.txt"
    $neutralizedDir = "data/foundational_assets/neutralized_delineations"
    $subjectDb = "data/processed/subject_db.csv"
    $personalitiesDb = "personalities_db.txt"

    Invoke-PipelineStep `
        -ScriptName "neutralize_delineations.py" `
        -Description "Rewrites esoteric texts into neutral psychological descriptions using an LLM. Includes a retry mechanism." `
        -InputFiles @($sfDelineations) `
        -OutputFiles @("$($neutralizedDir)/*.csv") `
        -Action {
            $neutralizeSuccess = $false
            for ($i = 1; $i -le 3; $i++) {
                if ($Interactive) { Write-Host "`n--- Neutralization Attempt $i of 3 ---" -ForegroundColor Magenta }
                
                $neutralizeArgs = @(
                    (Join-Path $ProjectRoot "src/neutralize_delineations.py"),
                    "--sandbox-path",
                    $SandboxDir
                )
                if ($i -eq 1) { $neutralizeArgs += "--force" }

                pdm run python @neutralizeArgs 2>&1 | Tee-Object -Variable neutralizeOutput
                
                if (($neutralizeOutput | Out-String) -notmatch "failure\(s\)") {
                    $neutralizeSuccess = $true
                    if ($Interactive) { Write-Host "`nNeutralization successful on attempt $i." -ForegroundColor Green }
                    break
                } else {
                    if ($Interactive) { Write-Host "`nNeutralization failed on attempt $i. Retrying..." -ForegroundColor Yellow }
                }
            }
            if (-not $neutralizeSuccess) { throw "FATAL: Delineation neutralization failed after 3 attempts. Halting test." }
        }

    Invoke-PipelineStep `
        -ScriptName "create_subject_db.py" `
        -Description "Integrates chart data with the final subject list to create a master database." `
        -InputFiles @($sfChartExport, $finalCandidates) `
        -OutputFiles @($subjectDb) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/create_subject_db.py") --sandbox-path $SandboxDir --force
        }

    Invoke-PipelineStep `
        -ScriptName "generate_personalities_db.py" `
        -Description "Assembles the final personalities database from the subject data and neutralized text library." `
        -InputFiles @($subjectDb, "$($neutralizedDir)/*.csv") `
        -OutputFiles @($personalitiesDb) `
        -Action {
            pdm run python (Join-Path $ProjectRoot "src/generate_personalities_db.py") --sandbox-path $SandboxDir --force
        }
    
    # --- 5. Final Verification ---
    Write-Host "`n--- Verifying final output... ---" -ForegroundColor Cyan
    $finalDbPath = Join-Path $SandboxDir "personalities_db.txt"
    if (-not (Test-Path $finalDbPath)) {
        throw "FAIL: The final 'personalities_db.txt' file was not created."
    }
    
    # We expect 3 subjects + 1 header line = 4 lines total.
    $lineCount = (Get-Content $finalDbPath).Length
    if ($lineCount -ne 4) { 
        throw "FAIL: The final 'personalities_db.txt' has the wrong number of lines (Expected 4, Found $lineCount)."
    }
    
    Write-Host "`nPASS: The final personalities_db.txt was created successfully." -ForegroundColor Green
    Write-Host "`nSUCCESS: The live data pipeline integration test completed successfully." -ForegroundColor Green
    Write-Host "Inspect the artifacts, then run Stage 3 to clean up."
    Write-Host ""
}
catch {
    Write-Host "`nERROR: Layer 3 test workflow failed.`n$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}