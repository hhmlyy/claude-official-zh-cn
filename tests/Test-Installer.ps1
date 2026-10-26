#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$MsixPath,
    [string]$CatalogDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$installer = Join-Path (Split-Path $PSScriptRoot -Parent) 'Install-ClaudeZhCN.ps1'
$tokens = $null
$parseErrors = $null
$null = [Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw ($parseErrors | Out-String) }
. $installer -CatalogDirectory $CatalogDirectory
Add-Type -AssemblyName System.IO.Compression.FileSystem
$workspace = Join-Path ([IO.Path]::GetTempPath()) ('claude-zh-test-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $workspace
# Resolve /tmp symlinks on macOS; real Windows paths are unchanged.
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    $workspace = (Get-Item -LiteralPath $workspace).FullName
    if ($workspace.StartsWith('/var/')) { $workspace = '/private' + $workspace }
    if ($workspace.StartsWith('/tmp/')) { $workspace = '/private' + $workspace }
}
$script:Passed = 0
$archive = [IO.Compression.ZipFile]::OpenRead((Get-Item -LiteralPath $MsixPath).FullName)

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    $script:Passed++
    Write-Host "PASS: $Message"
}

function Assert-Fails([scriptblock]$Body, [string]$Message) {
    $failed = $false
    try { & $Body } catch { $failed = $true }
    Assert-True $failed $Message
}

function New-Fixture([string]$Name) {
    $root = Join-Path $workspace $Name
    $files = @($script:RegistryFile) + @($script:EnglishFiles.Keys)
    foreach ($file in $files) {
        $destination = Join-Path $root $file
        $null = New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force
        $entry = $archive.GetEntry('app/resources/ion-dist/' + $file)
        if ($null -eq $entry) { throw "Missing official MSIX entry: $file" }
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination)
    }
    return $root
}

function New-Stage {
    $path = Join-Path $workspace ([guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $path
    return $path
}

try {
    $root = New-Fixture 'baseline'
    $status = Get-LanguageStatus $root
    Assert-True (-not $status.Installed) 'Official Windows resource hashes match; original state detected'
    Assert-True ((Find-IonDist $root) -eq $root) 'Explicit ion-dist path detection'
    $original = Join-Path $root $script:RegistryFile
    $patched = Join-Path $workspace 'registered.js'
    New-RegisteredBundle $original $patched
    Assert-True ((Get-Sha256 $patched) -eq $script:RegisteredHash) 'Registration bytes match the proven fixed SHA-256'
    Copy-Verified $patched $original $script:RegisteredHash
    Assert-True ((Get-Sha256 $original) -eq $script:RegisteredHash) 'Atomic replacement of an existing file'
    $entry = $archive.GetEntry('app/resources/ion-dist/' + $script:RegistryFile)
    $savedOriginal = Join-Path $workspace 'original.js'
    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $savedOriginal)
    Copy-Verified $savedOriginal $original $script:OriginalHash
    Assert-True ((Get-Sha256 $original) -eq $script:OriginalHash) 'Restore original bytes exactly'

    [IO.File]::AppendAllText($original, 'unknown version')
    $before = Get-Sha256 $original
    Assert-Fails { Get-LanguageStatus $root } 'Reject an unknown application bundle'
    Assert-True ((Get-Sha256 $original) -eq $before) 'Version rejection leaves files unchanged'
    Copy-Verified $savedOriginal $original $script:OriginalHash
    $main = Join-Path $root 'i18n/zh-Hans.json'
    [IO.File]::WriteAllText($main, '{}')
    Assert-Fails { Get-LanguageStatus $root } 'Reject an existing unknown Chinese catalog'
    Assert-True ([IO.File]::ReadAllText($main) -eq '{}') 'Unknown catalog is not overwritten'
    Remove-Item -LiteralPath $main

    if ($CatalogDirectory) {
        # Use real official translations supplied locally, never synthetic replacements.
        $stage = New-Stage
        Get-OfficialCatalogs $CatalogDirectory $stage
        $backup = Join-Path $workspace 'backup-roundtrip'
        Invoke-LanguageChange $root $backup $stage Install
        Assert-True (Get-LanguageStatus $root).Installed 'Full offline installation'
        $originalBackupHash = Get-Sha256 (Join-Path $backup 'registry.original.js')
        Invoke-LanguageChange $root $backup $stage Install
        Assert-True ((Get-Sha256 (Join-Path $backup 'registry.original.js')) -eq $originalBackupHash) 'Repeated installation preserves the original backup'
        Invoke-LanguageChange $root $backup (New-Stage) Restore
        Assert-True ((Get-LanguageStatus $root).RegistryHash -eq $script:OriginalHash) 'Round-trip restores the original registry'
        Assert-True (-not (Test-Path -LiteralPath $main)) 'Restore removes a catalog introduced by the tool'
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $root 'i18n/dynamic/zh-Hans.json'))) 'Restore removes the introduced dynamic catalog'
        Invoke-LanguageChange $root $backup (New-Stage) Restore
        Assert-True ((Get-LanguageStatus $root).RegistryHash -eq $script:OriginalHash) 'Repeated restore is safe'

        $preserved = New-Fixture 'preserve-existing'
        $stage = New-Stage
        Get-OfficialCatalogs $CatalogDirectory $stage
        $catalog = $script:Catalogs[0]
        Copy-Verified (Join-Path $stage $catalog.Name) (Join-Path $preserved $catalog.Target) $catalog.Hash
        $backup = Join-Path $workspace 'backup-preserve'
        Invoke-LanguageChange $preserved $backup $stage Install
        Invoke-LanguageChange $preserved $backup (New-Stage) Restore
        Assert-True ((Get-Sha256 (Join-Path $preserved $catalog.Target)) -eq $catalog.Hash) 'Restore preserves a pre-existing official main catalog'
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $preserved $script:Catalogs[1].Target))) 'Restore respects the different original states of both catalogs'

        $rollbackRoot = New-Fixture 'rollback'
        $stage = New-Stage
        Get-OfficialCatalogs $CatalogDirectory $stage
        [IO.File]::WriteAllText((Join-Path $stage $script:Catalogs[1].Name), '{}')
        $backup = Join-Path $workspace 'backup-rollback'
        Assert-Fails { Invoke-LanguageChange $rollbackRoot $backup $stage Install } 'A corrupted second staged catalog aborts installation'
        Assert-True ((Get-LanguageStatus $rollbackRoot).RegistryHash -eq $script:OriginalHash) 'Failure leaves the original application registry intact'
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $rollbackRoot $script:Catalogs[0].Target))) 'Failure rolls back the already-written main catalog'
    } else {
        Write-Host 'Offline catalog round-trip skipped: provide -CatalogDirectory to enable it.'
    }
    Write-Host "All $script:Passed assertions passed. Temporary fixtures will be removed."
} finally {
    $archive.Dispose()
    Remove-Item -LiteralPath $workspace -Recurse -Force
}
