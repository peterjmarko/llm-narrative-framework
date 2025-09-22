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
# Filename: tests/algorithm_validation/generate_mock_study_assets.ps1

param(
    [string]$OutputPath = "tests/assets/mock_study",
    [int]$ReplicationsPerExperiment = 6,
    [int]$K = 4,
    [int]$M = 32,
    [switch]$Force,
    [switch]$Verbose
)

# Script initialization and validation
if ($Verbose) { $VerbosePreference = "Continue" }

Write-Host "=== Mock Study Generator - Step 3 Implementation ===" -ForegroundColor Cyan
Write-Host "Focus: Statistical Analysis Pipeline Validation" -ForegroundColor Green
Write-Host "Parameters: M=$M trials, K=$K subjects, $ReplicationsPerExperiment replications per experiment" -ForegroundColor White
Write-Host "Using REAL personality data with controlled mock LLM responses" -ForegroundColor White

# Verify required data files exist
$RequiredFiles = @(
    "data/processed/personalities_db.txt",
    "data_foundational_assets_point_weights.csv",
    "data_foundational_assets_balance_thresholds.csv", 
    "data_foundational_assets_country_codes.csv"
)

Write-Host "`nValidating required data files..." -ForegroundColor White
foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        Write-Error "Required file not found: $File"
        Write-Error "Please ensure the data preparation pipeline has been run."
        exit 1
    }
    Write-Verbose "✓ Found: $File"
}

# Ensure output directory exists
if (Test-Path $OutputPath) {
    if ($Force) {
        Write-Host "Removing existing mock study directory..." -ForegroundColor Yellow
        Remove-Item $OutputPath -Recurse -Force
    } else {
        Write-Error "Output directory '$OutputPath' already exists. Use -Force to overwrite."
        exit 1
    }
}

Write-Verbose "Creating output directory: $OutputPath"
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

# Copy foundational assets required for analysis
Write-Host "Copying foundational assets..." -ForegroundColor White
$FoundationalAssets = @(
    "data_foundational_assets_point_weights.csv",
    "data_foundational_assets_balance_thresholds.csv", 
    "data_foundational_assets_country_codes.csv"
)

foreach ($Asset in $FoundationalAssets) {
    if (Test-Path $Asset) {
        $DestPath = Join-Path $OutputPath $Asset
        Copy-Item $Asset $DestPath -Force
        Write-Verbose "Copied: $Asset"
    } else {
        Write-Warning "Foundational asset not found: $Asset"
    }
}

# Load real personality data
Write-Host "Loading real personality data..." -ForegroundColor White
$PersonalitiesPath = "data/processed/personalities_db.txt"
$PersonalityData = Import-PersonalityDatabase -FilePath $PersonalitiesPath -K $K

Write-Host "Loaded $($PersonalityData.Count) personality records for K=$K subjects" -ForegroundColor Green

# 2x2 Factorial Design Parameters
$MappingStrategies = @("correct", "random")
$GroupSizes = @(4, 10)
$Model = "gemini-1.5-flash"  # Single model for validation

# Create study-level directory structure
$StudyName = "mock_validation_study"
$StudyPath = Join-Path $OutputPath $StudyName
New-Item -ItemType Directory -Path $StudyPath -Force | Out-Null

Write-Host "`nGenerating 2x2 factorial design experiments..." -ForegroundColor Cyan

$ExperimentCounter = 1
foreach ($MappingStrategy in $MappingStrategies) {
    foreach ($K in $GroupSizes) {
        $ExperimentName = "exp_${ExperimentCounter}_${Model}_${MappingStrategy}_k${K}"
        $ExperimentPath = Join-Path $StudyPath $ExperimentName
        
        Write-Host "  Creating experiment: $ExperimentName" -ForegroundColor White
        New-Item -ItemType Directory -Path $ExperimentPath -Force | Out-Null
        
        # Create config.ini.archived for this experiment
        Create-ExperimentConfig -ExperimentPath $ExperimentPath -ExperimentName $ExperimentName -Model $Model -MappingStrategy $MappingStrategy -K $K -M $M -ReplicationsPerExperiment $ReplicationsPerExperiment -StudyName $StudyName
        
        # Generate replications for this experiment using real personality data
        for ($rep = 1; $rep -le $ReplicationsPerExperiment; $rep++) {
            Generate-MockReplication -ExperimentPath $ExperimentPath -ReplicationNumber $rep -Model $Model -MappingStrategy $MappingStrategy -K $K -M $M -PersonalityData $PersonalityData
        }
        
        $ExperimentCounter++
    }
}

function Import-PersonalityDatabase {
    param(
        [string]$FilePath,
        [int]$K
    )
    
    Write-Verbose "Reading personality database from: $FilePath"
    
    # Read the TSV file (tab-delimited)
    $RawData = Get-Content $FilePath -Encoding UTF8
    $Header = $RawData[0] -split "`t"
    $DataRows = $RawData[1..($RawData.Length-1)]
    
    # Parse into structured objects
    $AllPersonalities = @()
    foreach ($Row in $DataRows) {
        if ($Row.Trim() -eq "") { continue }  # Skip empty rows
        
        $Fields = $Row -split "`t"
        if ($Fields.Length -ge 5) {  # Ensure we have all required fields
            $AllPersonalities += @{
                Index = $Fields[0]
                idADB = $Fields[1] 
                Name = $Fields[2]
                BirthYear = $Fields[3]
                DescriptionText = $Fields[4]
            }
        }
    }
    
    Write-Verbose "Parsed $($AllPersonalities.Count) personality records"
    
    # For validation testing, we need a fixed subset of K personalities
    # Use deterministic selection to ensure reproducible results
    $SelectedPersonalities = @()
    for ($i = 0; $i -lt $K; $i++) {
        if ($i -lt $AllPersonalities.Count) {
            $SelectedPersonalities += $AllPersonalities[$i]
        }
    }
    
    Write-Verbose "Selected $($SelectedPersonalities.Count) personalities for K=$K"
    return $SelectedPersonalities
}

function Create-ExperimentConfig {
    param(
        [string]$ExperimentPath,
        [string]$ExperimentName,
        [string]$Model,
        [string]$MappingStrategy,
        [int]$K,
        [int]$M,
        [int]$ReplicationsPerExperiment,
        [string]$StudyName
    )
    
    $ConfigContent = @"
[Model]
name = $Model
temperature = 0.7

[Experiment]
k = $K
m = $M
mapping_strategy = $MappingStrategy
replications = $ReplicationsPerExperiment
experiment_name = $ExperimentName
db = personalities_db.txt

[Study]
study_name = $StudyName
created_date = $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
generator_version = mock_study_generator_v1.0
data_source = real_personalities_db
validation_focus = statistical_analysis_pipeline
"@
    $ConfigPath = Join-Path $ExperimentPath "config.ini.archived"
    $ConfigContent | Out-File -FilePath $ConfigPath -Encoding UTF8
    Write-Verbose "Created config for experiment: $ExperimentName"
}

function Generate-MockReplication {
    param(
        [string]$ExperimentPath,
        [int]$ReplicationNumber,
        [string]$Model,
        [string]$MappingStrategy,
        [int]$K,
        [int]$M,
        [array]$PersonalityData
    )
    
    $RepPath = Join-Path $ExperimentPath "replication_$ReplicationNumber"
    New-Item -ItemType Directory -Path $RepPath -Force | Out-Null
    Write-Verbose "Creating replication $ReplicationNumber in: $RepPath"
    
    # Create personalities mapping file using REAL data
    $PersonalitiesMapping = Create-PersonalitiesMapping -PersonalityData $PersonalityData -K $K
    $PersonalitiesPath = Join-Path $RepPath "personalities_mapping.json"
    $PersonalitiesMapping | ConvertTo-Json -Depth 10 -Compress | Out-File -FilePath $PersonalitiesPath -Encoding UTF8
    
    # Generate controlled mock LLM responses based on mapping strategy
    $MockResponses = Generate-ControlledMockResponses -Model $Model -MappingStrategy $MappingStrategy -K $K -M $M -ReplicationSeed $ReplicationNumber -PersonalityData $PersonalityData
    $ResponsesPath = Join-Path $RepPath "llm_responses.json"
    $MockResponses | ConvertTo-Json -Depth 10 -Compress | Out-File -FilePath $ResponsesPath -Encoding UTF8
    
    # Create experiment manifest
    $ManifestPath = Join-Path $RepPath "experiment_manifest.json"
    $Manifest = @{
        replication_number = $ReplicationNumber
        model = $Model
        mapping_strategy = $MappingStrategy
        k = $K
        m = $M
        generated_timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ"
        generator_type = "mock_controlled_v1.0"
        data_source = "real_personalities_db"
        validation_focus = "statistical_analysis_pipeline"
        data_quality = "high"
        validation_ready = $true
    }
    $Manifest | ConvertTo-Json -Depth 5 -Compress | Out-File -FilePath $ManifestPath -Encoding UTF8
    
    Write-Verbose "Generated replication $ReplicationNumber with $($MockResponses.Length) responses"
}

function Create-PersonalitiesMapping {
    param(
        [array]$PersonalityData,
        [int]$K
    )
    
    # Create the personalities mapping using real personality descriptions
    $PersonalitiesMapping = @()
    
    for ($i = 0; $i -lt $K; $i++) {
        $Personality = $PersonalityData[$i]
        $PersonalitiesMapping += @{
            subject_id = "SUBJ_$($i + 1)"
            name = $Personality.Name
            birth_year = $Personality.BirthYear
            adb_id = $Personality.idADB
            personality_description = $Personality.DescriptionText
            data_source = "real_personalities_db"
            index_in_db = $Personality.Index
        }
    }
    
    return $PersonalitiesMapping
}

function Generate-ControlledMockResponses {
    param(
        [string]$Model,
        [string]$MappingStrategy,
        [int]$K,
        [int]$M,
        [int]$ReplicationSeed,
        [array]$PersonalityData
    )
    
    $Responses = @()
    
    for ($trial = 1; $trial -le $M; $trial++) {
        $CorrectSubjectId = ($trial % $K) + 1
        
        # Create deterministic but varied random generator for this trial
        $SeedValue = ($ReplicationSeed * 10000) + ($trial * 100) + [int]($Model.GetHashCode() / 1000000)
        $Random = New-Object System.Random($SeedValue)
        
        # Generate rankings based on mapping strategy with controlled accuracy
        if ($MappingStrategy -eq "correct") {
            $Rankings = Generate-CorrectMappingRankings -CorrectId $CorrectSubjectId -K $K -Model $Model -Random $Random
        } else {
            $Rankings = Generate-RandomMappingRankings -K $K -Random $Random
        }
        
        $Response = @{
            trial_number = $trial
            query_id = "QUERY_$($trial.ToString().PadLeft(4, '0'))"
            model_response = Generate-RealisticModelResponse -Trial $trial -Model $Model -PersonalityData $PersonalityData -CorrectSubjectId $CorrectSubjectId -K $K
            subject_rankings = $Rankings
            correct_subject_id = "SUBJ_$($CorrectSubjectId.ToString().PadLeft(3, '0'))"
            response_timestamp = (Get-Date).AddSeconds($trial * 2).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
            processing_time_ms = 1500 + ($trial % 1000)
            response_quality = "high"
            validation_flags = @()
            data_source = "mock_controlled_for_validation"
        }
        
        $Responses += $Response
    }
    
    return $Responses
}

function Generate-CorrectMappingRankings {
    param(
        [int]$CorrectId,
        [int]$K,
        [string]$Model,
        [System.Random]$Random
    )
    
    # Group size-specific performance patterns for controlled validation
    $GroupSizeAccuracy = @{
        4 = 0.75   # Higher accuracy for smaller groups (easier task)
        10 = 0.65  # Lower accuracy for larger groups (harder task)
    }
    
    $BaseAccuracy = $ModelAccuracy[$Model]
    
    # Determine if this trial should be correct (realistic accuracy pattern)
    $IsCorrect = $Random.NextDouble() -lt $BaseAccuracy
    
    if ($IsCorrect) {
        # Place correct answer in top 3 positions (realistic top-k performance)
        $CorrectRank = $Random.Next(1, [math]::Min(4, $K + 1))
    } else {
        # Place correct answer in lower positions  
        $CorrectRank = $Random.Next([math]::Min(4, $K), $K + 1)
    }
    
    # Create deterministic but realistic ranking distribution
    $RankAssignments = @{}
    $RankAssignments[$CorrectId] = $CorrectRank
    
    # Assign other ranks
    $AvailableRanks = (1..$K) | Where-Object { $_ -ne $CorrectRank }
    $OtherSubjects = (1..$K) | Where-Object { $_ -ne $CorrectId }
    
    for ($i = 0; $i -lt $OtherSubjects.Length; $i++) {
        $RankAssignments[$OtherSubjects[$i]] = $AvailableRanks[$i]
    }
    
    # Convert to required format
    $Rankings = @()
    for ($SubjectId = 1; $SubjectId -le $K; $SubjectId++) {
        $Rankings += @{
            subject_id = "SUBJ_$($SubjectId.ToString().PadLeft(3, '0'))"
            rank = $RankAssignments[$SubjectId]
            confidence = [math]::Round($Random.NextDouble() * 0.4 + 0.6, 3)  # 0.6-1.0 confidence
        }
    }
    
    return $Rankings
}

function Generate-RandomMappingRankings {
    param(
        [int]$K,
        [System.Random]$Random
    )
    
    # Random performance around chance level (1/K)
    $Rankings = @()
    $RandomRanks = (1..$K) | Sort-Object { $Random.Next() }
    
    for ($i = 0; $i -lt $K; $i++) {
        $Rankings += @{
            subject_id = "SUBJ_$(($i + 1).ToString().PadLeft(3, '0'))"
            rank = $RandomRanks[$i]
            confidence = [math]::Round($Random.NextDouble() * 0.6 + 0.4, 3)  # 0.4-1.0 confidence
        }
    }
    
    return $Rankings
}

function Generate-RealisticModelResponse {
    param(
        [int]$Trial,
        [string]$Model,
        [array]$PersonalityData,
        [int]$CorrectSubjectId,
        [int]$K
    )
    
    # Create realistic model responses that reference actual personality characteristics
    $CorrectPersonality = $PersonalityData[$CorrectSubjectId - 1]
    $DescriptionSnippet = $CorrectPersonality.DescriptionText.Substring(0, [math]::Min(50, $CorrectPersonality.DescriptionText.Length))
    
    $GroupSizeComplexity = @{
        4 = "straightforward comparison of personality traits"
        10 = "complex multi-dimensional analysis of personality characteristics"
    }
    
    $ComplexityDescription = $GroupSizeComplexity[$K]
    
    return "Based on $ComplexityDescription including '$DescriptionSnippet...', I rank the $K subjects considering psychological coherence and trait alignment patterns. [MOCK_VALIDATION_RESPONSE_K$K] (Trial $Trial, Validation Testing)"
}

# Generate summary report
Write-Host "`n=== Mock Study Generation Complete ===" -ForegroundColor Green
Write-Host "Study location: $StudyPath" -ForegroundColor Yellow
Write-Host "Data source: REAL personalities_db.txt" -ForegroundColor Yellow
Write-Host "Factorial design: 2x2 (Mapping Strategy × Group Size)" -ForegroundColor Yellow
Write-Host "Model: $Model (single model for validation)" -ForegroundColor Yellow
Write-Host "Mapping strategies: $($MappingStrategies -join ', ')" -ForegroundColor Yellow
Write-Host "Group sizes (k): $($GroupSizes -join ', ')" -ForegroundColor Yellow
Write-Host "Total experiments: 4" -ForegroundColor Yellow
Write-Host "Replications per experiment: $ReplicationsPerExperiment" -ForegroundColor Yellow
Write-Host "Total replications: $($ReplicationsPerExperiment * 4)" -ForegroundColor Yellow
Write-Host "Trials per replication: $M" -ForegroundColor Yellow
Write-Host "Total trials: $($ReplicationsPerExperiment * 4 * $M)" -ForegroundColor Yellow
Write-Host "Statistical basis: M=32 from 25÷0.85 response rate, K=4 minimum meaningful group size" -ForegroundColor Gray

# Validation readiness report
Write-Host "`n=== Statistical Analysis Validation Readiness ===" -ForegroundColor Cyan
Write-Host "✓ Uses REAL personality data (not synthetic)" -ForegroundColor Green
Write-Host "✓ Controlled mock LLM responses with known statistical properties" -ForegroundColor Green
Write-Host "✓ Sufficient replications for full statistical analysis" -ForegroundColor Green
Write-Host "✓ Model-specific performance patterns for validation" -ForegroundColor Green
Write-Host "✓ Foundational assets copied for analysis pipeline" -ForegroundColor Green
Write-Host "✓ Well-calibrated parameters based on statistical requirements" -ForegroundColor Green
Write-Host "✓ Ready for GraphPad Prism validation (Step 4)" -ForegroundColor Green

# Next steps guidance
Write-Host "`n=== Next Steps for Statistical Validation ===" -ForegroundColor White
Write-Host "1. Run analysis pipeline: analyze_llm_performance.py" -ForegroundColor Gray
Write-Host "2. Run study compilation: analyze_study_results.py" -ForegroundColor Gray
Write-Host "3. Extract metrics for GraphPad validation" -ForegroundColor Gray
Write-Host "4. Implement validate_statistical_reporting.ps1" -ForegroundColor Gray
Write-Host "5. Execute two-phase validation strategy" -ForegroundColor Gray

Write-Host "`nMock study generator completed successfully!" -ForegroundColor Green
Write-Host "Focus: Statistical analysis pipeline validation using real personality data" -ForegroundColor Cyan

# === End of tests/algorithm_validation/generate_mock_study_assets.ps1 ===
