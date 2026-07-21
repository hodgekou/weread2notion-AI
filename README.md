# WeRead2Notion AI

将你的微信读书书架、阅读进度、章节、划线、个人想法和阅读统计，自动同步到一套完整的 Notion 阅读管理模板。

无需在电脑上长期运行程序。完成一次配置后，GitHub Actions 会每天自动同步。

## 开始使用

### 第一步：复制 Notion 模板

打开下面的模板页面，然后点击右上角的 `Duplicate`，将它复制到你自己的 Notion Workspace：

[复制 WeRead2Notion AI Template](https://app.notion.com/p/wph/Template-3a329affe5af800b8581f98b71e948fb)

复制完成后，请保存新页面的完整 URL。后面配置 `NOTION_PAGE` 时会用到它。

> 请使用 Duplicate 后的新页面，不要填写上面的公共模板地址。每次 Duplicate 都会生成一个新的页面 ID。

### 第二步：创建并连接 Notion Integration

1. 打开 [Notion Integrations](https://www.notion.so/profile/integrations)。
2. 点击 `New integration`。
3. 名称填写 `WeRead2Notion-AI`。
4. Workspace 选择刚才复制模板所在的 Workspace。
5. 在 Capabilities 中启用：
   - `Read content`
   - `Insert content`
   - `Update content`
6. 保存并复制生成的 Internal Integration Secret，后面将它配置为 `NOTION_TOKEN`。
7. 返回 Duplicate 后的 Notion 页面，点击右上角 `••• → Connections`，添加 `WeRead2Notion-AI`。

Integration 必须连接到最外层的“微信读书”模板页面，这样才能访问页面内的书架、章节和统计数据库。

### 第三步：Fork 项目并配置 Secrets

点击 GitHub 页面右上角的 `Fork`，将本项目 Fork 到你自己的 GitHub 账号。

进入你 Fork 后的仓库，然后打开：

`Settings → Secrets and variables → Actions → New repository secret`

依次创建以下三个 Repository secrets：

| Secret 名称 | 填写内容 |
| --- | --- |
| `WEREAD_API_KEY` | 你的微信读书 Gateway API Key，可前往 [微信读书助手](https://weread.qq.com/r/weread-skills) 获取 |
| `NOTION_TOKEN` | 第二步创建的 `WeRead2Notion-AI` Integration Secret |
| `NOTION_PAGE` | 第一步 Duplicate 后的新 Notion 页面完整 URL |

Secret 名称必须完全一致，并注意以下对应关系：

- `NOTION_TOKEN` 所属的 Integration 必须是你在页面 Connections 中添加的同一个 Integration。
- `NOTION_PAGE` 必须是你自己的 Duplicate 页面，不能使用公共 Template 页面。
- 不要把任何 Token 或 API Key 写进 README、代码或 `.env` 后提交到 GitHub。

### 第四步：测试同步

1. 打开你 Fork 仓库的 `Actions` 页面。
2. 在左侧选择 `weread sync`。
3. 点击 `Run workflow`。
4. 首次测试保持 `full` 未勾选。
5. 再次点击绿色的 `Run workflow` 开始同步。

等待 `Sync` 任务显示绿色勾号后，刷新 Duplicate 后的 Notion 页面。你的书架、阅读进度、阅读时长和统计数据将出现在模板中；划线和笔记会按章节写入对应书籍的正文。

微信读书当前书架是同步范围的唯一依据。书籍从微信读书书架移除后，下一次成功同步会将它在 Notion 中的书籍页面、章节、划线和笔记移入回收站。

工作流还会每天自动运行一次。只有需要备份并重新生成全部数据库记录时，才使用 `full` 模式。

## 常见问题

### 提示 `Could not find block with ID`

请检查：

- `NOTION_PAGE` 是否为 Duplicate 后的新页面 URL。
- 页面右上角 `••• → Connections` 中是否已经添加 `WeRead2Notion-AI`。
- GitHub 的 `NOTION_TOKEN` 是否属于该 Integration。
- Integration 和 Notion 页面是否位于同一个 Workspace。

### 日志显示了其他 Integration 名称

日志中的名称由 `NOTION_TOKEN` 决定，与 GitHub 仓库名称无关。请将 `NOTION_TOKEN` 替换为你自己创建的 `WeRead2Notion-AI` Integration Secret。

### “全部”视图没有数据

确认你使用的是最新 Template，并检查 Actions 是否已成功完成。不要在“全部”视图中添加空的年份筛选。

### “阅读时长格式化”显示“还未阅读”

请确认仓库已经同步到最新版本，然后重新运行一次 Actions。同步器会使用微信读书返回的累计阅读时长更新该字段。

## 问题反馈与功能建议

请通过 [GitHub Issues](https://github.com/hodgekou/weread2notion-AI/issues/new/choose) 提交问题或需求。仓库提供了面向维护者和 AI 的 Issue 模板，建议尽可能提供：

- 当前结果与期望结果
- 可以复现问题的操作步骤
- 脱敏后的 GitHub Actions 运行链接或日志
- 相关 Notion 页面、书名和 BookId
- 使用普通同步还是全量同步
- 可以判断问题已经解决的验收标准

除问题或需求描述外，其余信息可以留空或填写“不清楚”。请勿提交 `WEREAD_API_KEY`、`NOTION_TOKEN`、Cookie、`.env` 内容或其他敏感信息。

## 更多文档

- [技术文档与本地运行说明](docs/TECHNICAL.md)
- [微信读书助手](https://weread.qq.com/r/weread-skills)
- [提交问题或功能建议](https://github.com/hodgekou/weread2notion-AI/issues/new/choose)

## AI 生成声明

本项目的代码、文档以及 Notion 模板适配工作完全由 OpenAI ChatGPT（Codex，GPT-5 系列模型）生成。

## License

MIT
