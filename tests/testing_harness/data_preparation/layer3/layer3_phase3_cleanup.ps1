#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 3: Automated Cleanup ---

param(
    [Parameter(Mandatory=$true)]
    [string]$ProfileName
)

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
$SandboxParentDir = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $SandboxParentDir "layer3_sandbox"

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Phase 3: Automated Cleanup ---" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $SandboxDir) {
    # --- Create a backup before cleaning up ---
    try {
        $backupDir = Join-Path $ProjectRoot "data/backup"
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupFileName = "layer3_sandbox_backup_{0}_{1}.zip" -f $ProfileName, $timestamp
        $backupPath = Join-Path $backupDir $backupFileName
        
        Write-Host "Creating backup of test artifacts..."
        Compress-Archive -Path $SandboxDir -DestinationPath $backupPath -Force
        Write-Host "  -> Backup saved to: $((Resolve-Path $backupPath -Relative).TrimStart(".\"))" -ForegroundColor Cyan
    }
    catch {
        Write-Warning "Could not create sandbox backup. Manual cleanup may be required."
        Write-Warning $_.Exception.Message
    }

    Write-Host "Removing Layer 3 sandbox directory..."
    try {
        Remove-Item -Path $SandboxDir -Recurse -Force -ErrorAction Stop
        Write-Host "  -> Done." -ForegroundColor Green
    }
    catch {
        Write-Warning "Could not fully remove sandbox (files may be in use by another process)."
        Write-Host "Attempting partial cleanup..." -ForegroundColor Yellow
        
        # Try to remove what we can, suppressing progress output
        Get-ChildItem $SandboxDir -Recurse -ErrorAction SilentlyContinue | 
            Remove-Item -Force -Recurse -ErrorAction SilentlyContinue | Out-Null
            
        if (Test-Path $SandboxDir) {
            Write-Host "  -> Partial cleanup completed. Some files may remain." -ForegroundColor Yellow
            Write-Host "     Close any IDEs/editors and try again, or manually delete:" -ForegroundColor Yellow
            Write-Host "     $SandboxDir" -ForegroundColor Yellow
        } else {
            Write-Host "  -> Done (after retry)." -ForegroundColor Green
        }
    }

    # Bonus: If this was the last test sandbox, remove the parent temp dir.
    if (Test-Path $SandboxParentDir) {
        try {
            if (-not (Get-ChildItem -Path $SandboxParentDir -ErrorAction SilentlyContinue)) {
                Write-Host "Parent 'temp_test_environment' is now empty. Removing it as well."
                Remove-Item -Path $SandboxParentDir -Recurse -Force -ErrorAction Stop
                Write-Host "  -> Done." -ForegroundColor Green
            }
        }
        catch {
            Write-Host "  -> Could not remove parent directory (files in use)." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "Layer 3 sandbox directory not found. Nothing to remove."
}

Write-Host "`nCleanup complete." -ForegroundColor Green
Write-Host ""