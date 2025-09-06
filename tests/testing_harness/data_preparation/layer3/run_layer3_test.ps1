#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('default', 'bypass')]
    [string]$Profile,

    [Parameter(Mandatory=$false)]
    [switch]$Interactive
)

$ErrorActionPreference = 'Stop'

function Test-ProfileValid {
    param([hashtable]$Profile)
    $required = @('Name', 'Description', 'Subjects', 'ExpectedFinalLineCount', 'ConfigOverrides')
    foreach ($field in $required) {
        if (-not $Profile.ContainsKey($field)) {
            throw "Profile '$($Profile.Name)' is missing required field: '$field'"
        }
    }
    if ($Profile.Subjects.Count -eq 0) {
        throw "Profile '$($Profile.Name)' must define at least one test subject."
    }
}

# --- Define Common Test Assets ---
$commonSubjects = @(
    @{ Name = "Ernst (1900) Busch"; idADB = "52735"; Date = "1900-01-22" }, @{ Name = "Paul McCartney"; idADB = "9129"; Date = "1942-06-18" },
    @{ Name = "Jonathan Cainer"; idADB = "42399"; Date = "1957-12-18" }, @{ Name = "Philip, Duke of Edinburgh"; idADB = "215"; Date = "1921-06-10" },
    @{ Name = "Suicide: Gunshot 14259"; idADB = "14259"; Date = "1967-11-19" }, @{ Name = "Jonathan Renna"; idADB = "94360"; Date = "1979-04-28" },
    @{ Name = "Romário Marques"; idADB = "101097"; Date = "1989-07-20" }
)

# --- Define Test Profiles ---
$TestProfiles = @{
    default = @{
        Name = "Default"; Description = "Tests the standard pipeline with LLM-based selection active."
        Subjects = $commonSubjects
        ConfigOverrides = @{ "bypass_candidate_selection" = "false" }
        InterventionScript = {
            param($SandboxDir)
            Write-Host "`n--- HARNESS INTERVENTION: Injecting validation failures... ---" -ForegroundColor Magenta
            $wikiLinksFile = Join-Path $SandboxDir "data/processed/adb_wiki_links.csv"
            (Get-Content $wikiLinksFile) | ForEach-Object {
                if ($_ -match ",101097,") { $_ -replace "https://en.wikipedia.org/wiki/Rom%C3%A1rio", "https://fr.wikipedia.org/wiki/Rom%C3%A1rio" }
                elseif ($_ -match ",94360,") { $_ -replace 'http[^,]*', '' } else { $_ }
            } | Set-Content -Path $wikiLinksFile
            Write-Host "  -> Injected Non-English URL and No Link Found failures."
        }
        ExpectedFinalLineCount = 4 # This will be determined by the LLM scoring process + header
    }
    bypass = @{
        Name = "Bypass"; Description = "Tests the pipeline with LLM-based selection bypassed."
        Subjects = $commonSubjects
        ConfigOverrides = @{ "bypass_candidate_selection" = "true" }
        InterventionScript = $null
        # Expects the 3 subjects that pass deterministic filtering + header
        ExpectedFinalLineCount = 4
    }
}

# --- Select and Run the Test ---
$SelectedProfile = $TestProfiles[$Profile]
Test-ProfileValid -Profile $SelectedProfile
Write-Host "`n--- Running Layer 3 Test Profile: $($SelectedProfile.Name) ---" -ForegroundColor Magenta
Write-Host $SelectedProfile.Description -ForegroundColor Yellow

try {
    & "$PSScriptRoot/layer3_phase1_setup.ps1"
    # --- Phase 2: Execute ---
    # Pass the entire profile object to the workflow script using a splatting hashtable for robustness.
    $workflowPath = "$PSScriptRoot/layer3_phase2_test_workflow.ps1"
    $workflowArgs = @{
        TestProfile = $SelectedProfile
    }
    if ($Interactive) {
        $workflowArgs.Interactive = $true
    }

    & $workflowPath @workflowArgs
    & "$PSScriptRoot/layer3_phase3_cleanup.ps1" -ProfileName $Profile
    Write-Host "`nSUCCESS: Layer 3 test profile '$($Profile)' completed successfully." -ForegroundColor Green
    Write-Host ""
}
catch {
    Write-Host "`nERROR: Layer 3 test profile '$($Profile)' failed." -ForegroundColor Red
    if ($_.Exception.Message -ne "HANDLED_ERROR") {
        Write-Host "$($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
    exit 1
}