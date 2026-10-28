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
$script:RegistryFile = 'assets/v1/shared-52-uHFNjl7C.js'
$script:OriginalHash = '83537e599f2f6720c2a0a245162e44a5c7431e22872a32ed16ea716e65ded08a'
$script:RegisteredHash = 'f556db8f04ce27ffbe7b7113ff6fe7169274a9e8a4f083ca202dded325ecf3d4'
$script:EnglishFiles = @{
    'assets/v1/shared-50-DopKwmK0.js' = '371cdd50d64068beb78178a0eb988ace10eb077f79e72f7b915688c2d68e418d'
    'i18n/en-US.json' = '58c827a85e1ab35f8cd8934db9521842e169505432b407c3eaf129c322e7aa40'
    'i18n/dynamic/en-US.json' = '79e1211bbad7a95915bd982f97e36757e8c54cabe00130a6c673e6796d85cee9'
}
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

    [IO.File]::AppendAllText($original, "`n/* ClaudeOfficialZhHans: damaged registration */")
    $before = Get-Sha256 $original
    Assert-Fails { Get-LanguageStatus $root } 'Reject an unrecognized registration marker'
    Assert-True ((Get-Sha256 $original) -eq $before) 'Rejected registration leaves files unchanged'
    Copy-Verified $savedOriginal $original $script:OriginalHash
    $main = Join-Path $root 'i18n/zh-Hans.json'
    [IO.File]::WriteAllText($main, '{}')
    Assert-Fails { Get-LanguageStatus $root } 'Reject an existing unknown Chinese catalog'
    Assert-True ([IO.File]::ReadAllText($main) -eq '{}') 'Unknown catalog is not overwritten'
    Remove-Item -LiteralPath $main

    $otherBuild = New-Fixture 'other-build'
    $oldRegistry = Join-Path $otherBuild $script:RegistryFile
    $otherRegistry = Join-Path $otherBuild 'assets/v1/shared-other-build.js'
    Move-Item -LiteralPath $oldRegistry -Destination $otherRegistry
    [IO.File]::AppendAllText($otherRegistry, "`n/* another compatible build */`n")
    $otherHash = Get-Sha256 $otherRegistry
    Assert-True ((Get-LanguageStatus $otherBuild).OriginalHash -eq $otherHash) 'Find a compatible registration in a renamed, changed bundle'

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

        $stage = New-Stage
        Get-OfficialCatalogs $CatalogDirectory $stage
        Invoke-LanguageChange $root $backup $stage Install
        $stateFile = Join-Path $backup 'state.json'
        $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $state.Version = '3.6556.2'
        [IO.File]::WriteAllText($stateFile, ($state | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
        Invoke-LanguageChange $root $backup (New-Stage) Restore
        Assert-True ((Get-LanguageStatus $root).RegistryHash -eq $script:OriginalHash) 'Restore accepts the legacy backup format'

        $stage = New-Stage
        Get-OfficialCatalogs $CatalogDirectory $stage
        $backup = Join-Path $workspace 'backup-other-build'
        Invoke-LanguageChange $otherBuild $backup $stage Install
        Assert-True (Get-LanguageStatus $otherBuild).Installed 'Install with a different bundle hash'
        Invoke-LanguageChange $otherBuild $backup (New-Stage) Restore
        Assert-True ((Get-Sha256 $otherRegistry) -eq $otherHash) 'Restore the changed bundle exactly'

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
