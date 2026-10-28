#!/usr/bin/env python3
"""Claude 的中文与原生工具安装事务。"""
import argparse
import copy
import fcntl
import hashlib
import json
import mmap
import os
import pathlib
import platform
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ASAR = "Contents/Resources/app.asar"
ION_ASAR = "Contents/Resources/ion-dist.asar"
NODE = "Contents/Resources/app.asar.unpacked/node_modules/@ant/claude-swift/build/Release/computer_use.node"
FRAMEWORK = "Contents/Frameworks/Electron Framework.framework/Versions/A/Electron Framework"
REGISTRY = "Contents/Resources/ion-dist/assets/v1/shared-52-uHFNjl7C.js"
GATES = '1291166712:{rule:"forced",value:{enabled:!0}},1346958739:{rule:"forced",value:{major:26,minor:5}},'
TRACKED = (ASAR, "Contents/Info.plist", "Contents/MacOS/Claude", NODE, REGISTRY, FRAMEWORK,
           "Contents/Frameworks/Claude Helper.app/Contents/MacOS/Claude Helper",
           "Contents/Frameworks/Claude Helper (GPU).app/Contents/MacOS/Claude Helper (GPU)",
           "Contents/Frameworks/Claude Helper (Renderer).app/Contents/MacOS/Claude Helper (Renderer)",
           "Contents/Frameworks/Claude Helper (Plugin).app/Contents/MacOS/Claude Helper (Plugin)",
           "Contents/Resources/ion-dist/i18n/en-US.json",
           "Contents/Resources/ion-dist/i18n/dynamic/en-US.json",
           "Contents/Resources/ion-dist/i18n/zh-Hans.json",
           "Contents/Resources/ion-dist/i18n/dynamic/zh-Hans.json",
           "Contents/_CodeSignature/CodeResources")
ROOT = pathlib.Path(__file__).resolve().parent
MANAGED_POLICY = pathlib.Path("/Library/Managed Preferences/com.anthropic.claudefordesktop.plist")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(*args):
    result = subprocess.run([str(x) for x in args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, "命令失败：%s\n%s" %
            (args[0], result.stderr.decode(errors="replace")[-1500:]))
    return result


def read(path):
    require(path.is_file() and not path.is_symlink(), "文件缺失或是符号链接：" + str(path))
    return path.read_bytes()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    require(path.is_file() and not path.is_symlink(), "文件缺失或是符号链接：" + str(path))
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def snapshot(app, names=None):
    if names is None:
        names = set(TRACKED) | {ION_ASAR}
        assets = app / "Contents/Resources/ion-dist/assets/v1"
        names.update(str(path.relative_to(app)) for path in assets.glob("shared-*.js"))
    return {name: file_digest(app / name) if (app / name).exists() else None for name in names}


def matches_snapshot(app, expected):
    return snapshot(app, expected) == expected


def atomic(path, data, mode=0o600):
    require(not path.is_symlink(), "目标不能是符号链接：" + str(path))
    fd, name = tempfile.mkstemp(prefix=".claude-native-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save(path, value):
    atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def bundle_version(app):
    info = plistlib.loads(read(app / "Contents/Info.plist"))
    require(info.get("CFBundleIdentifier") == "com.anthropic.claudefordesktop", "应用标识不符。")
    return info


def host_architecture():
    result = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.optional.arm64"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return "arm64" if result.returncode == 0 and result.stdout.strip() == b"1" else platform.machine()


def environment():
    architecture = host_architecture()
    require(sys.platform == "darwin" and architecture in ("x86_64", "arm64"),
            "原生补丁仅适用于 Intel 或 Apple Silicon 的 macOS。")
    major = platform.mac_ver()[0].split(".", 1)[0]
    if major.isdecimal() and int(major) < 14:
        print("提示：此 Claude 构建的原生电脑控制需要 macOS 14 或更新版本；"
              "中文与内置浏览器仍取决于 Claude 和系统支持。", file=sys.stderr)
    return architecture


def source(app, native=True):
    bundle_version(app)
    require(not app.is_symlink(), "应用不能是符号链接。")
    raw = read(app / ASAR)
    if native:
        main_path(raw)
    executable = app / "Contents/MacOS/Claude"
    node = app / NODE
    for path in ((executable, node) if native else (executable,)):
        read(path)
        architectures = run("/usr/bin/lipo", "-archs", path).stdout.decode().split()
        require(host_architecture() in architectures, "Claude 应用与这台 Mac 的处理器不匹配。")
    return {"asar": digest(raw), "node": digest(read(node)) if native else None,
            "exec": digest(read(executable)), "plist": digest(read(app / "Contents/Info.plist"))}


def verify_signature(app, official=False):
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
    if official:
        result = run("/usr/bin/codesign", "-dvv", app)
        require(b"TeamIdentifier=Q6L2SF6YDW" in result.stderr, "备份不是官方签名的应用。")


def integrity_digest(info):
    entries = info.get("ElectronAsarIntegrity")
    require(isinstance(entries, dict) and entries, "缺少 ASAR 完整性信息。")
    result = hashlib.sha256()
    for name, entry in sorted(entries.items()):
        require(isinstance(name, str) and name.isascii() and isinstance(entry, dict) and
                entry.get("algorithm") == "SHA256" and isinstance(entry.get("hash"), str) and
                re.fullmatch(r"[0-9a-f]{64}", entry["hash"]), "ASAR 完整性信息格式不支持。")
        result.update((name + entry["algorithm"] + entry["hash"]).encode("ascii"))
    return result.digest()


def update_framework_digest(app, original_info, updated_info):
    path = app / FRAMEWORK
    require(path.is_file() and not path.is_symlink(), "Electron 框架文件缺失或是符号链接。")
    sentinel = b"AGbevlPCksUGKNL8TSn7wGmJEuJsXb2A"
    with path.open("r+b") as handle, mmap.mmap(handle.fileno(), 0) as data:
        positions = []
        offset = data.find(sentinel)
        while offset >= 0:
            positions.append(offset + len(sentinel))
            offset = data.find(sentinel, offset + len(sentinel))
        if not positions:
            return False
        architectures = run("/usr/bin/lipo", "-archs", path).stdout.decode().split()
        require(len(positions) == len(architectures) and all(pos + 34 <= len(data) for pos in positions),
                "Electron 完整性摘要的位置异常。")
        slots = [data[pos:pos + 34] for pos in positions]
        if all(slot[0] == 0 for slot in slots):
            return False
        original = b"\x01\x01" + integrity_digest(original_info)
        require(all(slot == original for slot in slots), "Electron 完整性摘要与原始应用不一致。")
        replacement = b"\x01\x01" + integrity_digest(updated_info)
        for pos in positions:
            data[pos:pos + 34] = replacement
        data.flush()
        os.fsync(handle.fileno())
    return True


def resign_helpers(app, temp):
    frameworks = app / "Contents/Frameworks"
    framework = frameworks / "Electron Framework.framework"
    run("/usr/bin/codesign", "--force", "--sign", "-",
        "--preserve-metadata=entitlements,flags,runtime", framework)
    helpers = sorted(frameworks.glob("Claude Helper*.app"))
    require(helpers, "未找到 Electron 辅助进程。")
    for index, helper in enumerate(helpers):
        require(helper.is_dir() and not helper.is_symlink(), "辅助进程路径异常。")
        entitlements = plistlib.loads(run("/usr/bin/codesign", "-d", "--entitlements", ":-", helper).stdout)
        for key in ("com.apple.application-identifier", "com.apple.developer.team-identifier", "keychain-access-groups"):
            entitlements.pop(key, None)
        entitlements["com.apple.security.cs.disable-library-validation"] = True
        path = pathlib.Path(temp) / ("helper-entitlements-%d.plist" % index)
        atomic(path, plistlib.dumps(entitlements))
        run("/usr/bin/codesign", "--force", "--sign", "-", "--options", "runtime",
            "--entitlements", path, helper)


def unpack(raw):
    size = struct.unpack_from("<I", raw, 4)[0]
    length = struct.unpack_from("<I", raw, 12)[0]
    require(16 + length <= 8 + size <= len(raw), "ASAR 索引异常。")
    return json.loads(raw[16:16 + length]), 8 + size


def nodes(header, prefix=""):
    for name, node in header.get("files", {}).items():
        path = prefix + "/" + name if prefix else name
        if "files" in node:
            yield from nodes(node, path)
        elif "offset" in node and not node.get("unpacked"):
            yield path, node


def asar_file(raw, path):
    header, base = unpack(raw)
    node = dict(nodes(header))[path]
    start = base + int(node["offset"])
    result = raw[start:start + node["size"]]
    require(len(result) == node["size"], "ASAR 数据段越界。")
    return result


def main_path(raw):
    header, base = unpack(raw)
    matches = []
    anchor = re.compile(rb'var [A-Za-z_$][\w$]*=\{(?=(?:' + re.escape(GATES.encode()) +
                        rb')?17519066:\{rule:"forcedFor",group:"builtinBrowser",value:!0\})')
    for path, node in nodes(header):
        if not path.startswith(".vite/build/") or not path.endswith(".js"):
            continue
        data = raw[base + int(node["offset"]):base + int(node["offset"]) + node["size"]]
        found = list(anchor.finditer(data))
        if found and b'"1291166712"' in data and b'"1346958739"' in data:
            matches.extend((path, match.end()) for match in found)
    require(len(matches) == 1, "无法唯一识别原生功能表，未修改。")
    return matches[0]


def main_bytes(raw):
    return asar_file(raw, main_path(raw)[0])


def patched_asar(raw):
    """只在功能表插入两项；其余文件和官方操作检查逐字节保留。"""
    path, table_start = main_path(raw)
    original = asar_file(raw, path)
    text = original.decode()
    # 锚点此前使用字节定位；只接受 ASCII 前缀，避免 Unicode 字符偏移。
    table_start = len(original[:table_start].decode())
    # 先定位整张对象表，拒绝重复键；不能靠后插入覆盖官方已有定义。
    depth, end = 1, table_start
    while depth:
        require(end < len(text), "功能表未闭合。")
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    table = text[table_start:end]
    require(not re.search(r"(?:1291166712|1346958739):", table), "目标开关已经有定义。")
    replacement = (text[:table_start] + GATES + text[table_start:]).encode()
    result, header_hash = replace_asar_files(raw, {path: replacement})
    require(main_bytes(result).replace(GATES.encode(), b"", 1) == original,
            "补丁包含预期之外的主进程改动。")
    return result, header_hash


def replace_asar_files(raw, replacements, additions=None):
    additions = additions or {}
    header, base = unpack(raw)
    header = copy.deepcopy(header)
    segments = {}
    for path, node in nodes(header):
        segments.setdefault((int(node["offset"]), node["size"]), []).append((path, node))
    require(set(replacements).issubset(dict(nodes(header))), "ASAR 文件缺失。")
    payload = bytearray()
    end = 0
    for (offset, size), entries in sorted(segments.items()):
        require(offset == end, "ASAR 数据段不连续或重叠。")
        changed = [path for path, _ in entries if path in replacements]
        require(not changed or len(entries) == 1, "待修改文件意外共享 ASAR 数据段。")
        block = replacements[changed[0]] if changed else raw[base + offset:base + offset + size]
        require(changed or len(block) == size, "ASAR 数据段越界。")
        for path, node in entries:
            node["offset"], node["size"] = str(len(payload)), len(block)
            if changed:
                update_integrity(node, block)
        payload.extend(block)
        end = offset + size
    require(base + end == len(raw), "ASAR 存在未识别的数据。")
    for path, block in additions.items():
        parts = path.split("/")
        directory = header
        for part in parts[:-1]:
            directory = directory["files"][part]
        require(parts[-1] not in directory["files"], "ASAR 中文资源已存在。")
        node = {"offset": str(len(payload)), "size": len(block)}
        update_integrity(node, block)
        directory["files"][parts[-1]] = node
        payload.extend(block)
    encoded = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode()
    padded = ((len(encoded) + 7) // 4) * 4
    result = (struct.pack("<IIII", 4, padded + 4, padded, len(encoded)) + encoded +
              b"\0" * (padded - 4 - len(encoded)) + payload)
    return result, digest(encoded)


def update_integrity(node, block):
    block_size = node.get("integrity", {}).get("blockSize", 4194304)
    require(isinstance(block_size, int) and block_size > 0, "ASAR 完整性块大小无效。")
    node["integrity"] = {"algorithm": "SHA256", "hash": digest(block), "blockSize": block_size,
                         "blocks": [digest(block[i:i + block_size])
                                    for i in range(0, len(block), block_size)]}


CATALOGS = (
    ("zh-Hans.official.json", "i18n/zh-Hans.json",
     "dc0f674b04d17055671f06a5645294352d98780128e944706b5411d53cae038b",
     "https://claude.ai/i18n/zh-Hans.json?v=dc0f674b04d1"),
    ("zh-Hans.dynamic.official.json", "i18n/dynamic/zh-Hans.json",
     "8121dfdeb01237ec4b46a9d252d777da2ee2c5edcf35b885a76fc82810c09fb4",
     "https://claude.ai/i18n/dynamic/zh-Hans.json?v=8121dfdeb012"),
)
LOCALES = rb'(?P<name>[A-Za-z_$][\w$]*)=\[(?P<list>"en-US"(?:,"[A-Za-z0-9-]+")+)\];function [A-Za-z_$][\w$]*\('
FIRST_LIST = re.compile(LOCALES + rb'[A-Za-z_$][\w$]*\)\{return (?P=name)\.includes\(')
SECOND_LIST = re.compile(LOCALES + rb'[A-Za-z_$][\w$]*,[A-Za-z_$][\w$]*=(?P=name)\)\{let [A-Za-z_$][\w$]*=new Map;')


def registered_bundle(original):
    first, second = list(FIRST_LIST.finditer(original)), list(SECOND_LIST.finditer(original))
    require(len(first) == len(second) == 1, "无法唯一识别语言列表，未修改。")
    require(first[0]["list"] == second[0]["list"] and b'"ja-JP"' in first[0]["list"] and
            b'"zh-Hans"' not in first[0]["list"] and b"/i18n/dynamic/" in original and
            b"ClaudeOfficialZhHans" not in original, "语言注册结构不匹配或已经修改。")
    names = (first[0]["name"].decode("ascii"), second[0]["name"].decode("ascii"))
    require(names[0] != names[1], "语言列表不能共用变量。")
    tail = ("\n/* ClaudeOfficialZhHans: register the official Chinese catalogs. */\n" +
            "".join('if (!%s.includes("zh-Hans")) %s.push("zh-Hans");\n' % (name, name)
                    for name in names))
    return original + tail.encode("ascii")


def language_layout(app):
    resources = app / "Contents/Resources"
    archive, directory = resources / "ion-dist.asar", resources / "ion-dist"
    require(archive.exists() != directory.exists(), "无法唯一识别语言资源目录或 ASAR。")
    if archive.exists():
        raw = read(archive)
        header, _ = unpack(raw)
        paths = dict(nodes(header))
        candidates = [path for path in paths if path.startswith("assets/v1/shared-") and path.endswith(".js")]
        get = lambda path: asar_file(raw, path)
    else:
        require(not directory.is_symlink(), "语言资源目录不能是符号链接。")
        raw = None
        paths = {str(path.relative_to(directory)): path for path in (directory / "assets/v1").glob("shared-*.js")}
        candidates = list(paths)
        get = lambda path: read(directory / path)
    matches = []
    for path in candidates:
        data = get(path)
        if FIRST_LIST.search(data) and SECOND_LIST.search(data):
            matches.append((path, registered_bundle(data)))
    require(len(matches) == 1, "无法唯一识别语言注册文件，未修改。")
    for path in ("i18n/en-US.json", "i18n/dynamic/en-US.json"):
        require(isinstance(json.loads(get(path)), dict), "英文语言资源格式异常。")
    for _, path, expected, _ in CATALOGS:
        exists = path in paths if raw is not None else (directory / path).exists()
        if exists:
            require(digest(get(path)) == expected, "已有中文语言文件与官方资源不一致。")
    return raw, directory, matches[0]


def install_language(args, app, info):
    raw, directory, (registry, registered) = language_layout(app)
    catalogs = {}
    for name, target, expected, url in CATALOGS:
        local = args.catalog_dir / name
        data = read(local) if local.exists() or local.is_symlink() else run(
            "/usr/bin/curl", "--fail", "--location", "--connect-timeout", "15", "--max-time", "60",
            "--proto", "=https", "--proto-redir", "=https", url).stdout
        require(digest(data) == expected, "官方中文语言文件校验不符：" + name)
        catalogs[target] = data
    if raw is None:
        for target, data in catalogs.items():
            atomic(directory / target, data, 0o644)
        atomic(directory / registry, registered, 0o644)
    else:
        paths = dict(nodes(unpack(raw)[0]))
        additions = {path: data for path, data in catalogs.items() if path not in paths}
        data, header_hash = replace_asar_files(raw, {registry: registered}, additions)
        atomic(app / ION_ASAR, data, 0o644)
        require("Resources/ion-dist.asar" in info.get("ElectronAsarIntegrity", {}),
                "应用未声明语言 ASAR 完整性摘要。")
        info["ElectronAsarIntegrity"]["Resources/ion-dist.asar"] = {"algorithm": "SHA256", "hash": header_hash}


def config(args):
    directory = args.config_dir
    require(directory.resolve() == directory.absolute(), "第三方配置目录不能经过符号链接。")
    meta = read(directory / "_meta.json")
    identifier = json.loads(meta)["appliedId"]
    require(isinstance(identifier, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier),
            "第三方配置标识非法。")
    path = directory / (identifier + ".json")
    raw = read(path)
    value = json.loads(raw)
    require(value.get("inferenceProvider") == "gateway", "当前不是 Magpie 使用的 gateway 部署。")
    require(not value.get("bootstrapUrl") and not value.get("bootstrapEnabled"), "配置由服务器管理，停止本地修改。")
    managed = MANAGED_POLICY
    user_managed = managed.parent / pathlib.Path.home().name / managed.name
    require(not managed.exists() and not user_managed.exists(), "存在组织管理策略，停止本地修改。")
    return path, value, raw, meta


def browser(args, restore=None):
    path, value, raw, meta = config(args)
    before = {"id": path.stem, "present": "builtinBrowserEnabled" in value,
              "value": value.get("builtinBrowserEnabled")}
    if restore is None:
        if value.get("builtinBrowserEnabled") is True:
            return before
        value["builtinBrowserEnabled"] = True
    else:
        require(path.stem == restore["id"], "Magpie 已切换配置；不覆盖新配置。")
        if before == restore:
            return before
        require(value.get("builtinBrowserEnabled") is True, "浏览器开关已被其他操作修改。")
        if restore["present"]:
            value["builtinBrowserEnabled"] = restore["value"]
        else:
            value.pop("builtinBrowserEnabled", None)
    require(read(path) == raw and read(args.config_dir / "_meta.json") == meta, "配置发生并发变化。")
    atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
    return before


def processes(app):
    prefix = str(app / "Contents") + "/"
    return any(line.startswith(prefix) for line in
               run("/bin/ps", "-axo", "comm=").stdout.decode().splitlines())


def load_state(args):
    path = args.state_dir / "state.json"
    if not path.exists():
        return None
    state = json.loads(read(path))
    require(state.get("schema") == 1 and state.get("app") == str(args.app), "安装记录属于其他应用。")
    return state


def persist(args, state):
    save(args.state_dir / "state.json", state)


def prepared(args, state):
    path = args.state_dir / "Claude.prepared.app"
    require(matches_snapshot(path, state["prepared"]), "准备副本已改变，请重新准备。")
    verify_signature(path)
    return path


def prepare(args):
    language_only = getattr(args, "language_only", False)
    state = load_state(args)
    if state and state["phase"] == "installed":
        require(matches_snapshot(args.app, state["installed"]), "已安装文件被其他操作修改，停止。")
        print("合并补丁已安装；无需重新构建。")
        return state
    require(not state or state["phase"] in ("prepared", "restored"), "上次事务中断，需先核对备份。")
    before = snapshot(args.app)
    legacy_installed = before[REGISTRY] == "f556db8f04ce27ffbe7b7113ff6fe7169274a9e8a4f083ca202dded325ecf3d4"
    build = source(args.app, native=False) if language_only else source(args.app)
    if not language_only:
        config(args)
    backup = args.state_dir / "Claude.original.app"
    if not backup.exists():
        with tempfile.TemporaryDirectory(prefix=".original-", dir=str(args.state_dir)) as temp:
            candidate = pathlib.Path(temp) / "Claude.app"
            run("/usr/bin/ditto", args.app, candidate)
            if legacy_installed:
                run("/bin/bash", ROOT / "Install-ClaudeZhCN.command", "--legacy-restore", "--restore", "--no-restart",
                    "--app", candidate, "--backup-dir", args.backup_dir)
            verify_signature(candidate, official=True)
            require(matches_snapshot(args.app, before), "Claude 在准备期间更新了文件。")
            candidate.rename(backup)
    backup_build = source(backup, native=False) if language_only else source(backup)
    require(backup_build == build, "现有官方备份属于不同构建，停止以免替换当前版本。")
    expected = dict(before)
    if legacy_installed:
        expected[REGISTRY] = "83537e599f2f6720c2a0a245162e44a5c7431e22872a32ed16ea716e65ded08a"
        expected["Contents/Resources/ion-dist/i18n/zh-Hans.json"] = None
        expected["Contents/Resources/ion-dist/i18n/dynamic/zh-Hans.json"] = None
    require(matches_snapshot(backup, expected), "备份与当前语言资源不一致，停止以免替换其他构建。")
    verify_signature(backup, official=True)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=str(args.state_dir)) as temp:
        candidate = pathlib.Path(temp) / "Claude.app"
        run("/usr/bin/ditto", backup, candidate)
        info = bundle_version(candidate)
        original_info = copy.deepcopy(info)
        install_language(args, candidate, info)
        if not language_only:
            data, header_hash = patched_asar(read(candidate / ASAR))
            atomic(candidate / ASAR, data, 0o644)
            require("Resources/app.asar" in info.get("ElectronAsarIntegrity", {}), "应用未声明主 ASAR 完整性摘要。")
            info["ElectronAsarIntegrity"]["Resources/app.asar"] = {"algorithm": "SHA256", "hash": header_hash}
        atomic(candidate / "Contents/Info.plist", plistlib.dumps(info, sort_keys=False), 0o644)
        if update_framework_digest(candidate, original_info, info):
            resign_helpers(candidate, temp)
        entitlements = plistlib.loads(run("/usr/bin/codesign", "-d", "--entitlements", ":-", candidate).stdout)
        # 临时签名不能冒用官方团队或钥匙串访问组，否则 AMFI 会拒绝启动。
        for key in ("com.apple.application-identifier", "com.apple.developer.team-identifier", "keychain-access-groups"):
            entitlements.pop(key, None)
        # 保留 hardened runtime，同时允许加载不同签名的 Electron 框架。
        entitlements["com.apple.security.cs.disable-library-validation"] = True
        entitlements_path = pathlib.Path(temp) / "entitlements.plist"
        atomic(entitlements_path, plistlib.dumps(entitlements))
        run("/usr/bin/codesign", "--force", "--sign", "-", "--options", "runtime",
            "--entitlements", entitlements_path, candidate)
        verify_signature(candidate)
        if not language_only:
            require(digest(read(candidate / NODE)) == build["node"], "原生模块被意外修改。")
        require(matches_snapshot(args.app, before), "Claude 在准备期间更新了文件。")
        target = args.state_dir / "Claude.prepared.app"
        if target.exists():
            shutil.rmtree(target)
        candidate.rename(target)
    state = {"schema": 1, "app": str(args.app), "phase": "prepared", "before": before, "language_only": language_only,
             "original": snapshot(backup), "prepared": snapshot(target)}
    persist(args, state)
    print("已在副本准备：" + ("官方中文。" if language_only else "官方中文＋原生电脑控制开关＋内置浏览器。") + "正在运行的 Claude 未修改。")
    return state


def install(args):
    language_only = getattr(args, "language_only", False)
    require(not processes(args.app), "Claude 仍在运行。请等任务完成并正常退出后重试；可以先使用 --prepare。")
    state = load_state(args)
    if not state or state["phase"] == "restored":
        state = prepare(args)
    if state["phase"] == "installed":
        require(matches_snapshot(args.app, state["installed"]), "已安装文件被其他操作修改。")
        if not language_only:
            browser(args)
        print("补丁已安装。")
        return
    require(state["phase"] == "prepared" and matches_snapshot(args.app, state["before"]),
            "当前 Claude 与准备时不一致，请重新准备。")
    backup = args.state_dir / "Claude.original.app"
    require(matches_snapshot(backup, state["original"]), "原始备份缺失或被修改，停止安装。")
    verify_signature(backup, official=True)
    candidate = prepared(args, state)
    flag = None
    if not language_only:
        path, value, _, _ = config(args)
        flag = {"id": path.stem, "present": "builtinBrowserEnabled" in value,
                "value": value.get("builtinBrowserEnabled")}
    previous = args.state_dir / "Claude.previous.app"
    require(not previous.exists(), "存在未完成的安装，请先核对 Claude.previous.app。")
    state.update(phase="installing", browser=flag)
    persist(args, state)
    moved = False
    try:
        require(not processes(args.app), "Claude 已重新打开，停止安装。")
        args.app.rename(previous)
        moved = True
        candidate.rename(args.app)
        verify_signature(args.app)
        if not language_only:
            browser(args)
        state.update(phase="installed", installed=snapshot(args.app))
        persist(args, state)
    except BaseException:
        if moved:
            if args.app.exists():
                args.app.rename(candidate)
            previous.rename(args.app)
        if not language_only:
            browser(args, flag)
        state["phase"] = "prepared"
        persist(args, state)
        raise
    shutil.rmtree(previous)
    print("已安装官方中文。" if language_only else
          "已安装：官方中文＋原生电脑控制开关＋官方内置浏览器。首次使用请在 Claude 设置中启用电脑控制并核对系统权限。")
    if not args.no_restart:
        run("/usr/bin/open", "-a", args.app)


def restore(args):
    language_only = getattr(args, "language_only", False)
    state = load_state(args)
    require(state is not None, "没有本工具的原生补丁记录。")
    if state["phase"] in ("prepared", "restored"):
        print("尚未应用原生补丁，无需恢复应用。")
        return
    require(state["phase"] == "installed", "上次事务中断，需先核对原应用与备份。")
    require(not processes(args.app), "请先正常退出 Claude，再恢复。")
    require(matches_snapshot(args.app, state["installed"]), "应用已被其他操作修改，停止恢复。")
    backup = args.state_dir / "Claude.original.app"
    require(matches_snapshot(backup, state["original"]), "原始应用备份被修改。")
    verify_signature(backup, official=True)
    flag = state["browser"]
    restore_browser = not language_only and not (flag["present"] is True and flag["value"] is True)
    if restore_browser:
        path, current, _, _ = config(args)
        require(path.stem == flag["id"] and
                (current.get("builtinBrowserEnabled") is True or
                 ("builtinBrowserEnabled" in current, current.get("builtinBrowserEnabled")) ==
                 (flag["present"], flag["value"])), "浏览器配置已被其他操作修改。")
    previous = args.state_dir / "Claude.previous.app"
    require(not previous.exists(), "存在未完成的应用替换。")
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=str(args.state_dir)) as temp:
        candidate = pathlib.Path(temp) / "Claude.app"
        run("/usr/bin/ditto", backup, candidate)
        args.app.rename(previous)
        try:
            candidate.rename(args.app)
            verify_signature(args.app, official=True)
            if restore_browser:
                browser(args, flag)
            state["phase"] = "restored"
            persist(args, state)
        except BaseException:
            if args.app.exists():
                args.app.rename(candidate)
            previous.rename(args.app)
            raise
    shutil.rmtree(previous)
    print("已恢复原始官方应用，中文注册一并撤销。")
    if not args.no_restart:
        run("/usr/bin/open", "-a", args.app)


def check(args):
    language_only = getattr(args, "language_only", False)
    bundle_version(args.app)
    state = load_state(args)
    if not language_only:
        path, value, _, _ = config(args)
    if state and state["phase"] == "installed":
        require(matches_snapshot(args.app, state["installed"]), "已安装补丁的文件校验失败。")
        verify_signature(args.app)
        print("核验通过：中文补丁已安装。" if language_only else "核验通过：合并补丁已安装，电脑控制入口已恢复。")
    else:
        source(args.app, native=False) if language_only else source(args.app)
        verify_signature(args.app, official=True)
        language_layout(args.app)
        if state and state["phase"] == "prepared":
            prepared(args, state)
            print("核验通过：补丁副本已准备，尚未应用。")
        else:
            print("核验通过：当前构建可准备补丁。")
    if not language_only:
        print("当前 Magpie 配置的官方内置浏览器：" + ("开启" if value.get("builtinBrowserEnabled") is True else "关闭"))
        print("系统权限与模型实际操作能力须另行验证；本检查不代表已获辅助功能或屏幕录制权限。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "prepare", "install", "restore"))
    parser.add_argument("--app", type=pathlib.Path, default=pathlib.Path("/Applications/Claude.app"))
    parser.add_argument("--backup-dir", type=pathlib.Path)
    parser.add_argument("--catalog-dir", type=pathlib.Path, default=ROOT / "catalogs")
    parser.add_argument("--config-dir", type=pathlib.Path, default=pathlib.Path.home() / "Library/Application Support/Claude-3p/configLibrary")
    parser.add_argument("--no-restart", action="store_true")
    parser.add_argument("--language-only", action="store_true")
    args = parser.parse_args()
    args.app = args.app.absolute()
    if args.backup_dir is None:
        version = bundle_version(args.app).get("CFBundleShortVersionString", "")
        require(isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9._-]+", version), "应用版本信息无效。")
        args.backup_dir = pathlib.Path.home() / "Library/Application Support/ClaudeOfficialZhHans" / version
    args.backup_dir = args.backup_dir.absolute()
    args.state_dir = args.backup_dir / (("language-" if args.language_only else "native-") + environment())
    require(args.app.resolve() == args.app and args.backup_dir.resolve() == args.backup_dir,
            "应用或备份路径不能经过符号链接。")
    if args.action == "check":
        check(args)
        return
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(args.state_dir.resolve() == args.state_dir and
            not (args.state_dir / "transaction.lock").is_symlink(), "事务目录或锁文件不能是符号链接。")
    with (args.state_dir / "transaction.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {"prepare": prepare, "install": install, "restore": restore}[args.action](args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, struct.error) as error:
        print("错误：" + str(error), file=sys.stderr)
        sys.exit(1)
