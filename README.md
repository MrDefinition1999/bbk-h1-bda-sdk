# BBK H1 Native BDA SDK

这是一个独立的 BBK H1（`Y100`）原生 BDA SDK，面向 MIPS little-endian
freestanding 应用。公开 API 都回溯到 H1 专用的静态证据和可观察测试；尚未完成实机验证的候选 API 仍放在 `reverse/`。

## 已验证运行时模型

- CPU 代码是 MIPS32 little-endian 平面镜像，正常应用从 `0x83C00020` 加载。
- `0x83C00000..0x83C0001F` 由固件在调用前初始化，包含五个服务表指针。
- BDA 头选择文件 payload 偏移，不声明运行时加载地址。
- 对话框、堆内存、文件系统、RGB565 图形和 80 Hz 单调时钟均通过独立模拟器探针。
- 公开头文件位于 `sdk/include/`，逆向探针和候选布局位于 `reverse/`。

构建器支持单源探针和多源原生应用，也支持把一张 RGBA PNG 转成 H1 的四种菜单图标资源。

## 目录

```text
sdk/include/       已通过测试的公共 H1 API
h1_bda/            编译、打包、图标和校验实现
examples/          已通过模拟器测试的示例
docs/              验证行为和开发文档
reverse/           H1 专用探针、扫描器和证据
scripts/           工具链、验证和模拟器部署脚本
tests/             格式与构建回归测试
```

仓库不复制 9588 BDA 模板或复用 9588 固件 ABI 常量；9588 SDK 只用于研究方法参考。

English version: [README.en.md](README.en.md)

## 许可

原创源代码和文档采用 [Apache License 2.0](LICENSE)。验证截图及其中展示的第三方界面见 [NOTICE](NOTICE)。
