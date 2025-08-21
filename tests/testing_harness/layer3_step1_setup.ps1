# Filename: tests/testing_harness/layer3_step1_setup.ps1
function Get-ProjectRoot {
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) { return $currentDir.Path }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml)."
}

$ProjectRoot = Get-ProjectRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 1: Automated Setup ---" -ForegroundColor Cyan

# Create the test directory and all required subdirectories
$testDir = "temp_integration_test"; New-Item -Path $testDir -ItemType Directory -Force | Out-Null
@("sources", "reports", "processed", "intermediate", "foundational_assets/neutralized_delineations") | ForEach-Object { New-Item -Path (Join-Path $testDir "data/$_") -ItemType Directory -Force | Out-Null }

# Copy the orchestrator, real source code, and required assets
Copy-Item -Path "prepare_data.ps1" -Destination $testDir
Copy-Item -Path "src" -Destination $testDir -Recurse
Copy-Item -Path ".env" -Destination $testDir
Copy-Item -Path "data/foundational_assets/country_codes.csv", "data/foundational_assets/point_weights.csv", "data/foundational_assets/balance_thresholds.csv", "data/foundational_assets/sf_delineations_library.txt" -Destination (Join-Path $testDir "data/foundational_assets/")

# Create the seed data files inside the test directory
Set-Content -Path (Join-Path $testDir "data/sources/adb_raw_export.txt") -Value @"
Index`tidADB`tLastName`tFirstName`tGender`tDay`tMonth`tYear`tTime`tZoneAbbr`tZoneTimeOffset`tCity`tCountryState`tLongitude`tLatitude`tRating`tBio`tCategories`tLink
5404`t6790`tConnery`tSean`tM`t25`t8`t1930`t18:05`t...`t-01:00`tEdinburgh`tSCOT (UK)`t3W13`t55N57`tAA`tScottish actor and film icon, he was the first to play the role of agent 007 in`tVoice/Speech, Entertain Producer, Knighted, Philanthropist, Kids - Noted, Hobbies, games, Hair, Kids 1-3, Top 5% of Profession, Rags to riches, Sex-symbol, Size, Order of birth, Foster, Step, or Adopted Kids, Number of Divorces, American Book, Number of Marriages, Vocational award, Live Stage, Oscar, Expatriate, Appearance gorgeous, Mate - Noted, Actor/ Actress, Long life >80 yrs`thttps://www.astro.com/astro-databank/Connery,_Sean
5459`t90566`tHernán`tAarón`tM`t20`t11`t1930`t04:10`t...`t-07:00`tCamargo (Chihuahua)`tMEX`t105W10`t27N40`tAA`tMexican stage and screen actor most famous for his work in ’’telenovelas’’ (TV`tVocational award, Heart disease/attack, Illness/ Disease, Clerical/ Secretarial, Kids 1-3, TV series/ Soap star, Actor/ Actress, Long life >80 yrs`thttps://www.astro.com/astro-databank/Hernán,_Aarón
5482`t24013`tOdetta`t`tF`t31`t12`t1930`t09:20`t...`t-06:00`tBirmingham`tAL (US)`t86W48`t33N31`tAA`tAmerican singer known for vocal power and clarity with a rich intensity of`tRace, Illness/ Disease, Heart disease/attack, Kidney, Top 5% of Profession, Profiles Of Women, Travel for work, Vocalist/ Pop, Rock, etc., Number of Marriages`thttps://www.astro.com/astro-databank/Odetta
"@
Set-Content -Path (Join-Path $testDir "data/reports/adb_validation_report.csv") -Value @"
Index,idADB,ADB_Name,Entry_Type,WP_URL,WP_Name,Name_Match_Score,Death_Date_Found,Status,Notes
5404,6790,"Connery, Sean",Person,https://en.wikipedia.org/wiki/Sean_Connery,Sean Connery,100,True,OK,
5459,90566,"Hernán, Aarón",Person,https://en.wikipedia.org/wiki/Aar%C3%B3n_Hern%C3%A1n,Aarón Hernán,100,True,OK,
5482,24013,Odetta,Person,https://en.wikipedia.org/wiki/Odetta,Odetta,100,True,OK,
"@

Write-Host "`nIntegration test environment created successfully in 'temp_integration_test'." -ForegroundColor Green
Write-Host "Your next action is Step 2: Execute the Test Workflow." -ForegroundColor Yellow
Write-Host ""