"""Intel 原生补丁：真实 ASAR 保真、配置隔离、安装失败回滚与官方原版恢复。"""
import importlib.util
import json
import os
import pathlib
import plistlib
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_macos", ROOT / "native_macos.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
FIXTURE = os.environ.get("CLAUDE_NATIVE_FIXTURE")


class BrowserConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="claude-native-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = pathlib.Path(self.temp.name).resolve()
        self.path = self.directory / "fixture.json"
        (self.directory / "_meta.json").write_text(json.dumps({"appliedId": "fixture"}))
        self.original = {"inferenceProvider": "gateway", "inferenceGatewayBaseUrl": "http://127.0.0.1:9999",
                         "inferenceGatewayApiKey": "fixture-secret", "otherSetting": {"enabled": False}}
        self.path.write_text(json.dumps(self.original))
        self.args = types.SimpleNamespace(config_dir=self.directory)

    def test_only_browser_flag_changes_and_restore_keeps_new_settings(self):
        record = native.browser(self.args)
        value = json.loads(self.path.read_text())
        self.assertEqual(value, dict(self.original, builtinBrowserEnabled=True))
        value["laterSetting"] = "keep"
        self.path.write_text(json.dumps(value))
        native.browser(self.args, record)
        self.assertEqual(json.loads(self.path.read_text()), dict(self.original, laterSetting="keep"))

    def test_existing_enabled_flag_is_not_rewritten(self):
        self.path.write_text(json.dumps(dict(self.original, builtinBrowserEnabled=True)))
        before = self.path.stat().st_mtime_ns
        record = native.browser(self.args)
        native.browser(self.args, record)
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_changed_or_server_managed_config_is_rejected(self):
        record = native.browser(self.args)
        value = json.loads(self.path.read_text())
        value["builtinBrowserEnabled"] = False
        self.path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "其他操作"):
            native.browser(self.args, record)
        value["bootstrapUrl"] = "https://example.invalid/config"
        self.path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "服务器"):
            native.browser(self.args)

    def test_symlink_config_is_rejected(self):
        target = self.directory / "elsewhere.json"
        self.path.rename(target)
        self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "符号链接"):
            native.browser(self.args)


@unittest.skipUnless(FIXTURE, "设置 CLAUDE_NATIVE_FIXTURE 指向已核验的官方 Intel 应用副本")
class IntelFixtureTests(unittest.TestCase):
    def test_asar_changes_only_the_two_availability_gates(self):
        original = native.read(pathlib.Path(FIXTURE) / native.ASAR)
        patched, header_hash = native.patched_asar(original)
        self.assertEqual(native.main_bytes(patched).replace(native.GATES.encode(), b"", 1),
                         native.main_bytes(original))
        before, old_base = native.unpack(original)
        after, new_base = native.unpack(patched)
        old_nodes, new_nodes = dict(native.nodes(before)), dict(native.nodes(after))
        self.assertEqual(set(old_nodes), set(new_nodes))
        for path, node in old_nodes.items():
            if path == native.MAIN:
                continue
            new = new_nodes[path]
            start, stop = old_base + int(node["offset"]), new_base + int(new["offset"])
            self.assertEqual(original[start:start + node["size"]], patched[stop:stop + new["size"]], path)
        encoded = json.dumps(after, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(header_hash, native.digest(encoded))
        if shutil.which("node"):
            syntax = subprocess.run(["node", "--check"], input=native.main_bytes(patched),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(syntax.returncode, 0, syntax.stderr.decode(errors="replace"))
        with self.assertRaisesRegex(ValueError, "Intel 原版"):
            native.patched_asar(patched)

    def test_real_bundle_install_rollback_idempotence_and_restore(self):
        with tempfile.TemporaryDirectory(prefix="claude-native-roundtrip-") as temp:
            root = pathlib.Path(temp).resolve()
            app, backup, configs = root / "Claude.app", root / "backup", root / "config"
            configs.mkdir()
            (configs / "_meta.json").write_text(json.dumps({"appliedId": "fixture"}))
            original_config = {"inferenceProvider": "gateway", "inferenceGatewayApiKey": "fixture-secret"}
            config_path = configs / "fixture.json"
            config_path.write_text(json.dumps(original_config))
            native.run("/usr/bin/ditto", pathlib.Path(FIXTURE), app)
            state_dir = backup / "native-x86_64"
            state_dir.mkdir(parents=True)
            args = types.SimpleNamespace(app=app, backup_dir=backup, config_dir=configs,
                                         catalog_dir=ROOT / "catalogs", state_dir=state_dir, no_restart=True)
            baseline = native.snapshot(app)
            native.prepare(args)
            self.assertEqual(native.snapshot(app), baseline)
            backup_plist = state_dir / "Claude.original.app/Contents/Info.plist"
            original_plist = native.read(backup_plist)
            native.atomic(backup_plist, original_plist + b" ", 0o644)
            with self.assertRaisesRegex(ValueError, "备份缺失或被修改"):
                native.install(args)
            self.assertEqual(native.snapshot(app), baseline)
            native.atomic(backup_plist, original_plist, 0o644)
            with mock.patch.object(native, "browser", side_effect=[ValueError("injected failure"), None]):
                with self.assertRaisesRegex(ValueError, "injected failure"):
                    native.install(args)
            self.assertEqual(native.snapshot(app), baseline)
            self.assertEqual(json.loads(config_path.read_text()), original_config)
            self.assertFalse((state_dir / "Claude.previous.app").exists())
            native.install(args)
            native.check(args)
            installed = native.snapshot(app)
            self.assertNotEqual(installed[native.ASAR], baseline[native.ASAR])
            self.assertEqual(installed[native.NODE], baseline[native.NODE])
            entitlements = plistlib.loads(native.run("/usr/bin/codesign", "-d", "--entitlements", ":-", app).stdout)
            self.assertFalse(set(entitlements) & {"com.apple.application-identifier",
                             "com.apple.developer.team-identifier", "keychain-access-groups"})
            self.assertTrue(entitlements["com.apple.security.cs.allow-jit"])
            self.assertTrue(entitlements["com.apple.security.cs.disable-library-validation"])
            self.assertTrue(json.loads(config_path.read_text())["builtinBrowserEnabled"])
            native.install(args)
            self.assertEqual(native.snapshot(app), installed)
            native.restore(args)
            self.assertEqual(native.snapshot(app), baseline)
            self.assertEqual(json.loads(config_path.read_text()), original_config)
            native.verify_signature(app, official=True)


if __name__ == "__main__":
    unittest.main()
