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
    Write-Host "`n--- Performing targeted live fetch for 7 test subjects... ---" -ForegroundColor Yellow
    
    New-Item -Path (Split-Path $outputFile) -ItemType Directory -Force | Out-Null
    "Index`tidADB`tLastName`tFirstName`tGender`tDay`tMonth`tYear`tTime`tZoneAbbr`tZoneTimeOffset`tCity`tCountryState`tLongitude`tLatitude`tRating`tBio`tCategories`tLink" | Set-Content -Path $outputFile -Encoding UTF8
    
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
                Add-Content -Path $outputFile -Value $fetchedContent
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
    $finalRecordCount = $reIndexedData.Length

    Write-Host "`n--- Final Output ---" -ForegroundColor Yellow
    Write-Host " - Raw data export saved to: $displayPath" -ForegroundColor Cyan
    $keyMetric = "Created initial dataset with $finalRecordCount subjects"
    Write-Host "`nSUCCESS: $keyMetric. Initial data fetch completed successfully. ✨`n" -ForegroundColor Green

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

    # Sequentially call each script
    pdm run python (Join-Path $ProjectRoot "src/find_wikipedia_links.py") --sandbox-path . --force

    # --- HARNESS INTERVENTION: Injecting validation failures... ---
    Write-Host "`n--- HARNESS INTERVENTION: Injecting validation failures... ---" -ForegroundColor Magenta
    $hirohitoID = "215"    # Philip, Duke of Edinburgh
    $marquesID = "101097"  # Romário Marques
    $rennaID = "94360"     # Jonathan Renna

    # Read the content, modify it, and write it back. Using Get-Content/Set-Content
    # is more robust for preserving the exact format than Import/Export-Csv.
    $modifiedLinks = (Get-Content $wikiLinks) | ForEach-Object {
        if ($_ -match ",$($hirohitoID),") {
            # This subject will naturally fail the name match, so no change is needed.
            $_
        } elseif ($_ -match ",$($marquesID),") {
            # Replace Marques's English URL with a French one to fail the language check.
            $_ -replace "https://en.wikipedia.org/wiki/Rom%C3%A1rio", "https://fr.wikipedia.org/wiki/Rom%C3%A1rio"
        } elseif ($_ -match ",$($rennaID),") {
            # Blank out Renna's URL to simulate a "No Link Found" failure.
            # This requires careful regex to replace only the URL part.
            $_ -replace 'http[^,]*', ''
        } else {
            $_
        }
    }
    Set-Content -Path $wikiLinks -Value $modifiedLinks
    Write-Host "  -> Injected Non-English URL and No Link Found failures."

    pdm run python (Join-Path $ProjectRoot "src/validate_wikipedia_pages.py") --sandbox-path . --force
    pdm run python (Join-Path $ProjectRoot "src/select_eligible_candidates.py") --sandbox-path . --force

    pdm run python (Join-Path $ProjectRoot "src/generate_eminence_scores.py") --sandbox-path . --force

    pdm run python (Join-Path $ProjectRoot "src/generate_ocean_scores.py") --sandbox-path . --force

    # --- Integration Test Checkpoint ---
    Write-Host "`n--- INTEGRATION TEST CHECKPOINT: generate_ocean_scores.py ---" -ForegroundColor Magenta
    $displayOceanScoresPath = (Join-Path $PWD $oceanScores).Replace("$ProjectRoot" + [System.IO.Path]::DirectorySeparatorChar, "")
    if (-not (Test-Path $oceanScores)) { throw "FAIL: '$displayOceanScoresPath' was not created." }
    $lineCount = (Get-Content $oceanScores).Length
    # We expect the 3 control subjects + 1 header line = 4 lines total, as the cutoff logic won't trigger.
    if ($lineCount -ne 4) { throw "FAIL: '$displayOceanScoresPath' has the wrong number of lines (Expected 4, Found $lineCount)." }
    Write-Host "Verification PASSED: '$displayOceanScoresPath' was created with the correct number of records." -ForegroundColor Green
    Write-Host ""
    exit 0 # Temporarily exit after this stage for methodical testing.
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

    # Dynamically build the chart export content by injecting the pipeline-generated IDs
    # into the static data template. This correctly simulates Solar Fire preserving the ID in the name field.
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
    
    # Use -replace with regex to ensure we're targeting the exact name fields.
    # The `\(1900\)` escapes the parentheses for the regex match.
    # The replacement string uses nested quotes `"` to correctly form the new name field.
    $finalContent = $chartExportTemplate -replace '"Ernst \(1900\) Busch"', "`"$($idMap['Ernst (1900) Busch']) Ernst (1900) Busch`""
    $finalContent = $finalContent -replace '"Paul McCartney"', "`"$($idMap['Paul McCartney']) Paul McCartney`""
    $finalContent = $finalContent -replace '"Jonathan Cainer"', "`"$($idMap['Jonathan Cainer']) Jonathan Cainer`""

    $assetDir = "data/foundational_assets"
    $finalContent | Set-Content -Path (Join-Path $assetDir "sf_chart_export.csv") -Encoding UTF8
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