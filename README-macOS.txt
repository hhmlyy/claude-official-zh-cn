Claude 官方中文与原生工具 — macOS
仅适配 Claude Desktop 3.6556.2；一个包自动识别 Intel 和 Apple Silicon，包含中文注册及原生工具适配。

使用方法
1. 完整解压 ZIP，保留整个目录，包括 native_macos.py、catalogs、runtime 和入口脚本。
2. 等 Claude 当前任务结束，再正常退出 Claude。
3. 双击 Install-ClaudeZhCN.command，或在终端运行 bash ./Install-ClaudeZhCN.command。
4. 安装成功后会重新打开 Claude。在账号菜单 → Language → 中文（简体）中选择。

默认应用位置为 /Applications/Claude.app。Intel 和 Apple Silicon 的 macOS 26.5.2 默认同时安装中文与原生工具适配。Release 包内置两种处理器的 Python 运行环境，不需要另行安装 Python；运行时只解压所需架构到临时目录，结束后清理。源码包不含运行环境，需要 Python 3.9 或更新版本。应用和资源必须通过固定文件哈希检查，其他系统版本或构建会停止并显示原因。原生模式检测到 Claude 仍在运行时会停止，不会强制结束任务。

语言 JSON 优先从 catalogs 读取；缺少时从固定官方地址下载并核验。Release 离线包包含两份原始官方 JSON；GitHub 自动生成的 Source code 压缩包不包含语言资源。

原生适配只恢复本地功能开关。电脑控制仍需在 Claude 设置中启用、取得系统的辅助功能与屏幕录制权限，并由模型和网关支持相应工具协议。官方操作检查和确认逻辑保持原样。浏览器使用官方内置浏览器，不更改网关地址或密钥。

上述 Intel / macOS 26.5.2 / Claude 3.6556.2 组合已在 Magpie 下实机验证：辅助功能与屏幕录制均已授予，Claude 自带电脑控制通过界面点击计算 1+2，截图确认结果为 3；内置浏览器成功打开并读取 https://example.com。结果仅覆盖此构建及测试时的模型、网关组合。Apple Silicon 的官方应用文件已在隔离副本验证安装、回滚和还原；实际电脑控制与浏览器操作仍需在 Apple Silicon 机器上验证。

入口未使用 Apple 开发者证书签名或公证。如果系统拦截首次打开，请查看 Apple 的官方说明：
https://support.apple.com/zh-cn/102445
原生模式修改 app.asar、同步摘要并本地临时重签最外层应用，嵌套原生组件保持原文件。临时签名不等于开发者签名或公证，系统可能要求重新授权。仅中文模式不重签名。
临时签名移除依赖官方证书的应用标识与钥匙串访问组，官方 WebAuthn、硬件密钥及企业登录共享钥匙串能力不能保留。保留 hardened runtime，但为加载官方 Electron 框架，对本应用设置 disable-library-validation 例外，放宽其动态库签名限制。完整还原可恢复官方签名与原权限项。

遇到错误时，终端会显示原因。版本或文件校验不符时停止，不要把其他版本的文件覆盖进应用。

还原与检查
Claude 有任务运行时，只准备待安装副本，不替换当前应用：
bash ./Install-ClaudeZhCN.command --prepare
任务结束并正常退出后，再执行普通安装命令。

正常退出 Claude 后，在本目录打开终端完整还原：
bash ./Install-ClaudeZhCN.command --restore
只检查当前安装状态：
bash ./Install-ClaudeZhCN.command --check
原生模式恢复具有官方签名的完整应用和安装前的浏览器开关，中文一并撤销。完整应用备份和安装记录保存在下列目录中的 native-x86_64 或 native-arm64：
~/Library/Application Support/ClaudeOfficialZhHans/3.6556.2/

仅执行原有中文注册：
bash ./Install-ClaudeZhCN.command --language-only
仅中文模式的还原加上 --restore --language-only，会恢复注册文件并移除两份中文 JSON。原生模式安装后应使用普通 --restore 完整还原。

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
