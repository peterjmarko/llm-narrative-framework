# Filename: src/ArgBuilder.ps1

# This is a simple, pure function for building the command-line arguments.
# It is completely isolated for reliable testing.
function Build-ExperimentArgs {
    param(
        [string]$TargetDirectory,
        [int]$StartRep,
        [int]$EndRep,
        [string]$Notes,
        [switch]$ShowDetails
    )

    $pythonArgs = @("src/replication_manager.py")

    if (-not [string]::IsNullOrEmpty($TargetDirectory)) { $pythonArgs += $TargetDirectory }
    if ($StartRep) { $pythonArgs += "--start-rep", $StartRep }
    if ($EndRep) { $pythonArgs += "--end-rep", $EndRep }
    if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }
    if ($ShowDetails.IsPresent) { $pythonArgs += "--verbose" }
    
    return $pythonArgs
}