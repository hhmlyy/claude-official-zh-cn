"""原生补丁：真实 ASAR 保真、配置隔离、安装失败回滚与官方原版恢复。"""
import importlib.util
import io
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
CATALOG_DIR = pathlib.Path(os.environ.get("CLAUDE_NATIVE_CATALOG_DIR", str(ROOT / "catalogs")))


class ArchitectureTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CLAUDE_NATIVE_HOST_ARCH"), "未指定真实测试机架构")
    def test_actual_host_architecture(self):
        self.assertEqual(native.host_architecture(), os.environ["CLAUDE_NATIVE_HOST_ARCH"])

    def test_macos_versions_are_not_locked_to_one_release(self):
        for version in ("13.7.6", "14.8", "15.7", "26.5.2", "27.0"):
            with self.subTest(version=version), \
                    mock.patch.object(native.sys, "platform", "darwin"), \
                    mock.patch.object(native, "host_architecture", return_value="arm64"), \
                    mock.patch.object(native.platform, "mac_ver", return_value=(version, (), "arm64")), \
                    mock.patch.object(native.sys, "stderr", new_callable=io.StringIO) as warning:
                self.assertEqual(native.environment(), "arm64")
                self.assertEqual("macOS 14" in warning.getvalue(), version.startswith("13."))

    def test_unsupported_platform_or_architecture_is_rejected(self):
        with mock.patch.object(native.sys, "platform", "linux"), \
                mock.patch.object(native, "host_architecture", return_value="x86_64"):
            with self.assertRaisesRegex(ValueError, "macOS"):
                native.environment()
        with mock.patch.object(native.sys, "platform", "darwin"), \
                mock.patch.object(native, "host_architecture", return_value="unsupported"):
            with self.assertRaisesRegex(ValueError, "macOS"):
                native.environment()


class FrameworkIntegrityTests(unittest.TestCase):
    def test_universal_digest_is_updated_and_mismatches_fail_closed(self):
        original = {"ElectronAsarIntegrity": {
            "Resources/ion-dist.asar": {"algorithm": "SHA256", "hash": "1" * 64},
            "Resources/app.asar": {"algorithm": "SHA256", "hash": "0" * 64}}}
        updated = {"ElectronAsarIntegrity": {
            "Resources/app.asar": {"algorithm": "SHA256", "hash": "2" * 64},
            "Resources/ion-dist.asar": {"algorithm": "SHA256", "hash": "1" * 64}}}
        old_digest = bytes.fromhex("1d0353c4a11e58a606fae70a92ac97903fddf53f426ffed57165327ef704fc52")
        new_digest = bytes.fromhex("9911ca9d2705c9f3f7a6573b93e380e613ce5a3e27a03f391090c083d1857f94")
        sentinel = b"AGbevlPCksUGKNL8TSn7wGmJEuJsXb2A"
        old_slot, new_slot = b"\x01\x01" + old_digest, b"\x01\x01" + new_digest
        with tempfile.TemporaryDirectory(prefix="claude-digest-test-") as temp:
            app = pathlib.Path(temp)
            framework = app / native.FRAMEWORK
            framework.parent.mkdir(parents=True)
            baseline = b"first" + sentinel + old_slot + b"second" + sentinel + old_slot + b"end"
            framework.write_bytes(baseline)
            with mock.patch.object(native, "run", return_value=types.SimpleNamespace(stdout=b"x86_64 arm64")):
                self.assertTrue(native.update_framework_digest(app, original, updated))
                self.assertEqual(framework.read_bytes(), baseline.replace(old_slot, new_slot))
                bad = baseline[:-1] + b"x"
                bad = bad.replace(old_slot, b"\x01\x01" + b"x" * 32, 1)
                framework.write_bytes(bad)
                with self.assertRaisesRegex(ValueError, "与原始应用不一致"):
                    native.update_framework_digest(app, original, updated)
                self.assertEqual(framework.read_bytes(), bad)
                disabled = b"first" + sentinel + bytes(34) + b"second" + sentinel + bytes(34)
                framework.write_bytes(disabled)
                self.assertFalse(native.update_framework_digest(app, original, updated))
                self.assertEqual(framework.read_bytes(), disabled)

    def test_framework_without_digest_is_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="claude-digest-test-") as temp:
            app = pathlib.Path(temp)
            framework = app / native.FRAMEWORK
            framework.parent.mkdir(parents=True)
            framework.write_bytes(b"no embedded digest")
            self.assertFalse(native.update_framework_digest(app, {}, {}))
            self.assertEqual(framework.read_bytes(), b"no embedded digest")


class LanguageRegistrationTests(unittest.TestCase):
    def test_variable_names_are_discovered_and_registration_is_checked(self):
        original = (b'var Ab=["en-US","ja-JP"];function test(e){return Ab.includes(e)}'
                    b'var Cd=["en-US","ja-JP"];function choose(e,t=Cd){let n=new Map;}'
                    b'"/i18n/dynamic/"')
        result = native.registered_bundle(original)
        self.assertIn(b'Ab.push("zh-Hans")', result)
        self.assertIn(b'Cd.push("zh-Hans")', result)
        with self.assertRaisesRegex(ValueError, "已经修改"):
            native.registered_bundle(result)
        with self.assertRaisesRegex(ValueError, "结构不匹配"):
            native.registered_bundle(original.replace(b'var Cd=["en-US","ja-JP"]',
                                                       b'var Cd=["en-US","fr-FR"]'))
        with self.assertRaisesRegex(ValueError, "唯一识别"):
            native.registered_bundle(original + original)


class BrowserConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="claude-native-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = pathlib.Path(self.temp.name).resolve()
        policy = mock.patch.object(native, "MANAGED_POLICY", self.directory / "managed" / "claude.plist")
        policy.start()
        self.addCleanup(policy.stop)
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

    def test_managed_policy_is_rejected(self):
        native.MANAGED_POLICY.parent.mkdir()
        native.MANAGED_POLICY.touch()
        with self.assertRaisesRegex(ValueError, "组织管理策略"):
            native.browser(self.args)


class RestoreWithoutConfigTests(unittest.TestCase):
    def test_missing_config_is_safe_only_when_install_did_not_change_it(self):
        for already_enabled in (True, False):
            with self.subTest(already_enabled=already_enabled), \
                    tempfile.TemporaryDirectory(prefix="claude-restore-test-") as temp:
                root = pathlib.Path(temp).resolve()
                app, state_dir = root / "Claude.app", root / "state"
                backup = state_dir / "Claude.original.app"
                app.mkdir()
                backup.mkdir(parents=True)
                (app / "marker").write_text("installed")
                (backup / "marker").write_text("original")
                state = {"schema": 1, "app": str(app), "phase": "installed",
                         "installed": native.snapshot(app, ["marker"]),
                         "original": native.snapshot(backup, ["marker"]),
                         "browser": {"id": "fixture", "present": already_enabled,
                                     "value": True if already_enabled else None}}
                native.save(state_dir / "state.json", state)
                args = types.SimpleNamespace(app=app, state_dir=state_dir,
                                             config_dir=root / "missing-config", no_restart=True)

                def copy_app(command, source, destination):
                    self.assertEqual(command, "/usr/bin/ditto")
                    shutil.copytree(source, destination)

                with mock.patch.object(native, "processes", return_value=[]), \
                        mock.patch.object(native, "verify_signature"), \
                        mock.patch.object(native, "run", side_effect=copy_app):
                    if already_enabled:
                        native.restore(args)
                        self.assertEqual((app / "marker").read_text(), "original")
                        self.assertEqual(native.load_state(args)["phase"], "restored")
                    else:
                        with self.assertRaisesRegex(ValueError, "文件缺失"):
                            native.restore(args)
                        self.assertEqual((app / "marker").read_text(), "installed")
                        self.assertEqual(native.load_state(args)["phase"], "installed")


@unittest.skipUnless(FIXTURE, "设置 CLAUDE_NATIVE_FIXTURE 指向官方应用副本")
class NativeFixtureTests(unittest.TestCase):
    def setUp(self):
        self.architecture = os.environ.get("CLAUDE_NATIVE_FIXTURE_ARCH", native.host_architecture())
        temp = tempfile.TemporaryDirectory(prefix="claude-test-policy-")
        self.addCleanup(temp.cleanup)
        policy = mock.patch.object(native, "MANAGED_POLICY", pathlib.Path(temp.name).resolve() / "claude.plist")
        policy.start()
        self.addCleanup(policy.stop)
        if os.environ.get("CLAUDE_NATIVE_FIXTURE_ARCH"):
            patcher = mock.patch.object(native, "host_architecture", return_value=self.architecture)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_source_rejects_an_incompatible_architecture(self):
        with mock.patch.object(native, "host_architecture", return_value="unsupported"):
            with self.assertRaisesRegex(ValueError, "处理器不匹配"):
                native.source(pathlib.Path(FIXTURE))

    def test_asar_changes_only_the_two_availability_gates(self):
        original = native.read(pathlib.Path(FIXTURE) / native.ASAR)
        patched, header_hash = native.patched_asar(original)
        self.assertEqual(native.main_bytes(patched).replace(native.GATES.encode(), b"", 1),
                         native.main_bytes(original))
        before, old_base = native.unpack(original)
        after, new_base = native.unpack(patched)
        old_nodes, new_nodes = dict(native.nodes(before)), dict(native.nodes(after))
        self.assertEqual(set(old_nodes), set(new_nodes))
        main_path, _ = native.main_path(original)
        for path, node in old_nodes.items():
            if path == main_path:
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
        with self.assertRaisesRegex(ValueError, "已经有定义"):
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
            state_dir = backup / ("native-" + self.architecture)
            state_dir.mkdir(parents=True)
            args = types.SimpleNamespace(app=app, backup_dir=backup, config_dir=configs,
                                         catalog_dir=CATALOG_DIR, state_dir=state_dir, no_restart=True)
            baseline = native.snapshot(app)
            native.prepare(args)
            self.assertEqual(native.snapshot(app), baseline)
            if baseline[native.ION_ASAR] is not None:
                original_ion = native.read(state_dir / "Claude.original.app" / native.ION_ASAR)
                patched_ion = native.read(state_dir / "Claude.prepared.app" / native.ION_ASAR)
                old_header, old_base = native.unpack(original_ion)
                new_header, new_base = native.unpack(patched_ion)
                old_nodes, new_nodes = dict(native.nodes(old_header)), dict(native.nodes(new_header))
                registry = native.language_layout(state_dir / "Claude.original.app")[2][0]
                for path, node in old_nodes.items():
                    if path == registry:
                        continue
                    new = new_nodes[path]
                    start, stop = old_base + int(node["offset"]), new_base + int(new["offset"])
                    self.assertEqual(original_ion[start:start + node["size"]],
                                     patched_ion[stop:stop + new["size"]], path)
                self.assertEqual(native.asar_file(patched_ion, registry),
                                 native.registered_bundle(native.asar_file(original_ion, registry)))
                for _, path, expected, _ in native.CATALOGS:
                    self.assertEqual(native.digest(native.asar_file(patched_ion, path)), expected)
                info = native.bundle_version(state_dir / "Claude.prepared.app")
                encoded = json.dumps(new_header, separators=(",", ":"), ensure_ascii=False).encode()
                self.assertEqual(info["ElectronAsarIntegrity"]["Resources/ion-dist.asar"]["hash"],
                                 native.digest(encoded))
            original_source = native.source

            def source_with_other_backup(path):
                build = original_source(path)
                return dict(build, node="different") if path == state_dir / "Claude.original.app" else build

            with mock.patch.object(native, "source", side_effect=source_with_other_backup):
                with self.assertRaisesRegex(ValueError, "备份属于不同构建"):
                    native.prepare(args)
            self.assertEqual(native.snapshot(app), baseline)
            language_path = app / (native.ION_ASAR if baseline[native.ION_ASAR] else native.REGISTRY)
            original_language = native.read(language_path)
            native.atomic(language_path, original_language + b" ", 0o644)
            with self.assertRaisesRegex(ValueError, "备份与当前语言资源不一致"):
                native.prepare(args)
            native.atomic(language_path, original_language, 0o644)
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

    def test_language_only_install_and_restore(self):
        with tempfile.TemporaryDirectory(prefix="claude-language-roundtrip-") as temp:
            root = pathlib.Path(temp).resolve()
            app, backup = root / "Claude.app", root / "backup"
            native.run("/usr/bin/ditto", pathlib.Path(FIXTURE), app)
            state_dir = backup / ("language-" + self.architecture)
            state_dir.mkdir(parents=True)
            args = types.SimpleNamespace(app=app, backup_dir=backup, config_dir=root / "unused-config",
                                         catalog_dir=CATALOG_DIR, state_dir=state_dir,
                                         no_restart=True, language_only=True)
            baseline = native.snapshot(app)
            native.check(args)
            native.install(args)
            native.check(args)
            installed = native.snapshot(app)
            self.assertEqual(installed[native.ASAR], baseline[native.ASAR])
            self.assertFalse(args.config_dir.exists())
            native.install(args)
            self.assertEqual(native.snapshot(app), installed)
            native.restore(args)
            self.assertEqual(native.snapshot(app), baseline)
            native.verify_signature(app, official=True)
            native.restore(args)

    def test_legacy_language_backup_can_be_migrated(self):
        if not (pathlib.Path(FIXTURE) / native.REGISTRY).is_file():
            self.skipTest("此应用没有旧版语言资源布局")
        with tempfile.TemporaryDirectory(prefix="claude-legacy-roundtrip-") as temp:
            root = pathlib.Path(temp).resolve()
            app, backup = root / "Claude.app", root / "backup"
            native.run("/usr/bin/ditto", pathlib.Path(FIXTURE), app)
            state_dir = backup / ("language-" + self.architecture)
            state_dir.mkdir(parents=True)
            registry = app / native.REGISTRY
            original = native.read(registry)
            (backup / "shared-52.original.js").write_bytes(original)
            native.atomic(registry, native.registered_bundle(original), 0o644)
            for name, target, _, _ in native.CATALOGS:
                shutil.copyfile(CATALOG_DIR / name, app / "Contents/Resources/ion-dist" / target)
            args = types.SimpleNamespace(app=app, backup_dir=backup, config_dir=root / "unused-config",
                                         catalog_dir=CATALOG_DIR, state_dir=state_dir,
                                         no_restart=True, language_only=True)
            native.prepare(args)
            native.install(args)
            native.restore(args)
            self.assertEqual(native.read(registry), original)
            native.verify_signature(app, official=True)


if __name__ == "__main__":
    unittest.main()
