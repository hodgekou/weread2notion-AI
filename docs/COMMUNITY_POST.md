# WeRead2Notion AI 社区发布文案

以下文案可以直接用于 V2EX、即刻、知乎、小红书、公众号或其他中文社区。发布前可根据平台长度删减。

## 标题候选

1. 我用 AI 做了一个微信读书自动同步到 Notion 的开源项目
2. WeRead2Notion AI：无需服务器，每天自动同步微信读书到 Notion
3. 开源分享：把微信读书书架、划线、笔记和阅读统计同步到 Notion

## 完整介绍

我最近整理并开源了 **WeRead2Notion AI**。

它可以把微信读书的当前书架、阅读状态、阅读进度、阅读时长、划线和个人想法自动同步到 Notion，并通过 Notion 原生数据库和图表展示阅读统计。

整个项目不需要自己购买或维护服务器。完成一次配置后，GitHub Actions 会每天自动同步。

目前支持：

- 当前微信读书书架、作者和分类
- 想读、在读、已读状态
- 阅读进度和阅读时长
- 日、周、月、年阅读统计
- 按章节写入书籍正文的划线和个人想法
- 普通增量同步与全量备份重建
- Notion 设置页和原生图表

使用方法也比较简单：

1. Duplicate Notion 模板
2. 创建并连接 Notion Integration
3. Fork GitHub 项目
4. 配置三个 Actions Secrets
5. 手动测试一次，以后每天自动运行

项目地址：https://github.com/hodgekou/weread2notion-AI

Notion 模板：https://app.notion.com/p/wph/Template-3a329affe5af800b8581f98b71e948fb

这是一个完全由 ChatGPT / Codex（GPT-5 系列模型）协助生成和维护的项目。如果它对你有帮助，欢迎 Star、Fork、提交 Issue，也欢迎反馈首次配置过程中不清楚的地方。

## 短文案

开源了一个微信读书 → Notion 自动同步工具：书架、状态、进度、阅读时长、划线、笔记和原生统计图表都可以同步。无需服务器，配置 GitHub Actions 后每天自动运行。

GitHub：https://github.com/hodgekou/weread2notion-AI

## 推荐标签

`#微信读书` `#Notion` `#开源项目` `#GitHub` `#效率工具` `#阅读管理` `#AI编程`
