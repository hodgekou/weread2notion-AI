---
layout: guide
lang: ja
title: 微信読書から Notion への同期ガイド
description: 微信読書の本棚、読書の進捗、ハイライト、感想を Notion に同期します。章ごとにメモを読み返し、グラフで読書の記録を振り返れます。
---

# 微信読書から Notion への同期ガイド

## 同期するデータ

微信読書の現在の本棚（`/shelf/sync`）から書籍を取り込みます。ハイライトと感想は各書籍ページに章ごとにまとまります。著者やカテゴリ別に本を探したり、日・週・月・年単位の読書統計を Notion のグラフで確認したりできます。書籍ごとの日次記録には累計読書時間、その日の増加分、進捗、読書状態、現在の章が含まれます。

## 初回の設定

1. [Notion テンプレート](https://app.notion.com/p/wph/Template-3a329affe5af800b8581f98b71e948fb)を **Duplicate（複製）** し、自分のワークスペースにできた最上位ページの URL を控えます。
2. 同じワークスペースで [Notion インテグレーション](https://www.notion.so/profile/integrations)を作成します。**Read content**、**Insert content**、**Update content** を有効にして内部インテグレーションのシークレットをコピーします。複製した最上位ページの **••• → Connections** から接続すると、配下のデータベースにアクセスできます。
3. [このリポジトリ](https://github.com/hodgekou/weread2notion-AI)を **Fork** します。自分のフォークの **Settings → Secrets and variables → Actions → New repository secret** で、下表の3件を登録します。
4. 自分のフォークで **Actions → weread sync → Run workflow** を開きます。初回は `full` のチェックを外して実行します。**Sync** ジョブが完了したら **Summary** の件数を確認し、Notion を再読み込みします。
5. 自動実行は毎日 **日本時間 05:00**（UTC 20:00、北京時間 04:00）です。時刻を変更するにはフォークの既定ブランチで [weread.yml](https://github.com/hodgekou/weread2notion-AI/blob/main/.github/workflows/weread.yml) の cron 式を編集します。

| シークレット名 | 値 |
| --- | --- |
| `WEREAD_API_KEY` | [微信読書アシスタント](https://weread.qq.com/r/weread-skills)から取得した Gateway API キー |
| `NOTION_TOKEN` | 複製先に接続したインテグレーションのシークレット |
| `NOTION_PAGE` | 複製先ページの完全な URL、またはページ名の末尾に32文字のページ ID を付けたもの |

## データの更新と削除

既定の設定では、本棚から削除した本のページと同期済みのメモは、次の同期が成功したときに Notion のゴミ箱に移ります。過去の日次記録は残ります。書籍のプロパティ、統計、自動生成された本文、システム設定は同期のたびに更新される場合があります。自分の文章は自動生成領域の外に書いてください。ホームのレイアウトやビュー、絞り込み、並べ替え、グラフは自由に編集できます。

読了の判定には微信読書で手動で付けた読了マーク（`finishReading=1`）を使います。読書記録があり、読了マークのない本は「読書中」になります。データベースの全行をバックアップして再構築したい場合は `full` を選びます。作成された JSON バックアップは Actions の成果物から取得できます。書籍詳細の取得時に HTTP 499 などの一時エラーが起きると、その本の既存データを保持して他の本を処理します。対象の本は Summary に表示され、次回の同期で再試行されます。

## Notion で変更できる設定

同期時に「设置」データベースの「同步设置」を読み込みます。ページがない場合は既定値で作成します。下表の項目名はテンプレート上の表記です。

| 項目名 | 型・既定値 | 用途 |
| --- | --- | --- |
| 阅读完成进度强制改为100% | Checkbox・オフ | 読了した本の進捗を Notion 上で 100% と表示 |
| 只同步我的书架书籍 | Checkbox・オン | 本棚から削除した本の同期済みコンテンツをゴミ箱へ移動 |
| 同步划线和笔记 | Checkbox・オン | ハイライトと感想を章ごとに書き込み |
| 保存阅读快照 | Checkbox・オン | 本ごとの日次記録を保存 |
| 阅读统计起始年份 | Number・2023 | 読書統計の開始年 |

設定値には Notion の Checkbox または Number を使います。保存した値は次回も引き継がれます。システム管理用の `同步配置版本（不可删除）` はそのまま残してください。

## ローカルで実行する

Python 3.10 以降が必要です。リポジトリのルートで次を実行し、上表の3項目を手元の `.env` に設定します。

```sh
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

任意で `START_YEAR`（既定値 `2023`）、`BACKUP_DIR`（既定値 `backups`）、`NOTION_VERSION`、`NOTION_REQUEST_INTERVAL` を設定できます。

```sh
weread2notion check                     # テンプレートの構成を確認
weread2notion sync --dry-run            # 微信読書のデータだけで同期予定を確認
weread2notion sync                      # 差分同期
weread2notion sync --full               # バックアップと全行の再構築
weread2notion export --format json --output weread-export
weread2notion export --format markdown --output weread-export
```

エクスポートは Notion に接続せず、手元に `manifest.json` を生成します。Markdown 形式では `books/` に各書籍の概要、ハイライト、感想も保存します。出力には個人の読書記録が含まれます。

## よくある質問

- **Could not find block with ID が出る** — 複製先の URL、最上位ページとの接続、トークンの発行元、ワークスペースが一致しているか確認します。
- **「全部」ビューが空、または「无年」と表示される** — 最新のテンプレートと同期結果を確認します。年は読了日・読書日から取得します。「全部」ビューに空の年フィルターがあれば外します。
- **定期実行されない** — 自分のフォークで Actions が有効で、既定ブランチにワークフローがあることを確認します。開始時刻は前後することがあります。
- **読書時間が「还未阅读」のまま** — 差分同期を再実行して微信読書の累計時間を取得します。
- **フォークを更新したい** — リリースノートで変更点を確認し、**Sync fork** で上流の main を取り込んでから同期します。

不具合を報告する際は、期待する結果、再現手順、機密情報を除いたログ、書籍 ID、実行モードを添えてください。キー、トークン、Cookie、個人のメモ、`.env` の内容は公開しないでください。[GitHub Issues](https://github.com/hodgekou/weread2notion-AI/issues/new/choose)

[技術資料（中国語）](TECHNICAL.md) · [v1.0.0 リリースノート（中国語）](RELEASE_NOTES_v1.0.0.md)

コード、ドキュメント、Notion テンプレートの調整は OpenAI ChatGPT（Codex、GPT-5 シリーズ）が生成しました。[MIT ライセンス](https://github.com/hodgekou/weread2notion-AI/blob/main/LICENSE)
