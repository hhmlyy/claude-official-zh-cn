# Claude 官方简体中文注册工具 · macOS / Windows

让 Claude Desktop 的本地界面（包括 Magpie 的第三方网关模式）在原有 **Language** 菜单中出现 **中文（简体）**，并加载 Claude 官方主语言包和动态语言包。

这是独立的社区工具，与 Anthropic、Claude、Magpie 无隶属关系。“官方”仅指翻译资源来源。安装会修改本地应用的语言注册 JavaScript，应用更新可能覆盖修改。

macOS 包包含经过固定文件指纹核验的 **Intel 和 Apple Silicon 原生电脑控制与内置浏览器适配**，与中文共用安装、检查和还原入口。此适配只支持下文指定的构建，不提供云端账号权益。

## 直接下载双击包

从 [GitHub Release](https://github.com/hhmlyy/claude-official-zh-cn/releases/latest) 下载对应平台 ZIP，**完整解压后再双击入口**。macOS 的一个包自动识别 Intel 和 Apple Silicon，并内置所需运行环境；Windows 包提供中文注册。两个包均内置经过固定 SHA-256 核验的官方主语言包和动态语言包，安装时无需联网下载资源。

| 平台 | 下载 | 解压后双击 |
| --- | --- | --- |
| macOS | [Claude-ZhCN-macOS-3.6556.2.zip](https://github.com/hhmlyy/claude-official-zh-cn/releases/latest/download/Claude-ZhCN-macOS-3.6556.2.zip) | `Install-ClaudeZhCN.command` |
| Windows | [Claude-ZhCN-Windows-3.6556.2.zip](https://github.com/hhmlyy/claude-official-zh-cn/releases/latest/download/Claude-ZhCN-Windows-3.6556.2.zip) | `ClaudeZhCN.cmd` |

仅适配 **Claude Desktop 3.6556.2**。Windows 请先从托盘完全退出 Claude；受保护的 WindowsApps/MSIX 安装不支持修改。macOS ZIP 保留入口的可执行权限，不需要手动 `chmod`；未使用 Apple 开发者证书签名或公证，系统可能要求首次打开确认，参见 [Apple 官方说明](https://support.apple.com/zh-cn/102445)。

macOS 安装器不再锁定单一系统版本，仍只接受 **Claude 3.6556.2 的已登记官方构建**。该版本应用声明最低 macOS 13，电脑控制的内置检查要求 macOS 14 或更新版本；后台窗口控制还受 Claude 自身的系统版本条件限制。未实测的系统不能保证功能正常。安装前请等待任务结束并退出 Claude。此模式会本地重签应用并放宽该应用的动态库签名限制，官方硬件密钥等登录能力无法保留；脚本保存完整官方备份以供还原。

每个包附有 `README.txt` 和许可说明；Release 同时提供 `SHA256SUMS.txt` 供核对下载完整性。GitHub 自动生成的 **Source code** 压缩包不含官方语言资源，开发者可按下方源码使用说明运行。

## 支持范围

| 项目 | 当前范围 |
| --- | --- |
| Claude Desktop | **3.6556.2**，四个关键资源的 SHA-256 必须全部匹配 |
| macOS | 系统自带 Bash 3.2；默认安装位置 `/Applications/Claude.app` |
| macOS 原生工具适配 | **Intel x86_64 或 Apple Silicon arm64 / Claude 3.6556.2 已登记构建**；电脑控制需 macOS 14+，Release 包自带运行环境，源码使用 Python **3.9+** |
| Windows | Windows PowerShell **5.1** 或 PowerShell **7** |
| 安装目录 | 当前用户可写的普通安装目录；Windows 自动发现，两个平台均可手动指定 |
| MSIX / Microsoft Store | 能检查；**不支持修改受保护的 WindowsApps 目录** |
| 界面验证 | 同一前端资源的 macOS 版本已验证菜单切换；Windows 图形界面尚未实机验证 |

已直接核对官方 Windows x64 和 ARM64 MSIX **3.6556.2.0** 中的四个前端文件，与已验证方案逐字节一致。脚本不会根据版本号推测兼容性；遇到不同文件会停止。这不表示受保护的 MSIX 安装已可修改，也不表示 Windows 原生功能已经适配。

当前官方 Windows 安装器可能安装为 MSIX，因此本版**不能保证所有默认安装方式都能使用**。脚本会明确提示，不会接管 WindowsApps 权限、重新打包 MSIX、改动应用签名或更改系统策略。官方安装说明见 [Deploy Claude Desktop for Windows](https://support.claude.com/en/articles/12622703-deploy-claude-desktop-for-windows)。

## Windows 源码使用

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

## macOS 源码使用

下载并解压完整源码，在解压目录中打开终端。上述已核验的 Intel 和 Apple Silicon 系统默认将中文与原生工具一并安装，**先等待 Claude 的任务结束，再正常退出 Claude**：

```bash
bash ./Install-ClaudeZhCN.command
```

原生适配检测到 Claude 仍在运行时会停止，不会强制结束任务。安装成功后默认重新打开应用；在账号菜单 → **Language → 中文（简体）** 中选择语言。若希望双击运行，先执行一次 `chmod +x ./Install-ClaudeZhCN.command`。

Claude 有任务运行时，可以只构建并验证待安装副本：

```bash
bash ./Install-ClaudeZhCN.command --prepare
```

准备操作不替换当前应用；任务结束并退出 Claude 后，再执行普通安装命令。

只检查、不下载、不修改：

```bash
bash ./Install-ClaudeZhCN.command --check
```

正常退出 Claude 后，撤销本工具的安装。原生模式恢复具有官方签名的完整应用及安装前的浏览器开关，中文注册一并撤销：

```bash
bash ./Install-ClaudeZhCN.command --restore
```

自定义应用位置，安装后自行重启：

```bash
bash ./Install-ClaudeZhCN.command --app '/path/to/Claude.app' --no-restart
```

只需要原有中文注册功能时，明确指定：

```bash
bash ./Install-ClaudeZhCN.command --language-only
```

`--language-only` 不需要 Python，沿用原来的语言资源安装方式。Release 包内置经过哈希验证的 Intel 与 Apple Silicon Python 运行环境；源码模式需要 Python 3.9 或更新版本。两种模式均使用标准库和系统自带 `codesign`，不需要 Node.js 或第三方 Python 库。`--native` 可以显式要求原生模式，平台或文件指纹不符时会停止。

脚本优先使用 `catalogs` 目录中的两份官方 JSON，也可通过 `--catalog-dir '/path/to/catalogs'` 指定目录。缺少文件时下载并核验官方资源，下载失败不会修改实际应用。

默认备份目录如下，兼容此前 Mac 注册脚本的 `shared-52.original.js` 备份，也可通过 `--backup-dir` 指定：

```text
~/Library/Application Support/ClaudeOfficialZhHans/3.6556.2/
```

原生模式在此目录的 `native-x86_64` 或 `native-arm64` 中保留完整官方应用备份及安装记录；准备时另有一个待安装副本。应用和备份必须属于当前用户可写的普通目录。安装会修改 `app.asar`、同步完整性摘要并本地临时重签最外层应用，嵌套原生组件保持官方原文件。临时签名不等于 Apple 开发者签名或公证，首次使用时系统可能要求重新授权。

临时签名移除依赖官方团队证书的应用标识与钥匙串访问组，因此不能保留官方 WebAuthn、硬件密钥及企业登录共享钥匙串能力。保留 hardened runtime，但为加载官方签名的 Electron 框架，对本应用设置 `disable-library-validation` 例外；这会放宽本应用的动态库签名限制，见 [Apple 文档](https://developer.apple.com/documentation/BundleResources/Entitlements/com.apple.security.cs.disable-library-validation)。完整还原可恢复原签名与权限项。

安装只恢复本地可用性条件。电脑控制仍需在 Claude 设置中启用，并取得系统的辅助功能与屏幕录制权限；实际操作还取决于所选模型和网关的工具协议支持。官方操作检查与确认逻辑保持原样。浏览器使用 Claude 自带浏览器，仅开启现有 `builtinBrowserEnabled` 配置；不会改动网关地址或密钥。

仅中文模式的 `--restore --language-only` 会恢复注册文件并移除两份中文 JSON，包括安装前已存在且哈希匹配的文件；这一模式不重新签名。原生模式安装后请使用普通 `--restore` 完整还原。

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
  native_macos.py
  catalogs\
    zh-Hans.official.json
    zh-Hans.dynamic.official.json
```

必须保存原始响应内容，不能保存为网页、手工格式化或改变编码。文件不符合上表哈希时脚本会拒绝安装。Windows 可使用 `-CatalogDirectory 'D:\官方语言包'`，macOS 可使用 `--catalog-dir '/path/to/catalogs'` 指定已有文件目录。下载失败发生在修改应用前。

官方主语言包并不覆盖此版全部英文键，少量新文案会继续显示英文。本工具不自行翻译这些内容。

## 修改内容

- 向经过固定哈希核验的 `shared-52-uHFNjl7C.js` 末尾加入两个 `zh-Hans` 列表注册语句，保留原有语言菜单和语言偏好保存逻辑。
- 写入 `ion-dist/i18n/zh-Hans.json` 和 `ion-dist/i18n/dynamic/zh-Hans.json`，每次都校验 SHA-256。
- 中文注册保留英文 JSON、语言加载模块、账号信息和 `app.asar`。
- macOS 原生模式只向主进程功能表加入电脑控制可用性与已核验系统版本上限两项定义，重算 ASAR 和应用签名；原生截图、点击及操作检查代码保持原样。浏览器只修改当前本地 gateway 配置的 `builtinBrowserEnabled`，不修改模型、地址、密钥或云端权益。
- Windows 备份保存原始注册文件与资源存在状态，安装、还原中途失败时尝试回滚。macOS 备份保存原始注册文件，采用逐文件暂存替换。两个平台均拒绝覆盖校验不符的资源。

## 验证

macOS 已在 Bash 3.2 下使用真实应用资源的隔离副本验证安装、重复安装、完整注册检查、离线还原和重复还原，并核对还原后的注册文件及英文 JSON 哈希。实际安装的 Claude 也通过只读注册检查；语言菜单切换此前已实机验证。

Intel 更新版、Apple Silicon 更新版及通用版的官方应用副本均已通过隔离测试，验证 ASAR 中其余文件逐字节一致、安装失败回滚、重复安装、完整还原及官方签名恢复；另验证配置修改与还原不会覆盖其他字段。这些自动测试不替换实际应用，Apple Silicon 图形界面和实际电脑控制仍需实机验证。

上述 Intel / macOS 26.5.2 / Claude 3.6556.2 组合也已在 Magpie 下完成实机验证：辅助功能与屏幕录制均已授予；Claude 自带的 `mcp__computer-use__open_application`、`screenshot` 和 `computer_batch` 打开计算器，通过界面点击计算 `1+2`，截图确认结果为 `3`；`mcp__Claude_Browser__navigate` 和 `read_page` 成功打开并读取 `https://example.com`。实机结果仅覆盖此构建及测试时的模型、网关组合。

```bash
CLAUDE_NATIVE_FIXTURE='/path/to/pristine/Claude.app' PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s tests -p test_native_macos.py -v
```

未设置 `CLAUDE_NATIVE_FIXTURE` 时仅运行配置测试。原生适配参考 [Claude-Native-Unlock](https://github.com/canner0725-byte/Claude-Native-Unlock) 的 ASAR 处理与功能表定位方法，许可及使用范围见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

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

本仓库自行编写的脚本、测试与文档使用 [MIT License](LICENSE)。Claude、Magpie 及官方语言包的权利归各自权利人所有，不包含在本仓库 MIT 许可中。源码树不包含官方翻译文件；Release 离线包附带前文已注明来源与哈希的两份原始官方 JSON，其权利不因打包而转移。本项目不分发 Claude 应用或修改后的应用主包。
