#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 1: Automated Setup ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$TestEnvRoot = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $TestEnvRoot "layer3_sandbox"

# --- Cleanup from previous failed runs ---
if (Test-Path $SandboxDir) {
    Write-Host "Cleaning up previous Layer 3 sandbox..."
    Remove-Item -Path $SandboxDir -Recurse -Force
}

# --- Create the test environment ---
New-Item -ItemType Directory -Path $TestEnvRoot -Force | Out-Null
New-Item -ItemType Directory -Path $SandboxDir -Force | Out-Null
@("data/sources", "data/reports", "data/processed", "data/intermediate", "data/foundational_assets") | ForEach-Object {
    New-Item -Path (Join-Path $SandboxDir $_) -ItemType Directory -Force | Out-Null
}

# --- Copy required assets into the sandbox. DO NOT copy source code. ---
Copy-Item -Path ".env" -Destination $SandboxDir
Copy-Item -Path "data/foundational_assets/country_codes.csv", "data/foundational_assets/point_weights.csv", "data/foundational_assets/balance_thresholds.csv" -Destination (Join-Path $SandboxDir "data/foundational_assets/")

# --- Copy the pre-neutralized seed data into the sandbox ---
# This is the key to bypassing the expensive neutralization step.
$SeedDelineationsDir = Join-Path $ProjectRoot "tests/testing_harness/seed_data/seed_neutralized_delineations"
$DestDelineationsDir = Join-Path $SandboxDir "data/foundational_assets/neutralized_delineations"
Copy-Item -Path $SeedDelineationsDir -Destination $DestDelineationsDir -Recurse

# --- Create the other required seed files inside the sandbox ---
Copy-Item -Path (Join-Path $ProjectRoot "tests/testing_harness/seed_data/seed_subject_db.csv") -Destination (Join-Path $SandboxDir "data/intermediate/subject_db.csv")

$rawAdbContent = @"
Index`tidADB`tLastName`tFirstName`tGender`tDay`tMonth`tYear`tTime`tZoneAbbr`tZoneTimeOffset`tCity`tCountryState`tLongitude`tLatitude`tRating`tBio`tCategories`tLink
1`t1001`tConnery`tSean`tM`t25`t8`t1930`t18:05`tBST`t-01:00`tEdinburgh`tSCOT (UK)`t3W13`t55N57`tAA`tBio1`tCat1`tLink1
2`t1002`tOdetta`t`tF`t31`t12`t1930`t09:20`tCST`t-06:00`tBirmingham`tAL (US)`t86W48`t33N31`tAA`tBio2`tCat2`tLink2
3`t1003`tHernán`tAarón`tM`t20`t11`t1930`t04:10`tMST`t-07:00`tCamargo`tMEX`t105W10`t27N40`tAA`tBio3`tCat3`tLink3
"@
$rawAdbContent | Set-Content -Path (Join-Path $SandboxDir "data/sources/adb_raw_export.txt") -Encoding UTF8

# Pre-seed the output of find_wikipedia_links.py
$wikiLinksContent = @"
Index,idADB,ADB_Name,BirthYear,Entry_Type,Wikipedia_URL,Notes
1,1001,"Connery, Sean",1930,Person,https://en.wikipedia.org/wiki/Sean_Connery,
2,1002,"Odetta",1930,Person,https://en.wikipedia.org/wiki/Odetta,
3,1003,"Hernán, Aarón",1930,Person,https://en.wikipedia.org/wiki/Aar%C3%B3n_Hern%C3%A1n,
"@
$wikiLinksContent | Set-Content -Path (Join-Path $SandboxDir "data/processed/adb_wiki_links.csv") -Encoding UTF8

$validationReportContent = @"
Index,idADB,ADB_Name,Entry_Type,WP_URL,WP_Name,Name_Match_Score,Death_Date_Found,Status,Notes
1,1001,"Connery, Sean",Person,https://en.wikipedia.org/wiki/Sean_Connery,Sean Connery,100,True,OK,
2,1002,Odetta,Person,https://en.wikipedia.org/wiki/Odetta,Odetta,100,True,OK,
3,1003,"Hernán, Aarón",Person,https://en.wikipedia.org/wiki/Aar%C3%B3n_Hern%C3%A1n,Aarón Hernán,100,True,OK,
"@
$validationReportContent | Set-Content -Path (Join-Path $SandboxDir "data/reports/adb_validation_report.csv") -Encoding UTF8

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 1: Automated Setup ---" -ForegroundColor Cyan
Write-Host ""
Write-Host "Integration test sandbox created successfully in '$((Resolve-Path $SandboxDir -Relative).TrimStart(".\"))'." -ForegroundColor Green
Write-Host "Your next action is Step 2: Execute the Test Workflow." -ForegroundColor Yellow
Write-Host ""