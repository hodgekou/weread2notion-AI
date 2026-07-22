# WeRead2Notion AI 技术文档

将微信读书的书架、阅读进度、章节、划线、个人想法和阅读统计同步到 WeRead2Notion AI 模板，同时保留 Notion 页面原有的分栏、目录、视图、公式和样式。

[返回用户使用指南](../README.md)

## 设计原则

- **不重写主页**：同步器只创建、更新或归档数据库行，不调用整页内容替换。
- **全量同步先备份**：`--full` 会先导出所有数据库行为 JSON，再将旧行移入 Notion 回收站。
- **使用微信读书 Gateway API**：不需要 Cookie，API Key 从环境变量读取。
- **适配模板关系**：支持书架、作者、分类、日、周、月、年，以及可选的阅读记录数据库。
- **正文式笔记**：划线与个人想法按章节直接生成在书籍正文中，不再创建独立标签页或关系标签。
- **完整书架口径**：电子书、专辑/有声书和文章收藏都会进入书架。
- **书架是权威来源**：`/shelf/sync` 决定同步范围；仅存在于历史笔记或阅读记录中的书不会重新加入，已移出书架的书及其关联内容会移入 Notion 回收站。
- **人工状态优先**：只有书架条目的 `finishReading=1` 才同步为“已读”；阅读进度和 `finishTime` 不单独作为读完判据。
- **区分笔记口径**：统计总数包含书签；实际可导出的内容只有划线与个人想法/点评。
- **Notion 驱动配置**：每次联网同步前读取“设置”数据库；不存在时按环境变量和内置默认值运行，并自动创建默认配置。

## 要求

- Python 3.10+
- 已复制 WeRead2Notion AI 模板
- Notion Integration 已获得目标页面及所有子数据库权限
- 微信读书 Gateway API Key

模板页面必须包含这些数据库：

`书架`、`日`、`周`、`月`、`年`、`分类`、`作者`

数据库可以放在页面分栏或其他容器内；同步器会递归发现它们。数据库视图、筛选、排序、公式和页面布局不会被修改。

“设置”数据库不是模板校验的硬依赖。同步器会在缺失时自动创建，并创建唯一的“同步设置”配置页。对用户开放的配置属性只使用 Notion Checkbox 和 Number：

- `阅读完成进度强制改为100%`：Checkbox，默认 `false`
- `只同步我的书架书籍`：Checkbox，默认 `true`
- `同步划线和笔记`：Checkbox，默认 `true`
- `阅读统计起始年份`：Number，默认读取 `START_YEAR`

配置 Schema 只允许两类可编辑值：

- 布尔开关必须使用 Checkbox，读取结果为真正的 `true` 或 `false`。
- 数值配置必须使用 Number，可填写整数或实数，例如 `-1`、`0`、`1`、`2`、`0.5`。
- 禁止使用 Rich Text、Select、`"true"`、`"false"`、空字符串或其他字符串模拟布尔值和数值。

`同步配置版本（不可删除）` 是同步器维护的 Number 属性。它由配置模式版本、起始年份和三个布尔开关确定，用于发现设置变化。配置码变化时，普通同步会将当前书架全部加入本次更新范围；成功完成后才写回新的配置码。同步器兼容旧字段名称，已 Duplicate 的旧页面无需立即手动迁移。

## 本地配置

```bash
cp .env.example .env
```

```dotenv
WEREAD_API_KEY=wrk_xxx
NOTION_TOKEN=ntn_xxx
NOTION_PAGE=https://www.notion.so/your-page-id
```

可选配置：

```dotenv
START_YEAR=2023
BACKUP_DIR=backups
NOTION_VERSION=2026-03-11
NOTION_REQUEST_INTERVAL=0.34
```

## 安装与运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

检查模板：

```bash
weread2notion check
```

查看读取范围但不写入 Notion：

```bash
weread2notion sync --dry-run
```

日常同步：

```bash
weread2notion sync
```

安全重建全部数据：

```bash
weread2notion sync --full
```

全量同步顺序：

1. 读取并验证所有模板数据库。
2. 将旧数据库行导出到 `backups/*.json`。
3. 把旧行移入 Notion 回收站，不删除数据库和视图。
4. 重建年、月、周、日。
5. 重建作者、分类和书架。
6. 把划线与个人想法按章节直接写入书籍正文，不创建独立章节数据库。
7. 写入可用的阅读记录。

普通增量同步也会比较 `/shelf/sync` 与 Notion 书架。默认开启“只同步我的书架书籍”：Notion 中存在、但微信读书当前书架中不存在的条目，会连同旧版独立笔记/划线行和当前页面正文一起移入回收站；关闭后跳过该动作。清理动作只会在本次所需的微信读书请求全部成功后执行。

> 微信读书目前只提供书签数量，不提供书签正文，因此书签不会伪装成划线导入。

## GitHub Actions

仓库 Secrets：

- `WEREAD_API_KEY`
- `NOTION_TOKEN`
- `NOTION_PAGE`

工作流每天自动运行，也可以在 Actions 页面手动选择普通同步或全量同步。全量同步生成的 JSON 备份会作为 workflow artifact 上传。

## 开发

```bash
pip install -e '.[test]'
pytest
```

代码结构：

- `weread.py`：Gateway API、分页和升级提示处理
- `notion.py`：模板发现、Schema 适配、行级写入与备份
- `normalize.py`：时间、状态和书架条目标准化
- `sync.py`：按关系依赖执行同步
- `cli.py`：`check`、`sync`、`--dry-run`、`--full`

## 安全说明

不要把 API Key、Notion Token 或 `.env` 提交到 Git。全量同步的 JSON 备份可能包含你的书名、划线和笔记，也应作为私密数据保存。

## AI 生成声明

本项目的代码、文档以及 Notion 模板适配工作完全由 OpenAI ChatGPT（Codex，GPT-5 系列模型）生成。

## License

MIT
