#!/usr/bin/env python3
"""Claude 3.6556.2 的中文与原生工具安装事务。"""
import argparse
import copy
import fcntl
import hashlib
import json
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

VERSION = "3.6556.2"
ASAR = "Contents/Resources/app.asar"
MAIN = ".vite/build/index.chunk-jPKPzV-P.js"
NODE = "Contents/Resources/app.asar.unpacked/node_modules/@ant/claude-swift/build/Release/computer_use.node"
REGISTRY = "Contents/Resources/ion-dist/assets/v1/shared-52-uHFNjl7C.js"
SOURCE_HASH = "f7a038189ff6149b41135c3fbb55226f6e330cde3874abede239b9d594dc742f"
MAIN_HASH = "6e898798943b990e6eefa9209c61d977866b7898f681864f02c8cad3bb691ed5"
NODE_HASH = "c54403144c391d4fb3b0f88ff948056c994f66df56d3e14923063557e085e04a"
EXEC_HASH = "ac4e7ad46a19c6cd02e78fc4fdee21d1dbcc820fadd3b627a4631f236a99c0ca"
PLIST_HASH = "b370a819a9faab39826ff900ceb7d0d0ba081daafe93eed37cd3018e64060d31"
BUILDS = {
    SOURCE_HASH: {
        "architectures": ("x86_64",), "node": NODE_HASH, "exec": EXEC_HASH, "plist": PLIST_HASH,
    },
    "d1315bccfdb85cfcd79fcc34f194f3a5154d383bff1518fde95d39e821e3852d": {
        "architectures": ("x86_64", "arm64"),
        "node": "301ce0ba38ac3725d5b5833abfaae9c7e453d54fddd509850344f821f2931aa1",
        "exec": "6dc844c1b12bea0d46f3840a97dbab121aa64bad4710730eed46ef0cce6ac4b5",
        "plist": "00075ca3f823a0b7731e0591a25f512136ada6d5c208cad1a5dce562b392a276",
    },
    "b2dfbbb40325d978dcb7561ad12a6f9bc199f8f46b7d3d2897af74ce8965d68a": {
        "architectures": ("arm64",),
        "node": "35d05e0bb1192f8352b9b9c6dfd47cc4865a89498f4f1618a99370e5e052e3a3",
        "exec": "955991a288be2251ec08015c7eb33bbe77395e982e7c42b9428b012837725639",
        "plist": "695b59fbf4c4dc65590c94d920e24467d5b928e257261e15e63a833f3d7fb4e8",
    },
}
ANCHOR = "var Hon={"
GATES = '1291166712:{rule:"forced",value:{enabled:!0}},1346958739:{rule:"forced",value:{major:26,minor:5}},'
TRACKED = (ASAR, "Contents/Info.plist", "Contents/MacOS/Claude", NODE, REGISTRY,
           "Contents/Resources/ion-dist/i18n/zh-Hans.json",
           "Contents/Resources/ion-dist/i18n/dynamic/zh-Hans.json",
           "Contents/_CodeSignature/CodeResources")
ROOT = pathlib.Path(__file__).resolve().parent


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


def snapshot(app):
    return {name: digest(read(app / name)) if (app / name).exists() else None
            for name in TRACKED}


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
    require(info.get("CFBundleShortVersionString") == VERSION, "仅适配 Claude " + VERSION)
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


def source(app):
    bundle_version(app)
    require(not app.is_symlink(), "应用不能是符号链接。")
    build = BUILDS.get(digest(read(app / ASAR)))
    require(build is not None, "Claude ASAR 指纹不在已适配的构建中，停止修改。")
    require(host_architecture() in build["architectures"], "Claude 应用与这台 Mac 的处理器不匹配。")
    require(digest(read(app / NODE)) == build["node"], "原生电脑控制模块指纹不符。")
    require(digest(read(app / "Contents/MacOS/Claude")) == build["exec"] and
            digest(read(app / "Contents/Info.plist")) == build["plist"], "主程序或应用配置指纹不符。")
    return build


def verify_signature(app, official=False):
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
    if official:
        result = run("/usr/bin/codesign", "-dvv", app)
        require(b"TeamIdentifier=Q6L2SF6YDW" in result.stderr, "备份不是官方签名的应用。")


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


def main_bytes(raw):
    header, base = unpack(raw)
    node = dict(nodes(header))[MAIN]
    start = base + int(node["offset"])
    return raw[start:start + node["size"]]


def patched_asar(raw):
    """只在功能表插入两项；其余文件和官方操作检查逐字节保留。"""
    require(digest(raw) in BUILDS, "只接受已登记的官方原版 ASAR。")
    original = main_bytes(raw)
    require(digest(original) == MAIN_HASH, "主进程文件指纹不符。")
    text = original.decode()
    require(text.count(ANCHOR) == 1, "功能表锚点不唯一。")
    table_start = text.index(ANCHOR) + len(ANCHOR)
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
    header, base = unpack(raw)
    header = copy.deepcopy(header)
    segments = {}
    for path, node in nodes(header):
        segments.setdefault((int(node["offset"]), node["size"]), []).append((path, node))
    payload = bytearray()
    for (offset, size), entries in sorted(segments.items()):
        changed = any(path == MAIN for path, _ in entries)
        require(not changed or all(path == MAIN for path, _ in entries), "主文件意外共享 ASAR 数据段。")
        block = replacement if changed else raw[base + offset:base + offset + size]
        require(len(block) == (len(replacement) if changed else size), "ASAR 数据段越界。")
        for path, node in entries:
            node["offset"], node["size"] = str(len(payload)), len(block)
            if changed:
                block_size = node.get("integrity", {}).get("blockSize", 4194304)
                node["integrity"] = {"algorithm": "SHA256", "hash": digest(block),
                                     "blockSize": block_size,
                                     "blocks": [digest(block[i:i + block_size])
                                                for i in range(0, len(block), block_size)]}
        payload.extend(block)
    encoded = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode()
    padded = ((len(encoded) + 7) // 4) * 4
    result = (struct.pack("<IIII", 4, padded + 4, padded, len(encoded)) + encoded +
              b"\0" * (padded - 4 - len(encoded)) + payload)
    require(main_bytes(result).replace(GATES.encode(), b"", 1) == original,
            "补丁包含预期之外的主进程改动。")
    return result, digest(encoded)


def language(args, app, action):
    run("/bin/bash", ROOT / "Install-ClaudeZhCN.command", "--language-only", "--no-restart",
        "--app", app, "--backup-dir", args.backup_dir, "--catalog-dir", args.catalog_dir,
        *(["--restore"] if action == "restore" else []))


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
    managed = pathlib.Path("/Library/Managed Preferences/com.anthropic.claudefordesktop.plist")
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
    require(snapshot(path) == state["prepared"], "准备副本已改变，请重新准备。")
    verify_signature(path)
    return path


def prepare(args):
    state = load_state(args)
    if state and state["phase"] == "installed":
        require(snapshot(args.app) == state["installed"], "已安装文件被其他操作修改，停止。")
        print("合并补丁已安装；无需重新构建。")
        return state
    before = snapshot(args.app)
    build = source(args.app)
    config(args)
    backup = args.state_dir / "Claude.original.app"
    if not backup.exists():
        with tempfile.TemporaryDirectory(prefix=".original-", dir=str(args.state_dir)) as temp:
            candidate = pathlib.Path(temp) / "Claude.app"
            run("/usr/bin/ditto", args.app, candidate)
            language(args, candidate, "restore")
            source(candidate)
            verify_signature(candidate, official=True)
            require(snapshot(args.app) == before, "Claude 在准备期间更新了文件。")
            candidate.rename(backup)
    require(source(backup) == build, "现有官方备份属于不同构建，停止以免替换当前版本。")
    verify_signature(backup, official=True)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=str(args.state_dir)) as temp:
        candidate = pathlib.Path(temp) / "Claude.app"
        run("/usr/bin/ditto", backup, candidate)
        language(args, candidate, "install")
        data, header_hash = patched_asar(read(candidate / ASAR))
        atomic(candidate / ASAR, data, 0o644)
        info = bundle_version(candidate)
        info["ElectronAsarIntegrity"]["Resources/app.asar"] = {"algorithm": "SHA256", "hash": header_hash}
        atomic(candidate / "Contents/Info.plist", plistlib.dumps(info, sort_keys=False), 0o644)
        # 本构建未启用框架内嵌 ASAR 摘要；仅重签最外层应用，嵌套官方组件不改动。
        entitlements = plistlib.loads(run("/usr/bin/codesign", "-d", "--entitlements", ":-", candidate).stdout)
        # 临时签名不能冒用官方团队或钥匙串访问组，否则 AMFI 会拒绝启动。
        for key in ("com.apple.application-identifier", "com.apple.developer.team-identifier", "keychain-access-groups"):
            entitlements.pop(key, None)
        # 保留 hardened runtime，同时允许加载保持官方签名的 Electron 框架。
        entitlements["com.apple.security.cs.disable-library-validation"] = True
        entitlements_path = pathlib.Path(temp) / "entitlements.plist"
        atomic(entitlements_path, plistlib.dumps(entitlements))
        run("/usr/bin/codesign", "--force", "--sign", "-", "--options", "runtime",
            "--entitlements", entitlements_path, candidate)
        verify_signature(candidate)
        require(digest(read(candidate / NODE)) == build["node"], "原生模块被意外修改。")
        require(snapshot(args.app) == before, "Claude 在准备期间更新了文件。")
        target = args.state_dir / "Claude.prepared.app"
        if target.exists():
            shutil.rmtree(target)
        candidate.rename(target)
    state = {"schema": 1, "app": str(args.app), "phase": "prepared", "before": before,
             "original": snapshot(backup), "prepared": snapshot(target)}
    persist(args, state)
    print("已在副本准备：官方中文＋原生电脑控制开关＋内置浏览器。正在运行的 Claude 未修改。")
    return state


def install(args):
    require(not processes(args.app), "Claude 仍在运行。请等任务完成并正常退出后重试；可以先使用 --prepare。")
    state = load_state(args)
    if not state or state["phase"] == "restored":
        state = prepare(args)
    if state["phase"] == "installed":
        require(snapshot(args.app) == state["installed"], "已安装文件被其他操作修改。")
        browser(args)
        print("合并补丁已安装，原生浏览器配置已核对。")
        return
    require(state["phase"] == "prepared" and snapshot(args.app) == state["before"],
            "当前 Claude 与准备时不一致，请重新准备。")
    backup = args.state_dir / "Claude.original.app"
    require(snapshot(backup) == state["original"], "原始备份缺失或被修改，停止安装。")
    verify_signature(backup, official=True)
    candidate = prepared(args, state)
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
        browser(args)
        state.update(phase="installed", installed=snapshot(args.app))
        persist(args, state)
    except BaseException:
        if moved:
            if args.app.exists():
                args.app.rename(candidate)
            previous.rename(args.app)
        browser(args, flag)
        state["phase"] = "prepared"
        persist(args, state)
        raise
    shutil.rmtree(previous)
    print("已安装：官方中文＋原生电脑控制开关＋官方内置浏览器。首次使用请在 Claude 设置中启用电脑控制并核对系统权限。")
    if not args.no_restart:
        run("/usr/bin/open", "-a", args.app)


def restore(args):
    state = load_state(args)
    require(state is not None, "没有本工具的原生补丁记录。")
    if state["phase"] in ("prepared", "restored"):
        print("尚未应用原生补丁，无需恢复应用。")
        return
    require(state["phase"] == "installed", "上次事务中断，需先核对原应用与备份。")
    require(not processes(args.app), "请先正常退出 Claude，再恢复。")
    require(snapshot(args.app) == state["installed"], "应用已被其他操作修改，停止恢复。")
    backup = args.state_dir / "Claude.original.app"
    require(snapshot(backup) == state["original"], "原始应用备份被修改。")
    verify_signature(backup, official=True)
    path, current, _, _ = config(args)
    flag = state["browser"]
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
            browser(args, flag)
            state["phase"] = "restored"
            persist(args, state)
        except BaseException:
            if args.app.exists():
                args.app.rename(candidate)
            previous.rename(args.app)
            raise
    shutil.rmtree(previous)
    print("已恢复原始官方应用与安装前的浏览器开关，中文注册一并撤销。")
    if not args.no_restart:
        run("/usr/bin/open", "-a", args.app)


def check(args):
    bundle_version(args.app)
    state = load_state(args)
    path, value, _, _ = config(args)
    if state and state["phase"] == "installed":
        require(snapshot(args.app) == state["installed"], "已安装补丁的文件校验失败。")
        verify_signature(args.app)
        print("核验通过：合并补丁已安装，电脑控制入口已恢复。")
    else:
        source(args.app)
        if state and state["phase"] == "prepared":
            prepared(args, state)
            print("核验通过：合并补丁副本已准备，尚未应用。")
        else:
            print("核验通过：当前构建可准备原生功能补丁。")
    print("当前 Magpie 配置的官方内置浏览器：" + ("开启" if value.get("builtinBrowserEnabled") is True else "关闭"))
    print("系统权限与模型实际操作能力须另行验证；本检查不代表已获辅助功能或屏幕录制权限。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "prepare", "install", "restore"))
    parser.add_argument("--app", type=pathlib.Path, default=pathlib.Path("/Applications/Claude.app"))
    parser.add_argument("--backup-dir", type=pathlib.Path, default=pathlib.Path.home() / "Library/Application Support/ClaudeOfficialZhHans/3.6556.2")
    parser.add_argument("--catalog-dir", type=pathlib.Path, default=ROOT / "catalogs")
    parser.add_argument("--config-dir", type=pathlib.Path, default=pathlib.Path.home() / "Library/Application Support/Claude-3p/configLibrary")
    parser.add_argument("--no-restart", action="store_true")
    args = parser.parse_args()
    args.app = args.app.absolute()
    args.backup_dir = args.backup_dir.absolute()
    args.state_dir = args.backup_dir / ("native-" + environment())
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
