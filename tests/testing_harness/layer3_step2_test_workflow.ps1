#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 2: Execute the Test Workflow ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer3_sandbox"
$ErrorActionPreference = "Stop"

if (-not (Test-Path $SandboxDir)) { throw "FATAL: Test sandbox not found. Please run Step 1 first." }

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 2: Execute the Test Workflow ---" -ForegroundColor Cyan

try {
    Set-Location $SandboxDir

    $fetchScript = Join-Path $ProjectRoot "src/fetch_adb_data.py"
    $outputFile = "data/sources/adb_raw_export.txt"

    # --- 1. Targeted Live Fetch ---
    Write-Host "`n--- Performing targeted live fetch for 3 test subjects... ---" -ForegroundColor Yellow
    
    New-Item -Path (Split-Path $outputFile) -ItemType Directory -Force | Out-Null
    "Index`tidADB`tLastName`tFirstName`tGender`tDay`tMonth`tYear`tTime`tZoneAbbr`tZoneTimeOffset`tCity`tCountryState`tLongitude`tLatitude`tRating`tBio`tCategories`tLink" | Set-Content -Path $outputFile -Encoding UTF8
    
    $subjects = @(
        @{ Name="Ernst Busch";     Date="1900-01-22" },
        @{ Name="Paul McCartney";  Date="1942-06-18" },
        @{ Name="Jonathan Cainer"; Date="1957-12-18" }
    )
    foreach ($subject in $subjects) {
        Write-Host "  -> Fetching data for $($subject.Name)..."
        $tempOutputFile = Join-Path $SandboxDir "temp_fetch_output.txt"
        # Pass the --sandbox-path argument to correctly isolate all file operations.
        pdm run python $fetchScript --sandbox-path $SandboxDir --start-date $subject.Date --end-date $subject.Date -o $tempOutputFile --force
        
        $fetchedContent = Get-Content $tempOutputFile | Select-Object -Skip 1
        if ($fetchedContent) {
            Add-Content -Path $outputFile -Value $fetchedContent
        }
        Remove-Item $tempOutputFile
    }

    # CRITICAL: Filter the aggregated data to only our 3 target subjects before proceeding.
    Write-Host "`n--- Filtering aggregated data to target subjects... ---" -ForegroundColor Yellow
    $targetIDs = "52735", "9129", "42399" # Ernst Busch, Paul McCartney, Jonathan Cainer
    
    $header = Get-Content $outputFile | Select-Object -First 1
    $dataRows = Get-Content $outputFile | Select-Object -Skip 1
    
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
    Set-Content -Path $outputFile -Value $finalContent

    $displayPath = (Join-Path $PWD $outputFile).Replace("$ProjectRoot" + [System.IO.Path]::DirectorySeparatorChar, "")
    Write-Host "  -> Filtering and re-indexing complete. Final record count: $($reIndexedData.Length)."
    Write-Host "Output saved to: $displayPath"

    # --- 2. Run the Automated Pipeline Scripts Sequentially ---
    Write-Host "`n--- Running automated data pipeline scripts... ---" -ForegroundColor Yellow
    
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

    # Sequentially call each script with explicit input/output paths
    pdm run python (Join-Path $ProjectRoot "src/find_wikipedia_links.py") --work-dir $PWD -i $adbRaw -o $wikiLinks --force

    # --- Integration Test Checkpoint ---
    Write-Host "`n--- INTEGRATION TEST CHECKPOINT: find_wikipedia_links.py ---" -ForegroundColor Green
    $displayWikiLinksPath = (Join-Path $PWD $wikiLinks).Replace("$ProjectRoot" + [System.IO.Path]::DirectorySeparatorChar, "")
    if (-not (Test-Path $wikiLinks)) { throw "FAIL: '$displayWikiLinksPath' was not created." }
    $lineCount = (Get-Content $wikiLinks).Length
    if ($lineCount -ne 4) { throw "FAIL: '$displayWikiLinksPath' has the wrong number of lines (Expected 4, Found $lineCount)." }
    Write-Host "Verification PASSED: '$displayWikiLinksPath' was created with the correct number of records." -ForegroundColor Yellow
    Write-Host ""
    exit 0 # Temporarily exit after this stage for methodical testing.

    pdm run python (Join-Path $ProjectRoot "src/validate_wikipedia_pages.py") -i $wikiLinks -o $validationReport --force
    pdm run python (Join-Path $ProjectRoot "src/select_eligible_candidates.py") -i $adbRaw -v $validationReport -o $eligibleCandidates --force
    pdm run python (Join-Path $ProjectRoot "src/generate_eminence_scores.py") -i $eligibleCandidates -o $eminenceScores --force
    pdm run python (Join-Path $ProjectRoot "src/generate_ocean_scores.py") -i $eminenceScores -o $oceanScores --force
    pdm run python (Join-Path $ProjectRoot "src/select_final_candidates.py") -e $eligibleCandidates -s $eminenceScores -o $oceanScores -c (Join-Path $ProjectRoot "data/foundational_assets/country_codes.csv") -f $finalCandidates --force
    pdm run python (Join-Path $ProjectRoot "src/prepare_sf_import.py") -i $finalCandidates -o $sfImport --force
    
    # --- 3. Dynamic Simulation of Manual Steps ---
    Write-Host "`n--- Simulating Manual Solar Fire Export Steps... ---" -ForegroundColor Cyan
    $importFile = "data/intermediate/sf_data_import.txt"
    if (-not (Test-Path $importFile)) { throw "The pipeline did not generate the required '$importFile'." }
    
    # Read the real subject data from the import file
    $subjectData = Import-Csv -Path $importFile -Delimiter "`t"
    $idMap = @{}
    foreach ($row in $subjectData) {
        $idBase58 = $row.Name.Split(' ')[0]
        $fullName = $row.Name.Substring($idBase58.Length).Trim()
        $idMap[$fullName] = $idBase58
    }

    # Dynamically build the chart export content
    $chartExportContent = @"
"ID","Name","Sun Sign","Moon Sign","Mercury Sign","Venus Sign","Mars Sign","Jupiter Sign","Saturn Sign","Uranus Sign","Neptune Sign","Pluto Sign","Ascendant Sign","Midheaven Sign"
"$($idMap['Ernst Busch'])","Ernst Busch","Capricorn","Leo","Sagittarius","Sagittarius","Aquarius","Pisces","Sagittarius","Leo","Libra","Leo","Virgo","Gemini"
"$($idMap['Paul McCartney'])","Paul McCartney","Gemini","Leo","Gemini","Taurus","Leo","Gemini","Gemini","Gemini","Virgo","Leo","Virgo","Gemini"
"$($idMap['Jonathan Cainer'])","Jonathan Cainer","Sagittarius","Aries","Sagittarius","Scorpio","Libra","Libra","Sagittarius","Leo","Scorpio","Virgo","Cancer","Aries"
"@
    $assetDir = "data/foundational_assets"
    $chartExportContent | Set-Content -Path (Join-Path $assetDir "sf_chart_export.csv") -Encoding UTF8
    Write-Host "  -> Dynamically generated 'sf_chart_export.csv'."

    # Write the minimal static delineations library
    $delineationsContent = @"
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
    Write-Host "`n--- Running final data pipeline scripts... ---" -ForegroundColor Yellow
    $finalScripts = @(
        "src/neutralize_delineations.py",
        "src/create_subject_db.py",
        "src/generate_personalities_db.py"
    )
    # Define final set of paths
    $sfChartExport = "data/foundational_assets/sf_chart_export.csv"
    $sfDelineations = "data/foundational_assets/sf_delineations_library.txt"
    $neutralizedDir = "data/foundational_assets/neutralized_delineations"
    $subjectDb = "data/intermediate/subject_db.csv"
    $personalitiesDb = "personalities_db.txt"

    pdm run python (Join-Path $ProjectRoot "src/neutralize_delineations.py") -i $sfDelineations -o $neutralizedDir --force
    pdm run python (Join-Path $ProjectRoot "src/create_subject_db.py") -c $sfChartExport -f $finalCandidates -o $subjectDb --force
    pdm run python (Join-Path $ProjectRoot "src/generate_personalities_db.py") -s $subjectDb -n $neutralizedDir -p (Join-Path $ProjectRoot "data/foundational_assets/point_weights.csv") -b (Join-Path $ProjectRoot "data/foundational_assets/balance_thresholds.csv") -o $personalitiesDb --force

    # --- 5. Verification ---
    Write-Host "`n--- Verifying final output... ---" -ForegroundColor Cyan
    $finalDbPath = "personalities_db.txt"
    if (-not (Test-Path $finalDbPath)) {
        throw "FAIL: The final 'personalities_db.txt' file was not created."
    }
    
    $lineCount = (Get-Content $finalDbPath).Length
    if ($lineCount -lt 4) { 
        throw "FAIL: The final 'personalities_db.txt' has too few lines (Expected at least 4, Found $lineCount)."
    }
    
    Write-Host "`nPASS: The final personalities_db.txt was created successfully." -ForegroundColor Green
    Write-Host "`nSUCCESS: The live data pipeline integration test completed successfully." -ForegroundColor Green
    Write-Host "Inspect the artifacts, then run Step 3 to clean up."
    Write-Host ""
}
catch {
    Write-Host "`nERROR: Layer 3 test workflow failed.`n$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Set-Location $ProjectRoot
}