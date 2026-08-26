# dsh-image-vision

[English](README.en.md) | 中文

[![DSH Plugin](https://img.shields.io/badge/DSH-Plugin-111111)](https://github.com/niushuanan/xiaozhuang-dsh) [![Release](https://img.shields.io/badge/release-xiaozhuang--v0.4.2-2563eb)](https://github.com/niushuanan/dsh-image-vision/releases/tag/xiaozhuang-v0.4.2) [![MIT](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

让视觉模型直接读取原生附件，并为纯文本模型提供可连续追问的图片理解工具。

<p align="center"><img src="docs/04-image-understanding.webp" alt="对话输入框中的图片上传入口" width="800"></p>

## 安装

1. 打开 [Releases](https://github.com/niushuanan/dsh-image-vision/releases/latest)，下载附带的 ZIP。
2. 把 ZIP 交给能够读取并修改目标 DSH 项目的 AI。
3. 对 AI 说：**先阅读压缩包里的 AGENTS.md、INSTALL.md 和 manifest.json，只安装这个插件，并保留现有插件、数据、对话、附件和设置。**
4. 安装 AI 会按目标 DSH 的当前结构合入代码和 Cordis 行，只验证本插件直接涉及的入口。

## 运行要求

- 安装 AI 需要把 `support/image-vision` 复制到用户级 Skill 目录。
- 纯文本模型的后备视觉需要 Python 3 和用户自己的 DashScope API Key；仓库不包含任何密钥。

## 内容

- <code>payload/</code>：从主仓库复制的插件代码和必要运行资源。
- <code>manifest.json</code>：插件组成、来源、主仓库 commit 和逐文件 SHA-256。
- <code>INSTALL.md</code>：直接安装、冲突适配、失败恢复和最小验证说明。
- <code>docs/</code>：当前版本的真实产品截图。

## 来源与许可

本仓库是 [Xiaozhuang DSH](https://github.com/niushuanan/xiaozhuang-dsh) 的单向发布副本，不是独立开发源。当前内容同步自主仓库 commit [`49b1c5207b`](https://github.com/niushuanan/xiaozhuang-dsh/commit/49b1c5207b1556515752c6bf9e7902c1a5964ad9)，版本为 [`xiaozhuang-v0.4.2`](https://github.com/niushuanan/dsh-image-vision/releases/tag/xiaozhuang-v0.4.2)。代码采用 [MIT License](LICENSE)。
