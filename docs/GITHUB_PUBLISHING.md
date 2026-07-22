# GitHub 仓库发布设置

以下设置需要仓库管理员权限。使用 `hodgekou` 登录 GitHub 后完成一次即可。

## About

进入仓库首页右侧 `About → Edit repository details`：

- Description：`微信读书 → Notion 自动同步：书架、进度、时长、划线、笔记与原生统计图表，无需服务器。`
- Website：`https://app.notion.com/p/wph/Template-3a329affe5af800b8581f98b71e948fb`

推荐 Topics：

`weread` `notion` `wechat-reading` `reading-notes` `github-actions` `python` `automation` `codex`

## Social preview

进入 `Settings → General → Social preview → Edit`，上传：

`asset/weread2notion-social-preview.png`

图片尺寸为 GitHub 推荐的 1280 × 640。

## v1.0.0 Release

进入 `Releases → Draft a new release`：

- Tag：`v1.0.0`
- Title：`WeRead2Notion AI v1.0.0`
- Description：复制 [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md) 内容
- 勾选 `Set as the latest release`

## 可选：开启 Discussions

如果后续用户变多，可在 `Settings → General → Features` 中开启 Discussions，用于展示配置经验、模板截图和常见问题。现阶段 Issues 已足够，不必立即开启。
