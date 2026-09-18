---
name: gemini-polish
description: Claude Code / Codex の日本語応答と .md/.txt 出力を Gemini (agy) で推敲するフック一式の導入・更新・削除。「gemini-polish を入れたい／直したい／外したい」と言われたときに使う。推敲そのものはフックが自動で行うため、文章を書くときに読む必要はない。
---

# gemini-polish

`gemini-polish.js` 1 ファイル（Node.js、依存パッケージなし）が Claude Code / Codex のフックとして動き、モデルが人間に見せる日本語を Gemini に書き直させる。仕組み・設定項目・除外規則は同ディレクトリの `README.md` にある。

## 前提

- Node.js 18 以上が `node` として PATH にある。
- Google Antigravity CLI が `agy` として PATH にあり、ログイン済み（`agy models` が一覧を返す）。
- Claude Code 2.1 以降、または hooks が有効な Codex（`codex features list | grep hooks`）。

## インストール

`install` はユーザー設定（`~/.claude/settings.json`、`~/.codex/hooks.json`）を書き換える。変更前のファイルは `*.gemini-polish.bak` として残るが、**実行前にユーザーの承認を得る**。

1. 前提を確認する: `node --version`、`agy --version && agy models`
2. 承認を得てから登録する: `node <置き場所>/gemini-polish.js install`（プロジェクト単位なら `install --project`）
3. 確認する: `node <置き場所>/gemini-polish.js status`、`... test`
4. Codex の場合、ユーザーに `/hooks` で `gemini-polish.js` の 3 エントリ（UserPromptSubmit / PostToolUse / Stop）を trust してもらう。この操作は LLM からは代行できない。
5. ユーザーに伝える: 日本語を含む `.md .txt .rst .adoc .mdx` は書込時に自動で推敲・上書きされ、元ファイルは `~/.gemini-polish/backups/` に残る。ログは `~/.gemini-polish/log.txt`。一時停止は `GEMINI_POLISH_DISABLE=1`。

## 更新・アンインストール

- 更新: 新しい `gemini-polish.js` に置き換えて `install` を再実行（古いエントリは自動削除、Codex は再 trust が必要）。
- アンインストール: `node <置き場所>/gemini-polish.js uninstall`（`--project` も同様）。`~/.gemini-polish/` は残る。

## 推敲対象から外すべきファイル

`CLAUDE.md` / `AGENTS.md` / `MEMORY.md` / `SKILL.md` と `.claude/` `.codex/` 配下は既定で対象外。スクリプトが生成し、他のツールが検証する Markdown（例: `chrome-preference-profiler` の `profile.md`）には、先頭に `<!-- gemini-polish: skip -->` を置く。

## 手動での使用

```bash
node <置き場所>/gemini-polish.js text --file draft.txt      # 推敲結果を stdout へ
node <置き場所>/gemini-polish.js file README.md docs/*.md   # その場で推敲・上書き
```
