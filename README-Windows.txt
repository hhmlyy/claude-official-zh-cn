Claude 官方简体中文注册工具 — Windows 离线双击包
工具版本：1.0.0；仅适配 Claude Desktop 3.6556.2。

使用方法
1. 右键 ZIP 选择“全部解压缩”，不要在压缩包内部直接运行。
2. 从系统托盘菜单完全退出 Claude。
3. 双击 ClaudeZhCN.cmd，等待控制台显示结果。
4. 重新打开 Claude，在账号菜单 → Language → 中文（简体）中选择。

请保留 Install-ClaudeZhCN.ps1 和 catalogs 文件夹与入口的相对位置。本包已经包含两份原始官方语言 JSON，安装时不需要联网下载资源，也不需要安装 PowerShell 7、Node.js、Python 或翻译插件。入口使用 Windows 自带的 Windows PowerShell 5.1，执行后保留结果窗口。

支持范围
仅支持当前用户可写的普通安装目录。受保护的 WindowsApps/MSIX/Microsoft Store 安装会明确提示不支持，包内脚本不会接管该目录权限。已核对官方 x64 资源，Windows ARM64 尚未核对。Windows 图形界面尚未实机验证。
找不到安装目录、发现多个目录或资源版本不匹配时，脚本会显示原因并停止。自定义路径等用法见项目完整说明。

还原与检查
如需撤销注册，在本目录打开命令提示符运行：
ClaudeZhCN.cmd -Action Restore
只检查当前安装状态：
ClaudeZhCN.cmd -Action Check
备份保存在：
%LOCALAPPDATA%\ClaudeOfficialZhHans\3.6556.2\<安装路径摘要>\
还原会保留安装前已存在且校验匹配的官方中文 JSON。

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
