#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 Peter J. Marko
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: tests/testing_harness/data_preparation/layer3/run_layer3_test.ps1

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('default', 'bypass')]
    [string]$Profile,

    [Parameter(Mandatory=$false)]
    [switch]$Interactive
)

$ErrorActionPreference = 'Stop'

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_GRAY = "`e[90m"
$C_MAGENTA = "`e[95m"
$C_RED = "`e[91m"
$C_ORANGE = "`e[38;5;208m" # A specific orange from the 256-color palette
$C_YELLOW = "`e[93m"
$C_GREEN = "`e[92m"
$C_CYAN = "`e[96m"
$C_BLUE = "`e[94m"

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

if ($Interactive) {
    Write-Host ""
    Write-Host "Welcome to the Layer 3 Interactive Test (Guided Tour)." -ForegroundColor Cyan
    Write-Host "This test will walk you through the entire data preparation pipeline in a safe, isolated sandbox."
    Write-Host "It consists of three phases:"
    Write-Host "  1. Setup:    Creates a temporary sandbox and copies in a small seed dataset."
    Write-Host "  2. Execute:  Runs the full pipeline, which consists of 15 tasks (13 steps"
    Write-Host "               plus 2 validation sub-steps), pausing for your inspection before each one."
    Write-Host "  3. Cleanup:  Archives the test results and removes the sandbox."
    Write-Host ""
    [Console]::Write("${C_ORANGE}Press Enter to begin the Setup phase...`n${C_RESET} ")
    Read-Host | Out-Null
}

try {
    & "$PSScriptRoot/layer3_phase1_setup.ps1"

    if ($Interactive) {
        Write-Host "---" -ForegroundColor DarkGray
        Write-Host "Phase 1 (Setup) is complete. The test sandbox has been created." -ForegroundColor Cyan
        Write-Host "Next, we will begin Phase 2 (Execution), which will run the main data preparation"
        Write-Host "orchestrator ('prepare_data.ps1') against the seed data."
        Write-Host ""
        Write-Host "You will be prompted to continue before each of the 15 tasks."
        Write-Host ""
        [Console]::Write("${C_ORANGE}Press Enter to begin the Execution phase...${C_RESET} ")
        Read-Host | Out-Null
    }

    # --- Phase 2: Execute ---
    # Pass the entire profile object to the workflow script using a splatting hashtable for robustness.
    $workflowPath = "$PSScriptRoot/layer3_phase2_run.ps1"
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

# === End of tests/testing_harness/data_preparation/layer3/run_layer3_test.ps1 ===
