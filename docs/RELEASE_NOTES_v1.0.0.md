# WeRead2Notion AI v1.0.0

首个稳定版本现已发布。

WeRead2Notion AI 可以通过 GitHub Actions，把微信读书数据自动同步到一套可直接 Duplicate 的 Notion 阅读管理模板，无需自己部署服务器。

![WeRead2Notion AI 同步后的 Notion 阅读仪表盘](https://raw.githubusercontent.com/hodgekou/weread2notion-AI/main/asset/notion-dashboard.png)

## 主要功能

- 同步当前微信读书书架、作者、分类和阅读状态
- 同步阅读进度、阅读时长及日、周、月、年统计
- 将划线和个人想法按章节写入书籍正文
- 使用微信读书人工“读完”标记判断已读状态
- 支持普通增量同步和带 JSON 备份的全量重建
- 书籍移出当前书架后，可自动归档对应 Notion 页面和同步内容
- 提供 Notion 原生图表、视图及个性化同步设置
- 每天通过 GitHub Actions 自动运行，无需常驻电脑或服务器

## 开始使用

1. Duplicate [Notion Template](https://app.notion.com/p/wph/Template-3a329affe5af800b8581f98b71e948fb)。
2. 创建 Notion Integration，并连接到 Duplicate 后的最外层页面。
3. Fork [GitHub 项目](https://github.com/hodgekou/weread2notion-AI)。
4. 配置 `WEREAD_API_KEY`、`NOTION_TOKEN`、`NOTION_PAGE` 三个 Actions Secrets。
5. 手动运行一次 `weread sync`，之后等待每日自动同步。

完整步骤请查看项目 [README](../README.md)。

## 注意事项

同步器会更新其管理的 Notion 数据库属性、统计记录和书籍正文中的自动同步区域。请不要把需要长期保留的私人内容只写在这些自动管理区域内。

本项目的代码、文档和 Notion 模板适配工作完全由 OpenAI ChatGPT（Codex，GPT-5 系列模型）生成。

**Full Changelog**: https://github.com/hodgekou/weread2notion-AI/commits/v1.0.0
