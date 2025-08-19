#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
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
# Filename: migrate_experiment.ps1

<#
.SYNOPSIS
    Upgrades a legacy or severely corrupted experiment via a safe, non-destructive copy.

.DESCRIPTION
    This is a powerful safety utility for handling legacy or corrupted experiments.
    It performs a non-destructive migration by creating a clean, timestamped copy
    of the target experiment and running the full upgrade and validation process
    on that new copy.

    The original data is always left untouched. The script provides a clear,
    context-aware prompt that explains the safety of the process and accurately
    describes when API calls might be necessary to repair missing data.

.PARAMETER TargetDirectory
    The path to the experiment directory that will be targeted for migration.
    This original directory will be copied, not modified.

.EXAMPLE
    # Copy and migrate "Legacy_Experiment_1"
    # This creates a folder like "output/migrated_experiments/Legacy_Experiment_1_migrated_20250712_103000"
    .\migrate_experiment.ps1 -TargetDirectory "output/legacy/Legacy_Experiment_1"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to migrate.")]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false, HelpMessage = "Specifies a custom parent directory for the migrated experiment.")]
    [string]$DestinationParent,

    [Parameter(Mandatory = $false, HelpMessage = "Run in non-interactive mode, suppressing user prompts for confirmation.")]
    [switch]$NonInteractive,

    [Parameter(Mandatory=$false, HelpMessage="Suppresses the initial PDM detection message.")]
    [switch]$NoHeader
)

function Get-ProjectRoot {
    # This robust method works even when the script is pasted into a terminal.
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) {
            return $currentDir.Path
        }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml). Please run this script from within the project directory."
}

function Write-Header { param([string[]]$Lines, [string]$Color = "White", [int]$Width = 80); $s = "#" * $Width; Write-Host "`n$s" -F $Color; foreach ($l in $Lines) { $pL = [math]::Floor(($Width - $l.Length - 6) / 2); $pR = [math]::Ceiling(($Width - $l.Length - 6) / 2); Write-Host "###$(' ' * $pL)$l$(' ' * $pR)###" -F $Color }; Write-Host $s -F $Color; Write-Host "" }

# --- Main Script Logic ---
$ProjectRoot = Get-ProjectRoot
$C_CYAN = "`e[96m"; $C_GREEN = "`e[92m"; $C_YELLOW = "`e[93m"; $C_RED = "`e[91m"; $C_RESET = "`e[0m"

$logFilePath = $null
try {
    if (-not (Test-Path $TargetDirectory -PathType Container)) { throw "The specified TargetDirectory '$TargetDirectory' does not exist." }
    $TargetPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    # --- Setup destination and logging ---
    $TargetBaseName = (Get-Item -Path $TargetPath).Name
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $NewFolderName = "${TargetBaseName}_migrated_${Timestamp}"
    $DefaultDestParent = Join-Path $ProjectRoot "output/migrated_experiments"
    $DestParent = if ($PSBoundParameters.ContainsKey('DestinationParent')) { $PSBoundParameters['DestinationParent'] } else { $DefaultDestParent }
    $DestinationPath = Join-Path -Path $DestParent -ChildPath $NewFolderName
    if (-not (Test-Path -Path $DestParent)) { New-Item -ItemType Directory -Path $DestParent -Force | Out-Null }
    $logFilePath = Join-Path $DestinationPath "experiment_migration_log.txt"
    
    Write-Host "`nThe migration log will be saved to: $(Resolve-Path $logFilePath -Relative)" -ForegroundColor Gray
    Start-Transcript -Path $logFilePath -Force | Out-Null

    # --- Step 1: Initial Audit ---
    $auditScriptPath = Join-Path $ProjectRoot "audit_experiment.ps1"
    & $auditScriptPath -TargetDirectory $TargetPath
    $auditExitCode = $LASTEXITCODE

    # --- Step 2: Confirmation Prompt ---
    if (-not $NonInteractive.IsPresent) {
        $promptMessage = "`nThis is a safe, non-destructive process. A clean, upgraded copy of the experiment will be created, and your original data will not be modified. Do you wish to proceed? (Y/N)"
        $choice = Read-Host -Prompt $promptMessage
        if ($choice.Trim().ToLower() -ne 'y') { Write-Host "`nMigration aborted by user." -ForegroundColor Yellow; return }
    }

    # --- Step 3: Copy Data ---
    Write-Header -Lines "Step 1/2: Copying Experiment Data" -Color Cyan
    Write-Host "Source:      $((Resolve-Path $TargetPath -Relative).TrimStart(".\"))"
    Write-Host "Destination: $((Resolve-Path $DestinationPath -Relative).TrimStart(".\"))"
    Copy-Item -Path (Join-Path $TargetPath "*") -Destination $DestinationPath -Recurse -Force
    Write-Host "`nCopy complete."

    # --- Step 4: Upgrade Copy ---
    Write-Header -Lines "Step 2/2: Upgrading New Experiment Copy" -Color Cyan
    $migrateArgs = @((Join-Path $ProjectRoot "src/experiment_manager.py"), $DestinationPath, "--migrate", "--force-color", "--verbose")
    & pdm run python $migrateArgs
    if ($LASTEXITCODE -ne 0) { throw "Migration process failed." }

    # --- Step 5: Final Validation ---
    & $auditScriptPath -TargetDirectory $DestinationPath
    if ($LASTEXITCODE -ne 0) { throw "VALIDATION FAILED! The final migrated result is not valid." }

    Write-Host "`nMigration process complete. Migrated data is in: '$((Resolve-Path $DestinationPath -Relative).TrimStart(".\"))'`n" -ForegroundColor Green

} catch {
    Write-Header -Lines "MIGRATION FAILED" -Color Red
    Write-Host "$($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($logFilePath) {
        Stop-Transcript | Out-Null
        if (Test-Path -LiteralPath $logFilePath) {
            try { $c=Get-Content -Path $logFilePath -Raw; $c=$c -replace '(?s)\*+\r?\nPowerShell transcript start.*?\*+\r?\n\r?\n',''; $c=$c -replace '(?s)\*+\r?\nPowerShell transcript end.*',''; $c=$c -replace "`e\[[0-9;]*m",''; Set-Content -Path $logFilePath -Value $c.Trim() -Force } catch {}
            Write-Host "`nLog saved at: $(Resolve-Path -Path $logFilePath -Relative)" -ForegroundColor Gray
        }
    }
}

# === End of migrate_experiment.ps1 ===
