Claude 官方简体中文注册工具 — macOS 离线双击包
工具版本：1.0.0；仅适配 Claude Desktop 3.6556.2。

使用方法
1. 完整解压 ZIP，保留 catalogs 文件夹与入口脚本的相对位置。
2. 双击 Install-ClaudeZhCN.command，等待终端显示结果。
3. 脚本会退出并重新打开 Claude。在账号菜单 → Language → 中文（简体）中选择。

本包已经包含两份原始官方语言 JSON，不需要联网下载资源，也不需要手动设置可执行权限或安装其他依赖。默认应用位置为 /Applications/Claude.app。兼容 Apple 芯片与 Intel Mac 的系统 Bash，具体应用资源仍须通过全部哈希检查。

入口未使用 Apple 开发者证书签名或公证。如果系统拦截首次打开，请查看 Apple 的官方说明：
https://support.apple.com/zh-cn/102445
安装会修改应用资源并影响原签名校验；脚本不重签名。

遇到错误时，终端会显示原因。版本或文件校验不符时停止，不要把其他版本的文件覆盖进应用。

还原与检查
如需撤销注册，在本目录打开终端运行：
bash ./Install-ClaudeZhCN.command --restore
只检查当前安装状态：
bash ./Install-ClaudeZhCN.command --check
还原会移除两份中文 JSON，并从以下备份恢复原始注册文件：
~/Library/Application Support/ClaudeOfficialZhHans/3.6556.2/

资源与许可
本工具是独立社区项目；“官方”仅指翻译资源来源。自行编写的脚本与文档采用附带的 MIT License；官方语言资源权利归 Anthropic，不在 MIT 授权范围内。本包不包含 Claude 应用或修改后的应用主包。
主语言包：
https://claude.ai/i18n/zh-Hans.json?v=dc0f674b04d1
SHA-256: dc0f674b04d17055671f06a5645294352d98780128e944706b5411d53cae038b
动态语言包：
https://claude.ai/i18n/dynamic/zh-Hans.json?v=8121dfdeb012
SHA-256: 8121dfdeb01237ec4b46a9d252d777da2ee2c5edcf35b885a76fc82810c09fb4

项目与完整说明：
https://github.com/hhmlyy/claude-official-zh-cn
