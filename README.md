# WeRead2Notion

将微信读书的书架、阅读进度、章节、划线、个人想法和阅读统计同步到
WeRead2Notion Pro 模板，同时保留 Notion 页面原有的分栏、目录、视图、公式和样式。

## Notion 模板

[复制 WeRead2Notion AI 模板](https://app.notion.com/p/wph/Codex-fd729affe5af83119383810f23b49175)

## 设计原则

- **不重写主页**：同步器只创建、更新或归档数据库行，不调用整页内容替换。
- **全量同步先备份**：`--full` 会先导出所有数据库行为 JSON，再将旧行移入 Notion 回收站。
- **使用微信读书 Gateway API**：不需要 Cookie，API Key 从环境变量读取。
- **适配 Pro 模板关系**：支持书架、作者、分类、章节、划线、笔记、日、周、月、年，以及可选的阅读记录数据库。
- **完整书架口径**：电子书、专辑/有声书和文章收藏都会进入书架。
- **区分笔记口径**：统计总数包含书签；实际可导出的内容只有划线与个人想法/点评。

## 要求

- Python 3.10+
- 已复制 WeRead2Notion Pro 模板
- Notion Integration 已获得目标页面及所有子数据库权限
- 微信读书 Gateway API Key

模板页面必须包含这些数据库：

`书架`、`笔记`、`划线`、`日`、`周`、`月`、`年`、`分类`、`作者`、`章节`

数据库可以放在页面分栏或其他容器内；同步器会递归发现它们。数据库视图、筛选、
排序、公式和页面布局不会被修改。

## 配置

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

先检查模板：

```bash
weread2notion check
```

查看读取范围，不写入 Notion：

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

全量同步的顺序是：

1. 读取并验证所有模板数据库。
2. 将旧数据库行导出到 `backups/*.json`。
3. 把旧行移入 Notion 回收站，不删除数据库和视图。
4. 重建年、月、周、日。
5. 重建作者、分类和书架。
6. 重建章节、划线、个人想法及关联关系。
7. 写入可用的阅读记录。

> 微信读书目前只提供书签数量，不提供书签正文，因此书签不会伪装成划线导入。

## GitHub Actions

在仓库 Secrets 中配置：

- `WEREAD_API_KEY`
- `NOTION_TOKEN`
- `NOTION_PAGE`

工作流每天自动运行，也可以在 Actions 页面手动选择普通同步或全量同步。全量同步产生的
JSON 备份会作为 workflow artifact 上传。

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

不要把 API Key、Notion Token 或 `.env` 提交到 Git。全量同步的 JSON 备份可能包含你的
书名、划线和笔记，也应作为私密数据保存。

## License

MIT
