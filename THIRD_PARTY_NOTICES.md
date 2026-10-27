# 第三方代码说明

macOS 原生功能补丁参考了 [Claude-Native-Unlock](https://github.com/canner0725-byte/Claude-Native-Unlock) 的官方功能开关定位和 ASAR 紧凑重排方法，基于提交 `c7134b20252561e5043f8536d1a098157356efac` 适配已登记的 Intel 和 Apple Silicon 构建。

本工具仅插入电脑控制启用开关和 macOS 版本范围；保留官方保存面板探针、受保护文档检查、逐应用授权和操作审查。

上游许可如下：

MIT License

Copyright (c) 2026 Claude Native Unlock contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Python 运行环境

macOS Release 包内的 `runtime` 包含 [python-build-standalone 20261026](https://github.com/astral-sh/python-build-standalone/releases/tag/20261026) 的 CPython 3.13.18 原始压缩包，分别用于 Apple Silicon 和 Intel。项目和构建脚本使用 Mozilla Public License 2.0，CPython 及其依赖使用各自的许可证。原始压缩包内保留 Python 和 pip 的许可文件；Release 包的 `runtime-licenses` 同时保留上游版本提供的许可文本。上游源码和完整许可见 [python-build-standalone](https://github.com/astral-sh/python-build-standalone/tree/20261026)。

- Apple Silicon 原始压缩包 SHA-256：`8392b6ea51d94391befb2c31ebe75463f045d0b69dfcf5e1bb3234e1f5fa3405`
- Intel 原始压缩包 SHA-256：`7412c19d896c99431b74a18a5643e110449a7f9590fbab179c3e5ab27b9aa9e3`
