#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Install', 'Check', 'Restore')]
    [string]$Action = 'Install',
    [string]$ResourcesPath,
    [string]$CatalogDirectory = (Join-Path $PSScriptRoot 'catalogs')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# The old hash is used only to find backups created by previous installers.
$script:LegacyOriginalHash = '83537e599f2f6720c2a0a245162e44a5c7431e22872a32ed16ea716e65ded08a'
$script:Catalogs = @(
    @{
        Name = 'zh-Hans.official.json'; Target = 'i18n/zh-Hans.json'
        Url = 'https://claude.ai/i18n/zh-Hans.json?v=dc0f674b04d1'
        Hash = 'dc0f674b04d17055671f06a5645294352d98780128e944706b5411d53cae038b'
    },
    @{
        Name = 'zh-Hans.dynamic.official.json'; Target = 'i18n/dynamic/zh-Hans.json'
        Url = 'https://claude.ai/i18n/dynamic/zh-Hans.json?v=8121dfdeb012'
        Hash = '8121dfdeb01237ec4b46a9d252d777da2ee2c5edcf35b885a76fc82810c09fb4'
    }
)

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-RegularFile([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "不是普通文件：$Path"
    }
}

function Assert-Hash([string]$Path, [string]$Expected) {
    Assert-RegularFile $Path
    if ((Get-Sha256 $Path) -ne $Expected) { throw "文件校验不符，已停止：$Path" }
}

function Assert-PlainDirectory([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    while ($null -ne $item) {
        if ($item -isnot [IO.DirectoryInfo] -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "目录或其上级目录是链接，已停止：$Path"
        }
        $item = $item.Parent
    }
}

function Get-BytesSha256([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-RegistrationInfo([string]$Path) {
    Assert-RegularFile $Path
    $bytes = [IO.File]::ReadAllBytes($Path)
    $text = [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
    $marker = "`n/* ClaudeOfficialZhHans: register the official Chinese catalogs. */`n"
    $position = $text.IndexOf($marker, [StringComparison]::Ordinal)
    $originalText = if ($position -ge 0) { $text.Substring(0, $position) } else { $text }
    $prefix = '(?<name>[A-Za-z_$][\w$]*)=\[(?<list>"en-US"(?:,"[A-Za-z0-9-]+")+)\];function [A-Za-z_$][\w$]*\('
    $first = [regex]::Matches($originalText, $prefix + '[A-Za-z_$][\w$]*\)\{return \k<name>\.includes\(')
    $second = [regex]::Matches($originalText, $prefix + '[A-Za-z_$][\w$]*,[A-Za-z_$][\w$]*=\k<name>\)\{let [A-Za-z_$][\w$]*=new Map;')
    if ($first.Count -eq 0 -or $second.Count -eq 0) { return $null }
    if ($first.Count -ne 1 -or $second.Count -ne 1 -or
        $first[0].Groups['list'].Value -cne $second[0].Groups['list'].Value -or
        $first[0].Groups['list'].Value -notmatch '"ja-JP"' -or
        $first[0].Groups['list'].Value -match '"zh-Hans"' -or
        $first[0].Groups['name'].Value -ceq $second[0].Groups['name'].Value -or
        -not $originalText.Contains('/i18n/dynamic/') -or $originalText.Contains('ClaudeOfficialZhHans')) {
        throw '语言注册结构不匹配，未修改。'
    }
    $tail = $marker
    foreach ($match in @($first[0], $second[0])) {
        $name = $match.Groups['name'].Value
        $tail += ('if (!{0}.includes("zh-Hans")) {0}.push("zh-Hans");' -f $name) + "`n"
    }
    if ($position -ge 0 -and $text.Substring($position) -cne $tail) { throw '语言注册标记已被修改。' }
    $original = [Text.Encoding]::UTF8.GetBytes($originalText)
    $registered = [byte[]]($original + [Text.Encoding]::ASCII.GetBytes($tail))
    return [pscustomobject]@{
        OriginalHash = Get-BytesSha256 $original
        RegisteredHash = Get-BytesSha256 $registered
        RegistryHash = Get-BytesSha256 $bytes
        Registered = ($position -ge 0)
        RegisteredBytes = $registered
    }
}

function Get-LanguageStatus([string]$IonDist) {
    Assert-PlainDirectory $IonDist
    foreach ($relative in @('i18n/en-US.json', 'i18n/dynamic/en-US.json')) {
        $path = Join-Path $IonDist $relative
        Assert-PlainDirectory (Split-Path -Parent $path)
        Assert-RegularFile $path
    }
    $assets = Join-Path $IonDist 'assets/v1'
    Assert-PlainDirectory $assets
    $registries = @(Get-ChildItem -LiteralPath $assets -Filter 'shared-*.js' -File -Force | ForEach-Object {
        $info = Get-RegistrationInfo $_.FullName
        if ($null -ne $info) { [pscustomobject]@{ Path = $_.FullName; Info = $info } }
    })
    if ($registries.Count -ne 1) {
        throw '无法唯一定位兼容的语言注册结构，未修改。'
    }
    $count = 0
    foreach ($catalog in $script:Catalogs) {
        $target = Join-Path $IonDist $catalog.Target
        Assert-PlainDirectory (Split-Path -Parent $target)
        if (Test-Path -LiteralPath $target) { Assert-Hash $target $catalog.Hash; $count++ }
    }
    $info = $registries[0].Info
    return [pscustomobject]@{
        RegistryPath = $registries[0].Path
        RegistryHash = $info.RegistryHash
        OriginalHash = $info.OriginalHash
        RegisteredHash = $info.RegisteredHash
        Registered = $info.Registered
        Installed = ($info.Registered -and $count -eq 2)
    }
}

function Find-IonDist([string]$Path) {
    $candidates = [Collections.Generic.List[string]]::new()
    if ($Path) {
        $full = [IO.Path]::GetFullPath($Path)
        foreach ($suffix in @('', 'ion-dist', 'resources/ion-dist', 'app/resources/ion-dist')) {
            $candidates.Add((Join-Path $full $suffix))
        }
    } else {
        foreach ($process in @(Get-Process -Name Claude -ErrorAction SilentlyContinue)) {
            if ($process.Path) { $candidates.Add((Join-Path (Split-Path $process.Path) 'resources/ion-dist')) }
        }
        foreach ($rootName in @('AnthropicClaude', 'Claude')) {
            $root = Join-Path $env:LOCALAPPDATA $rootName
            $candidates.Add((Join-Path $root 'resources/ion-dist'))
            foreach ($dir in @(Get-ChildItem -LiteralPath $root -Directory -Filter 'app-*' -ErrorAction SilentlyContinue)) {
                $candidates.Add((Join-Path $dir.FullName 'resources/ion-dist'))
            }
        }
        if (Get-Command Get-AppxPackage -ErrorAction SilentlyContinue) {
            foreach ($package in @(Get-AppxPackage | Where-Object { $_.Name -in @('Claude', 'AnthropicPBC.Claude') })) {
                $candidates.Add((Join-Path $package.InstallLocation 'app/resources/ion-dist'))
            }
        }
    }
    $found = @($candidates | Where-Object {
        (Test-Path -LiteralPath (Join-Path $_ 'i18n/en-US.json') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $_ 'assets/v1') -PathType Container)
    } | Select-Object -Unique)
    if ($found.Count -eq 0) { throw '找不到可识别的 Claude ion-dist 目录。可用 -ResourcesPath 指定；打包为 ASAR 的资源暂不支持。' }
    if ($found.Count -gt 1) { throw "发现多个安装目录，请用 -ResourcesPath 指定一个：`n$($found -join "`n")" }
    return (Get-Item -LiteralPath $found[0]).FullName.TrimEnd([char[]]'\/')
}

function Assert-Writable([string]$IonDist) {
    if ($IonDist -match '[\\/]WindowsApps[\\/]') {
        throw '此安装位于受保护的 WindowsApps/MSIX 目录，本版不支持原位修改。未修改权限或应用文件。'
    }
    $status = Get-LanguageStatus $IonDist
    foreach ($path in @($status.RegistryPath, (Join-Path $IonDist 'i18n/en-US.json'), (Join-Path $IonDist 'i18n/dynamic/en-US.json'))) {
        $handle = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
        $handle.Dispose()
    }
}

function Copy-Verified([string]$Source, [string]$Target, [string]$Hash) {
    Assert-Hash $Source $Hash
    Assert-PlainDirectory (Split-Path -Parent $Target)
    $temporary = Join-Path (Split-Path -Parent $Target) ('.claude-zh-' + [guid]::NewGuid().ToString('N'))
    try {
        [IO.File]::Copy($Source, $temporary, $false)
        Assert-Hash $temporary $Hash
        if (Test-Path -LiteralPath $Target) {
            Assert-RegularFile $Target
            [IO.File]::Replace($temporary, $Target, [NullString]::Value)
        } else {
            [IO.File]::Move($temporary, $Target)
        }
        Assert-Hash $Target $Hash
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function New-RegisteredBundle([string]$Original, [string]$Destination) {
    $info = Get-RegistrationInfo $Original
    if ($null -eq $info -or $info.Registered) { throw '原始语言注册结构不匹配，未修改。' }
    [IO.File]::WriteAllBytes($Destination, $info.RegisteredBytes)
    Assert-Hash $Destination $info.RegisteredHash
}

function Get-OfficialCatalogs([string]$Directory, [string]$Stage) {
    $oldTls = [Net.ServicePointManager]::SecurityProtocol
    try {
        [Net.ServicePointManager]::SecurityProtocol = $oldTls -bor [Net.SecurityProtocolType]::Tls12
        foreach ($catalog in $script:Catalogs) {
            $local = Join-Path $Directory $catalog.Name
            $destination = Join-Path $Stage $catalog.Name
            if (Test-Path -LiteralPath $local) {
                Assert-Hash $local $catalog.Hash
                [IO.File]::Copy($local, $destination, $false)
            } else {
                Write-Host "下载官方资源：$($catalog.Url)"
                try {
                    Invoke-WebRequest -Uri $catalog.Url -UseBasicParsing -OutFile $destination -TimeoutSec 60
                } catch {
                    throw "官方资源下载失败。请按 README 从浏览器保存两个官方 JSON 到 catalogs 后重试。`n$($_.Exception.Message)"
                }
            }
            Assert-Hash $destination $catalog.Hash
        }
    } finally { [Net.ServicePointManager]::SecurityProtocol = $oldTls }
}

function Invoke-LanguageChange(
    [string]$IonDist, [string]$Backup, [string]$Stage,
    [ValidateSet('Install', 'Restore')][string]$Operation
) {
    $status = Get-LanguageStatus $IonDist
    $registry = $status.RegistryPath
    $original = Join-Path $Backup 'registry.original.js'
    $stateFile = Join-Path $Backup 'state.json'
    if ($Operation -eq 'Install' -and $status.Installed) { Write-Host '官方中文已安装，无需重复修改。'; return }
    if ($Operation -eq 'Restore' -and -not $status.Registered -and -not (Test-Path -LiteralPath $stateFile)) {
        Write-Host '未发现本工具的安装记录，无需还原。'; return
    }
    Assert-PlainDirectory (Split-Path -Parent $registry)
    if (Test-Path -LiteralPath $Backup) { Assert-PlainDirectory $Backup }
    if (Test-Path -LiteralPath $stateFile) {
        Assert-RegularFile $stateFile
        $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($state.IonDist -ne $IonDist -or $state.Version -notin @('3.6556.2', 'structural-v1') -or
            $state.HadMain -isnot [bool] -or $state.HadDynamic -isnot [bool]) { throw '备份记录不匹配，未修改。' }
        Assert-Hash $original $status.OriginalHash
    } else {
        if ($Operation -eq 'Restore' -or $status.Registered) { throw '缺少原始文件备份，未修改。' }
        $state = [pscustomobject]@{
            Version = 'structural-v1'; IonDist = $IonDist
            HadMain = (Test-Path -LiteralPath (Join-Path $IonDist $script:Catalogs[0].Target))
            HadDynamic = (Test-Path -LiteralPath (Join-Path $IonDist $script:Catalogs[1].Target))
        }
        $null = New-Item -ItemType Directory -Path $Backup -Force
        Assert-PlainDirectory $Backup
        if (Test-Path -LiteralPath $original) { Assert-Hash $original $status.OriginalHash }
        else { Copy-Verified $registry $original $status.OriginalHash }
        [IO.File]::WriteAllText($stateFile, ($state | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    }
    if ($Operation -eq 'Install') { New-RegisteredBundle $original (Join-Path $Stage 'registered.js') }

    # Save the pre-operation state so a failed install or restore can roll back.
    $changes = [Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt 2; $index++) {
        $catalog = $script:Catalogs[$index]
        $keep = if ($index -eq 0) { $state.HadMain } else { $state.HadDynamic }
        $changes.Add([pscustomobject]@{
            Target = (Join-Path $IonDist $catalog.Target)
            Source = (Join-Path $Stage $catalog.Name)
            Hash = $catalog.Hash; Delete = ($Operation -eq 'Restore' -and -not $keep)
        })
    }
    $bundleSource = if ($Operation -eq 'Install') { Join-Path $Stage 'registered.js' } else { $original }
    $bundleHash = if ($Operation -eq 'Install') { $status.RegisteredHash } else { $status.OriginalHash }
    $changes.Add([pscustomobject]@{ Target = $registry; Source = $bundleSource; Hash = $bundleHash; Delete = $false })
    $undo = [Collections.Generic.List[object]]::new()
    try {
        foreach ($change in $changes) {
            $previous = $null
            $previousHash = $null
            if (Test-Path -LiteralPath $change.Target) {
                Assert-RegularFile $change.Target
                $previousHash = Get-Sha256 $change.Target
                $allowed = if ($change.Target -eq $registry) { $status.RegistryHash } else { $change.Hash }
                if ($previousHash -ne $allowed) { throw '检查后文件发生变化，已停止。' }
                $previous = Join-Path $Stage ('undo-' + $undo.Count)
                [IO.File]::Copy($change.Target, $previous, $false)
            } elseif ($change.Target -eq $registry) { throw '注册文件已消失，已停止。' }
            $undo.Add([pscustomobject]@{ Target = $change.Target; Previous = $previous; Hash = $previousHash; NewHash = $change.Hash })
            if ($change.Delete) {
                if (Test-Path -LiteralPath $change.Target) { Remove-Item -LiteralPath $change.Target }
            } elseif ($Operation -eq 'Restore' -and $change.Target -ne $registry) {
                # A pre-existing official catalog must still be present when restoring.
                Assert-Hash $change.Target $change.Hash
            } else { Copy-Verified $change.Source $change.Target $change.Hash }
        }
        $after = Get-LanguageStatus $IonDist
        if ($after.RegistryHash -ne $bundleHash) { throw '最终文件校验失败。' }
    } catch {
        $failure = $_
        for ($index = $undo.Count - 1; $index -ge 0; $index--) {
            $entry = $undo[$index]
            try {
                if (Test-Path -LiteralPath $entry.Target) {
                    Assert-RegularFile $entry.Target
                    if ((Get-Sha256 $entry.Target) -notin @($entry.Hash, $entry.NewHash)) { throw '文件已被其他程序修改。' }
                }
                if ($entry.Previous) { Copy-Verified $entry.Previous $entry.Target $entry.Hash }
                elseif (Test-Path -LiteralPath $entry.Target) { Remove-Item -LiteralPath $entry.Target }
            } catch { Write-Warning "自动回滚未完成：$($entry.Target)。备份：$Backup。$($_.Exception.Message)" }
        }
        throw $failure
    }
    if ($Operation -eq 'Install') { Write-Host '已注册官方中文。重新打开 Claude，在账号菜单 → Language → 中文（简体）中选择。' }
    else { Write-Host '已还原语言注册文件，保留安装前已有的官方中文资源。' }
}

# Dot-sourcing loads the functions for verification without touching an application.
if ($MyInvocation.InvocationName -eq '.') { return }
$stage = $null
try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw '入口脚本仅支持 Windows。' }
    $ionDist = Find-IonDist $ResourcesPath
    $status = Get-LanguageStatus $ionDist
    Write-Host "Claude 语言资源结构校验通过：$ionDist"
    if ($Action -eq 'Check') {
        if ($status.Installed) { Write-Host '状态：官方中文已完整注册。' }
        else { Write-Host '状态：语言资源结构匹配，尚未完整注册。' }
        if ($ionDist -match '[\\/]WindowsApps[\\/]') { Write-Host '安装类型：受保护的 MSIX，本版不支持原位修改。' }
        exit 0
    }
    if ($Action -eq 'Install' -and $status.Installed) { Write-Host '官方中文已安装，无需重复修改。'; exit 0 }
    Assert-Writable $ionDist
    if (@(Get-Process -Name Claude -ErrorAction SilentlyContinue).Count -gt 0) { throw '请先从托盘菜单完全退出 Claude，再运行脚本。' }
    $stage = Join-Path ([IO.Path]::GetTempPath()) ('claude-zh-' + [guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $stage
    if ($Action -eq 'Install') { Get-OfficialCatalogs $CatalogDirectory $stage }
    $digest = [Security.Cryptography.SHA256]::Create()
    try { $pathKey = ([BitConverter]::ToString($digest.ComputeHash([Text.Encoding]::UTF8.GetBytes($ionDist.ToLowerInvariant())))).Replace('-', '').Substring(0, 16) }
    finally { $digest.Dispose() }
    $legacyBackup = Join-Path $env:LOCALAPPDATA "ClaudeOfficialZhHans/3.6556.2/$pathKey"
    if ($status.OriginalHash -eq $script:LegacyOriginalHash -and (Test-Path -LiteralPath (Join-Path $legacyBackup 'state.json'))) {
        $backup = $legacyBackup
    } else {
        $backup = Join-Path $env:LOCALAPPDATA "ClaudeOfficialZhHans/by-content/$pathKey/$($status.OriginalHash)"
    }
    Invoke-LanguageChange $ionDist $backup $stage $Action
    exit 0
} catch {
    Write-Host "错误：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($stage -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
