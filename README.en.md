# dsh-image-vision

English | [中文](README.md)

[![DSH Plugin](https://img.shields.io/badge/DSH-Plugin-111111)](https://github.com/niushuanan/xiaozhuang-dsh) [![Release](https://img.shields.io/badge/release-xiaozhuang--v0.4.2-2563eb)](https://github.com/niushuanan/dsh-image-vision/releases/tag/xiaozhuang-v0.4.2) [![MIT](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

Let vision-capable models read native attachments while giving text-only models an image tool that supports follow-up questions.

<p align="center"><img src="docs/04-image-understanding.webp" alt="Image upload in the conversation composer" width="800"></p>

## Install

1. Open [Releases](https://github.com/niushuanan/dsh-image-vision/releases/latest) and download the attached ZIP.
2. Give the ZIP to an AI that can read and modify the target DSH project.
3. Tell the AI: **Read AGENTS.md, INSTALL.md, and manifest.json first. Install only this plugin and preserve existing plugins, data, conversations, attachments, and settings.**
4. The installing AI merges the code and Cordis rows into the target version and validates only the entry points directly owned by this plugin.

## Requirements

- The installing AI must copy `support/image-vision` into a user-level Skill directory.
- The text-model vision fallback needs Python 3 and the user's own DashScope API key. No credential is included.

## Contents

- <code>payload/</code>: plugin code and required runtime assets copied from the main repository.
- <code>manifest.json</code>: composition rows, sources, main-repository commit, and per-file SHA-256.
- <code>INSTALL.md</code>: direct installation, conflict adaptation, failure recovery, and narrow verification.
- <code>docs/</code>: real product screenshots from this version.

## Source and license

This repository is a one-way distribution mirror of [Xiaozhuang DSH](https://github.com/niushuanan/xiaozhuang-dsh), not an independent development source. It is synchronized from main-repository commit [`49b1c5207b`](https://github.com/niushuanan/xiaozhuang-dsh/commit/49b1c5207b1556515752c6bf9e7902c1a5964ad9) and released as [`xiaozhuang-v0.4.2`](https://github.com/niushuanan/dsh-image-vision/releases/tag/xiaozhuang-v0.4.2). Licensed under the [MIT License](LICENSE).
