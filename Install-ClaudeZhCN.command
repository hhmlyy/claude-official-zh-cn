#!/bin/bash
# Claude 3.6556.2: register official zh-Hans catalogs in the native language menu.
set -euo pipefail

PACKAGE_DIR="$(cd -- "$(/usr/bin/dirname -- "$0")" && pwd)"
CATALOG_DIR="$PACKAGE_DIR/catalogs"
APP_PATH="/Applications/Claude.app"
BACKUP_DIR="$HOME/Library/Application Support/ClaudeOfficialZhHans/3.6556.2"
ACTION="install"
RESTART="yes"
STAGED=""
WORK_DIR=""
REG_ORIGINAL="83537e599f2f6720c2a0a245162e44a5c7431e22872a32ed16ea716e65ded08a"
REG_REGISTERED="f556db8f04ce27ffbe7b7113ff6fe7169274a9e8a4f083ca202dded325ecf3d4"
MAIN_SHA="dc0f674b04d17055671f06a5645294352d98780128e944706b5411d53cae038b"
DYNAMIC_SHA="8121dfdeb01237ec4b46a9d252d777da2ee2c5edcf35b885a76fc82810c09fb4"

fail() { printf '错误：%s\n' "$*" >&2; exit 1; }
sha256() { /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'; }
verify() {
  [[ -f "$1" && ! -L "$1" ]] || fail "不是普通文件：$1"
  [[ "$(sha256 "$1")" == "$2" ]] || fail "文件校验不符，已停止：$1"
}
verify_optional() {
  if [[ -e "$1" || -L "$1" ]]; then verify "$1" "$2"; fi
}
cleanup() {
  if [[ -n "$STAGED" && -f "$STAGED" ]]; then /bin/unlink "$STAGED"; fi
  if [[ -n "$WORK_DIR" && -d "$WORK_DIR" && ! -L "$WORK_DIR" ]]; then /bin/rm -r "$WORK_DIR"; fi
}
put() {
  local source="$1" target="$2" expected="$3"
  STAGED=$(/usr/bin/mktemp "$(/usr/bin/dirname "$target")/.claude-zh-Hans.XXXXXX")
  /bin/cp "$source" "$STAGED"
  /bin/chmod 644 "$STAGED"
  verify "$STAGED" "$expected"
  /bin/mv "$STAGED" "$target"
  STAGED=""
  verify "$target" "$expected"
}
catalog() {
  local name="$1" installed="$2" expected="$3" url="$4"
  if [[ -e "$CATALOG_DIR/$name" || -L "$CATALOG_DIR/$name" ]]; then
    verify "$CATALOG_DIR/$name" "$expected"
    /bin/cp "$CATALOG_DIR/$name" "$WORK_DIR/$name"
  elif [[ -f "$installed" ]]; then
    verify "$installed" "$expected"
    /bin/cp "$installed" "$WORK_DIR/$name"
  else
    printf '下载官方资源：%s\n' "$url"
    /usr/bin/curl --fail --location --connect-timeout 15 --max-time 60 \
      --proto '=https' --proto-redir '=https' --output "$WORK_DIR/$name" "$url" || \
      fail '官方资源下载失败；请按 README 从浏览器保存两份官方 JSON 到 catalogs 后重试。应用尚未修改。'
  fi
  verify "$WORK_DIR/$name" "$expected"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) ACTION="check"; shift ;;
    --restore) ACTION="restore"; shift ;;
    --no-restart) RESTART="no"; shift ;;
    --app) [[ $# -ge 2 ]] || fail '--app 缺少路径。'; APP_PATH="$2"; shift 2 ;;
    --backup-dir) [[ $# -ge 2 ]] || fail '--backup-dir 缺少路径。'; BACKUP_DIR="$2"; shift 2 ;;
    --catalog-dir) [[ $# -ge 2 ]] || fail '--catalog-dir 缺少路径。'; CATALOG_DIR="$2"; shift 2 ;;
    -h|--help)
      printf '%s\n' '注册 Claude 官方中文：重新打开后在 Language → 中文（简体）中选择。' \
        '--check：只检查，不下载、不修改。  --restore：撤销注册，不需要下载。' \
        '--no-restart：自行退出和重启 Claude。  --app 路径：指定 Claude.app。' \
        '--catalog-dir 路径：指定两份官方 JSON 所在目录。' \
        '--backup-dir 路径：指定原文件备份目录；兼容此前 Mac 脚本的备份。' \
        '仅适配 3.6556.2。资源修改会影响原签名校验；脚本不重签名。'
      exit 0 ;;
    *) fail "未知参数：$1" ;;
  esac
done

[[ "$(/usr/bin/uname -s)" == "Darwin" ]] || fail '仅适用于 macOS。'
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP_PATH/Contents/Info.plist")
[[ "$VERSION" == "3.6556.2" ]] || fail "只适配 3.6556.2，当前为 $VERSION，未修改。"
RESOURCES="$APP_PATH/Contents/Resources/ion-dist"
REGISTRY="$RESOURCES/assets/v1/shared-52-uHFNjl7C.js"
MAIN="$RESOURCES/i18n/zh-Hans.json"
DYNAMIC="$RESOURCES/i18n/dynamic/zh-Hans.json"
BACKUP="$BACKUP_DIR/shared-52.original.js"
[[ -f "$REGISTRY" && ! -L "$REGISTRY" ]] || fail '找不到语言注册文件。'
CURRENT=$(sha256 "$REGISTRY")
[[ "$CURRENT" == "$REG_ORIGINAL" || "$CURRENT" == "$REG_REGISTERED" ]] || fail '语言注册文件不是已核验版本。'
verify "$RESOURCES/assets/v1/shared-50-DopKwmK0.js" '371cdd50d64068beb78178a0eb988ace10eb077f79e72f7b915688c2d68e418d'
verify "$RESOURCES/i18n/en-US.json" '58c827a85e1ab35f8cd8934db9521842e169505432b407c3eaf129c322e7aa40'
verify "$RESOURCES/i18n/dynamic/en-US.json" '79e1211bbad7a95915bd982f97e36757e8c54cabe00130a6c673e6796d85cee9'
verify_optional "$MAIN" "$MAIN_SHA"
verify_optional "$DYNAMIC" "$DYNAMIC_SHA"

if [[ "$ACTION" == "check" ]]; then
  if [[ "$CURRENT" == "$REG_REGISTERED" && -f "$MAIN" && -f "$DYNAMIC" ]]; then
    printf '核验通过：官方中文已完整注册到原有语言菜单，英文文件保持原版。\n'
  else
    printf '核验通过：当前可以安装中文语言注册。\n'
  fi
  exit 0
fi
if [[ "$ACTION" == "install" && "$CURRENT" == "$REG_REGISTERED" && -f "$MAIN" && -f "$DYNAMIC" ]]; then
  printf '官方中文已安装，无需重复修改。\n'
  exit 0
fi

if [[ "$ACTION" == "restore" ]]; then
  if [[ "$CURRENT" == "$REG_REGISTERED" ]]; then verify "$BACKUP" "$REG_ORIGINAL"; fi
else
  if [[ "$CURRENT" == "$REG_ORIGINAL" ]]; then ORIGINAL="$REGISTRY"; else ORIGINAL="$BACKUP"; fi
  verify "$ORIGINAL" "$REG_ORIGINAL"
  WORK_DIR=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/claude-zh-Hans.XXXXXX")
  catalog 'zh-Hans.official.json' "$MAIN" "$MAIN_SHA" 'https://claude.ai/i18n/zh-Hans.json?v=dc0f674b04d1'
  catalog 'zh-Hans.dynamic.official.json' "$DYNAMIC" "$DYNAMIC_SHA" 'https://claude.ai/i18n/dynamic/zh-Hans.json?v=8121dfdeb012'
  {
    /bin/cat "$ORIGINAL"
    printf '\n%s\n%s\n%s\n' \
      '/* ClaudeOfficialZhHans: register the official Chinese catalogs. */' \
      'if (!ay.includes("zh-Hans")) ay.push("zh-Hans");' \
      'if (!by.includes("zh-Hans")) by.push("zh-Hans");'
  } > "$WORK_DIR/registered.js"
  verify "$WORK_DIR/registered.js" "$REG_REGISTERED"
  [[ ! -L "$BACKUP_DIR" ]] || fail '备份目录不能是符号链接。'
  /bin/mkdir -p "$BACKUP_DIR"
  if [[ -e "$BACKUP" || -L "$BACKUP" ]]; then verify "$BACKUP" "$REG_ORIGINAL";
  else /bin/cp -p "$ORIGINAL" "$BACKUP"; verify "$BACKUP" "$REG_ORIGINAL"; fi
fi
[[ -w "$REGISTRY" && -w "$RESOURCES/assets/v1" && -w "$RESOURCES/i18n" && -w "$RESOURCES/i18n/dynamic" ]] || \
  fail '没有应用写入权限，未修改；请确认 Claude.app 属于当前用户。'

if [[ "$RESTART" == "yes" ]] && /usr/bin/pgrep -x Claude >/dev/null; then
  /usr/bin/osascript -e 'tell application id "com.anthropic.claudefordesktop" to quit' >/dev/null
  for ((attempt=0; attempt<30; attempt++)); do
    if ! /usr/bin/pgrep -x Claude >/dev/null; then break; fi
    /bin/sleep 1
  done
  if /usr/bin/pgrep -x Claude >/dev/null; then fail 'Claude 仍在运行，未强制结束；请退出后重试。'; fi
fi
[[ "$(sha256 "$REGISTRY")" == "$CURRENT" ]] || fail '文件在检查后发生变化，未覆盖。'
verify_optional "$MAIN" "$MAIN_SHA"
verify_optional "$DYNAMIC" "$DYNAMIC_SHA"
if [[ "$ACTION" == "restore" ]]; then
  if [[ "$CURRENT" != "$REG_ORIGINAL" ]]; then put "$BACKUP" "$REGISTRY" "$REG_ORIGINAL"; fi
  if [[ -f "$MAIN" ]]; then /bin/unlink "$MAIN"; fi
  if [[ -f "$DYNAMIC" ]]; then /bin/unlink "$DYNAMIC"; fi
  printf '已撤销中文注册、恢复原始注册文件并移除两份官方中文 JSON。\n'
else
  put "$WORK_DIR/zh-Hans.official.json" "$MAIN" "$MAIN_SHA"
  put "$WORK_DIR/zh-Hans.dynamic.official.json" "$DYNAMIC" "$DYNAMIC_SHA"
  if [[ "$CURRENT" != "$REG_REGISTERED" ]]; then put "$WORK_DIR/registered.js" "$REGISTRY" "$REG_REGISTERED"; fi
  printf '已注册官方中文。请在账号菜单 → Language → 中文（简体）切换。\n'
fi
if [[ "$RESTART" == "yes" ]]; then /usr/bin/open -a "$APP_PATH"; fi
