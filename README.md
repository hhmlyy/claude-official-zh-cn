# Claude 官方简体中文注册工具 · macOS / Windows

让 Claude Desktop 的本地界面（包括 Magpie 的第三方网关模式）在原有 **Language** 菜单中出现 **中文（简体）**，并加载 Claude 官方主语言包和动态语言包。

这是独立的社区工具，与 Anthropic、Claude、Magpie 无隶属关系。“官方”仅指翻译资源来源。安装会修改本地应用的语言注册 JavaScript，应用更新可能覆盖修改。

## 支持范围

| 项目 | 当前范围 |
| --- | --- |
| Claude Desktop | **3.6556.2**，四个关键资源的 SHA-256 必须全部匹配 |
| macOS | 系统自带 Bash 3.2；默认安装位置 `/Applications/Claude.app` |
| Windows | Windows PowerShell **5.1** 或 PowerShell **7** |
| 安装目录 | 当前用户可写的普通安装目录；Windows 自动发现，两个平台均可手动指定 |
| MSIX / Microsoft Store | 能检查；**不支持修改受保护的 WindowsApps 目录** |
| 界面验证 | 同一前端资源的 macOS 版本已验证菜单切换；Windows 图形界面尚未实机验证 |

已直接核对官方 Windows x64 MSIX **3.6556.2.0** 中的四个前端文件，与已验证方案逐字节一致。脚本不会根据版本号推测兼容性；遇到不同文件会停止。Windows ARM64 尚未核对。

当前官方 Windows 安装器可能安装为 MSIX，因此本版**不能保证所有默认安装方式都能使用**。脚本会明确提示，不会接管 WindowsApps 权限、重新打包 MSIX、改动应用签名或更改系统策略。官方安装说明见 [Deploy Claude Desktop for Windows](https://support.claude.com/en/articles/12622703-deploy-claude-desktop-for-windows)。

## Windows 使用

1. 下载并解压本仓库全部文件，不能只下载 `.cmd`。
2. 从系统托盘菜单完全退出 Claude。
3. 双击 **`ClaudeZhCN.cmd`**。
4. 重新打开 Claude，在账号菜单 → **Language → 中文（简体）** 中选择。

脚本先读取同目录 `catalogs` 中的官方 JSON；没有本地文件时，从下方固定官方地址下载并校验。无需 Node.js、Python 或第三方翻译插件。首次运行 `.cmd` 只对本次 PowerShell 进程使用 `ExecutionPolicy Bypass`，不会执行 `Set-ExecutionPolicy` 或永久修改执行策略。

只检查、不下载、不修改：

```powershell
.\ClaudeZhCN.cmd -Action Check
```

撤销注册，恢复原文件，并保留安装前已存在的官方中文 JSON：

```powershell
.\ClaudeZhCN.cmd -Action Restore
```

指定普通安装目录中的 `ion-dist`：

```powershell
.\ClaudeZhCN.cmd -ResourcesPath 'C:\path\to\Claude\resources\ion-dist'
```

也可以指定其上一级 `resources`、Claude 程序目录或 MSIX 解压根目录。多个安装目录同时存在时，脚本会要求明确指定。

原始注册文件及安装前资源存在状态保存在：

```text
%LOCALAPPDATA%\ClaudeOfficialZhHans\3.6556.2\<安装路径摘要>\
```

## macOS 使用

下载并解压本仓库，在解压目录中打开终端，运行：

```bash
bash ./Install-ClaudeZhCN.command
```

脚本默认退出并重新打开 Claude。完成后，在账号菜单 → **Language → 中文（简体）** 中选择。若希望双击运行，先执行一次 `chmod +x ./Install-ClaudeZhCN.command`。

只检查、不下载、不修改：

```bash
bash ./Install-ClaudeZhCN.command --check
```

撤销注册，恢复原始注册文件，并移除两份官方中文 JSON：

```bash
bash ./Install-ClaudeZhCN.command --restore
```

自定义应用位置，或自行退出和重启：

```bash
bash ./Install-ClaudeZhCN.command --app '/path/to/Claude.app' --no-restart
```

脚本同样优先使用下方 `catalogs` 目录中的两份官方 JSON，也可通过 `--catalog-dir '/path/to/catalogs'` 指定目录。缺少文件时下载并核验官方资源，下载失败不会修改应用。无需 Node.js、Python 或其他依赖。

默认备份目录如下，兼容此前 Mac 注册脚本的 `shared-52.original.js` 备份，也可通过 `--backup-dir` 指定：

```text
~/Library/Application Support/ClaudeOfficialZhHans/3.6556.2/
```

macOS 还原会移除两份中文 JSON，包括安装前已存在且哈希匹配的文件。脚本逐个暂存并校验文件后替换；中断后可重新安装或还原。修改应用资源会影响原签名校验，脚本不重签名。

## 官方资源与下载失败处理

| 资源 | 官方地址 | SHA-256 |
| --- | --- | --- |
| 主语言包（37,640 项） | [zh-Hans.json](https://claude.ai/i18n/zh-Hans.json?v=dc0f674b04d1) | `dc0f674b04d17055671f06a5645294352d98780128e944706b5411d53cae038b` |
| 动态语言包（49 项） | [dynamic/zh-Hans.json](https://claude.ai/i18n/dynamic/zh-Hans.json?v=8121dfdeb012) | `8121dfdeb01237ec4b46a9d252d777da2ee2c5edcf35b885a76fc82810c09fb4` |

如果命令行下载遇到 **403 / Cloudflare 验证**，请用浏览器打开上面两个官方链接，完成网站正常验证后，按原始 JSON 文件保存，放置为：

```text
claude-official-zh-cn\
  ClaudeZhCN.cmd
  Install-ClaudeZhCN.ps1
  Install-ClaudeZhCN.command
  catalogs\
    zh-Hans.official.json
    zh-Hans.dynamic.official.json
```

必须保存原始响应内容，不能保存为网页、手工格式化或改变编码。文件不符合上表哈希时脚本会拒绝安装。Windows 可使用 `-CatalogDirectory 'D:\官方语言包'`，macOS 可使用 `--catalog-dir '/path/to/catalogs'` 指定已有文件目录。下载失败发生在修改应用前。

官方主语言包并不覆盖此版全部英文键，少量新文案会继续显示英文。本工具不自行翻译这些内容。

## 修改内容

- 向经过固定哈希核验的 `shared-52-uHFNjl7C.js` 末尾加入两个 `zh-Hans` 列表注册语句，保留原有语言菜单和语言偏好保存逻辑。
- 写入 `ion-dist/i18n/zh-Hans.json` 和 `ion-dist/i18n/dynamic/zh-Hans.json`，每次都校验 SHA-256。
- 保留英文 JSON、语言加载模块、账号信息、Magpie 网关配置及 `app.asar`。不用于解锁付费或云端功能。
- Windows 备份保存原始注册文件与资源存在状态，安装、还原中途失败时尝试回滚。macOS 备份保存原始注册文件，采用逐文件暂存替换。两个平台均拒绝覆盖校验不符的资源。

## 验证

macOS 已在 Bash 3.2 下使用真实应用资源的隔离副本验证安装、重复安装、完整注册检查、离线还原和重复还原，并核对还原后的注册文件及英文 JSON 哈希。实际安装的 Claude 也通过只读注册检查；语言菜单切换此前已实机验证。

`tests/Test-Installer.ps1` 使用官方 Windows 安装包中的真实资源进行验证。默认测试注册结果的固定哈希、未知版本拒绝、未知中文文件拒绝、文件替换和原始文件还原。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\Test-Installer.ps1 -MsixPath 'D:\Claude.msix'
```

如果另外提供上述两份官方 JSON，增加完整安装、重复安装、还原、既有语言包保留和中途失败回滚验证：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\Test-Installer.ps1 -MsixPath 'D:\Claude.msix' -CatalogDirectory 'D:\官方语言包'
```

测试仅在系统临时目录中创建模拟应用目录，不改动已安装的 Claude。GitHub Actions 使用 Windows PowerShell 5.1 和 PowerShell 7 运行不依赖语言包下载的测试。

## 许可

本仓库自行编写的脚本、测试与文档使用 [MIT License](LICENSE)。Claude、Magpie 及官方语言包的权利归各自权利人所有，不包含在本仓库 MIT 许可中。仓库不分发 Claude 应用、修改后的应用主包或官方翻译文件。
