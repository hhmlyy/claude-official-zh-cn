Claude 官方中文与原生工具 — macOS
不按 Claude Desktop 版本号限制；一个包自动识别 Intel 和 Apple Silicon，包含中文注册及原生工具适配。安装器要求应用的资源结构可识别，结构变化可能导致不兼容。

使用方法
1. 完整解压 ZIP，保留整个目录，包括 native_macos.py、catalogs、runtime 和入口脚本。
2. 等 Claude 当前任务结束，再正常退出 Claude。
3. 双击 Install-ClaudeZhCN.command，或在终端运行 bash ./Install-ClaudeZhCN.command。
4. 安装成功后会重新打开 Claude。在账号菜单 → Language → 中文（简体）中选择。

默认应用位置为 /Applications/Claude.app。Intel 和 Apple Silicon 共用入口，默认安装中文与原生工具适配。电脑控制还需满足 Claude 的系统要求；未实测的系统不能保证功能正常。Release 包内置两种处理器的 Python 运行环境，不需要另行安装 Python；运行时只解压所需架构到临时目录，结束后清理。源码包不含运行环境，需要兼容的 Python。安装器检查官方签名、应用结构和备份完整性，不兼容时会停止并显示原因。检测到 Claude 仍在运行时会停止，不会强制结束任务。

语言 JSON 优先从 catalogs 读取；缺少时从固定官方地址下载并核验。Release 离线包包含两份原始官方 JSON；GitHub 自动生成的 Source code 压缩包不包含语言资源。

原生适配只恢复本地功能开关。电脑控制仍需在 Claude 设置中启用、取得系统的辅助功能与屏幕录制权限，并由模型和网关支持相应工具协议。官方操作检查和确认逻辑保持原样。浏览器使用官方内置浏览器，不更改网关地址或密钥。

Intel Mac 已在 Magpie 环境下实机验证电脑控制和内置浏览器。结果仅覆盖测试时使用的应用构建、系统、模型和网关。Apple Silicon 的官方应用文件已在隔离副本验证安装、回滚和还原；实际图形操作仍需实机验证。

入口未使用 Apple 开发者证书签名或公证。如果系统拦截首次打开，请查看 Apple 的官方说明：
https://support.apple.com/zh-cn/102445
两种模式均修改语言资源、同步 ASAR 摘要并本地临时重签应用；原生模式还修改 app.asar。如果 Electron 框架包含内嵌摘要，也会更新该摘要并重签框架与辅助进程；其他原生组件保持原文件。临时签名不等于开发者签名或公证，系统可能要求重新授权。
临时签名移除依赖官方证书的应用标识与钥匙串访问组，官方 WebAuthn、硬件密钥及企业登录共享钥匙串能力不能保留。保留 hardened runtime，但为加载 Electron 框架，对应用设置 disable-library-validation 例外；需要重签辅助进程时，也会对这些进程设置同一例外。这会放宽相应进程的动态库签名限制。完整还原可恢复官方签名与原权限项。

遇到错误时，终端会显示原因。资源结构、签名或文件校验不符时停止。

还原与检查
Claude 有任务运行时，只准备待安装副本，不替换当前应用：
bash ./Install-ClaudeZhCN.command --prepare
任务结束并正常退出后，再执行普通安装命令。

正常退出 Claude 后，在本目录打开终端完整还原：
bash ./Install-ClaudeZhCN.command --restore
只检查当前安装状态：
bash ./Install-ClaudeZhCN.command --check
原生模式恢复具有官方签名的完整应用和安装前的浏览器开关，中文一并撤销。完整应用备份和安装记录保存在下列目录中的 native-x86_64 或 native-arm64：
~/Library/Application Support/ClaudeOfficialZhHans/<Claude版本>/

仅执行中文注册：
bash ./Install-ClaudeZhCN.command --language-only
仅中文模式的还原加上 --restore --language-only，会恢复完整的官方应用备份。原生模式安装后应使用普通 --restore 完整还原。

资源与许可
本工具是独立社区项目；“官方”仅指翻译资源来源。自行编写的脚本与文档采用附带的 MIT License；原生适配引用与上游许可见 THIRD_PARTY_NOTICES.md。官方语言资源权利归 Anthropic，不在 MIT 授权范围内。本项目不分发 Claude 应用或修改后的应用主包。
主语言包：
https://claude.ai/i18n/zh-Hans.json?v=dc0f674b04d1
SHA-256: dc0f674b04d17055671f06a5645294352d98780128e944706b5411d53cae038b
动态语言包：
https://claude.ai/i18n/dynamic/zh-Hans.json?v=8121dfdeb012
SHA-256: 8121dfdeb01237ec4b46a9d252d777da2ee2c5edcf35b885a76fc82810c09fb4

项目与完整说明：
https://github.com/hhmlyy/claude-official-zh-cn
