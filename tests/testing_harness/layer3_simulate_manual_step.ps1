# Filename: tests/testing_harness/layer3_simulate_manual_step.ps1
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

$testDir = "temp_integration_test"
if (-not (Test-Path $testDir)) { throw "FATAL: Test directory '$testDir' not found. Please run Step 1 first." }

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Simulating Manual Step ---" -ForegroundColor Cyan

Set-Content -Path (Join-Path $testDir "data/foundational_assets/sf_chart_export.csv") -Value @"
"Connery Sean","25 August 1930","18:05","3fS1bTfA","+1:00","Edinburgh","SCOT (UK)","55n57","3w13"
"Body Name","Body Abbr","Longitude"
"Sun","Su","152.05"
"Moon","Mo","333.15"
"Mercury","Me","168.97"
"Venus","Ve","180.82"
"Mars","Ma","162.77"
"Jupiter","Ju","97.02"
"Saturn","Sa","298.50"
"Uranus","Ur","12.82"
"Neptune","Ne","151.02"
"Pluto","Pl","110.12"
"Ascendant","Asc","322.25"
"Midheaven","MC","251.58"
"Hernán Aarón","20 November 1930","4:10","6sYw24nF","-7:00","Camargo (Chihuahua)","MEX","27n40","105w10"
"Body Name","Body Abbr","Longitude"
"Sun","Su","237.58"
"Moon","Mo","126.70"
"Mercury","Me","254.83"
"Venus","Ve","220.52"
"Mars","Ma","143.20"
"Jupiter","Ju","104.53"
"Saturn","Sa","298.88"
"Uranus","Ur","13.78"
"Neptune","Ne","155.07"
"Pluto","Pl","110.75"
"Ascendant","Asc","216.92"
"Midheaven","MC","127.35"
"Odetta","31 December 1930","9:20","cTSo2","-6:00","Birmingham","AL (US)","33n31","86w48"
"Body Name","Body Abbr","Longitude"
"Sun","Su","279.17"
"Moon","Mo","289.02"
"Mercury","Me","293.45"
"Venus","Ve","258.97"
"Mars","Ma","153.25"
"Jupiter","Ju","107.57"
"Saturn","Sa","300.73"
"Uranus","Ur","13.88"
"Neptune","Ne","155.85"
"Pluto","Pl","111.08"
"Ascendant","Asc","329.58"
"Midheaven","MC","252.75"
"@

Write-Host "`nSuccessfully created 'sf_chart_export.csv' in the test directory." -ForegroundColor Green
Write-Host "You can now re-run Step 2 (layer3_step2_test_workflow.ps1) to complete the pipeline." -ForegroundColor Yellow
Write-Host ""