# Project Context

## 这个项目是干什么的

`dsh-image-vision` 是 Xiaozhuang DSH 的单向原生插件分发副本。唯一开发源是主仓库，当前目标 Harness 0.2.1-alpha.1。

## 代码结构是什么

- `payload/<id>/product/plugins/<id>/`：自有源码、Cordis patch、必要资源和构建产物。
- `payload/shared/`：针对官方 0.2.1 的通用接口补丁，安装 AI 只合入缺失的相关部分。
- `manifest.json`、`README*.md`、`INSTALL.md`、`AGENTS.md`：版本、组合与安装说明。
- `docs/`：保留真实产品截图；`tests/payload.test.mjs` 检查发布文件、大小、组装入口及版本。

## 关键入口在哪里

插件 `package.json` 与 `cordis.patch.yml` 声明目录安装与 Host/Client 入口；manifest 列出所包含插件、原生行和兼容补丁。

## 最近改了什么

### 2026-10-07 - 与主仓 0.2.1 适配同步

- 本次任务：从已推送的主仓源码同步全部相关独立插件版本。
- 改了哪些文件：payload、manifest、双语 README、INSTALL、发布包定向检查及本文件。
- 改了什么：同步 vision 的当前原生版本，将旧宿主补丁更新为官方 0.2.1 基线，保留现有截图和安装目录结构。
- 为什么这样改：独立仓库必须与本地实际运行的最新主仓插件一致，避免使用旧接口或旧 Profile 副本。
- 影响了哪些模块：仅所选插件的分发源码、运行资源与安装说明；不带入用户数据、依赖目录或测试输出。
- 验证：主仓已验证组合运行；本仓验证所有交付文件存在与大小、原生版本和入口，并检查编译后 JavaScript 语法。未进行哈希值对比。
