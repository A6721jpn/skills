---
name: gemini-polish
description: Claude Code / Codex が人間に見せる日本語（ターミナルの応答と .md/.txt などのドキュメント）を、Google Antigravity CLI (agy) を非対話モードで起動して Gemini 3.8 Flash (high) に書き直させるフック一式。「日本語の応答やドキュメントを自動で Gemini に推敲させたい」「gemini-polish をインストール／更新／アンインストールしたい」ときに使う。
---

# gemini-polish

Claude Code および Codex のフックとして動作し、モデルが提示する日本語をすべて Gemini に書き直させる。
実体は `gemini-polish.js` の 1 ファイルのみ（Node.js、依存パッケージなし）。詳細な仕組みや設定項目については、同ディレクトリの `README.md` を参照のこと。

## 前提

- Node.js 18 以上が `node` として PATH に通っていること。
- Google Antigravity CLI が `agy` として PATH に通っており、ログイン済みであること（`agy models` で一覧が返れば問題ない）。
- Claude Code は 2.1 以降、Codex は hooks 機能が有効（`codex features list | grep hooks` が `true`）であること。

## インストール手順（LLM 向け）

1. 本ディレクトリ（`gemini-polish/`）を任意の場所に配置する。既定の配置先は `C:\llm-tools\gemini-polish`（Windows）または `~/llm-tools/gemini-polish`。リポジトリごと clone した場合は、そのまま `skills/gemini-polish` を使用してよい。
2. 前提条件を確認する。

   ```bash
   node --version
   agy --version && agy models
   ```

3. フックを登録する。ユーザー設定（`~/.claude/settings.json` および `~/.codex/hooks.json`）に書き込まれる。既存の設定は保持され、変更前のファイルは `*.gemini-polish.bak` として同一の場所に残る。

   ```bash
   node <置き場所>/gemini-polish.js install
   ```

   プロジェクト単位で有効化したい場合は、対象プロジェクトのルートで `install --project` を実行する（`.claude/settings.json` および `.codex/hooks.json` に書き込まれる）。

4. 動作を確認する。

   ```bash
   node <置き場所>/gemini-polish.js status   # 登録状況、agy のバージョン、モデルを表示
   node <置き場所>/gemini-polish.js test     # 例文 1 つを agy 経由で推敲して表示
   ```

5. **Codex を使用する場合は、ユーザーに以下の対応を依頼する。** Codex は新規追加または変更されたフックを信頼するまで実行しない。Codex（CLI またはデスクトップ版）で `/hooks` を開き、`gemini-polish.js` を含む 3 つのエントリ（UserPromptSubmit / PostToolUse / Stop）を trust してもらう。この操作は LLM からは代行できない。

6. 確認後、ユーザーに以下の事項を伝える。
   - 応答は原則としてモデル自身が `gemini-polish.js text` を呼び出して推敲するため、1 回のみ表示される。呼び出しを忘れた場合は Stop フックが推敲文を差し戻すため、元の応答と推敲後の応答が両方表示される。
   - 日本語を含む `.md .txt .rst .adoc .mdx` を書き込むと自動で推敲・上書きされる。元のファイルは `~/.gemini-polish/backups/` に残る。
   - ログは `~/.gemini-polish/log.txt` に出力される。一時的に停止する場合は環境変数 `GEMINI_POLISH_DISABLE=1` を設定する。

## 更新・アンインストール

- 更新: 新しい `gemini-polish.js` に置き換えてから `install` を再実行する（古いエントリは自動的に削除される）。パスが変更された場合も同様。Codex 側では再度 `/hooks` による trust が必要となる。
- アンインストール: `node <置き場所>/gemini-polish.js uninstall` を実行する（`--project` も同様）。`~/.gemini-polish/` は残るため、不要であれば手動で削除する。

## 登録されるフック

| イベント | 役割 |
|---|---|
| `UserPromptSubmit` | 「最終応答は事前に `gemini-polish.js text` を通し、その出力をそのまま返却せよ」という指示を毎ターン注入する |
| `PostToolUse`（Write / Edit / apply_patch / Bash など） | 作成・編集されたドキュメントに日本語が含まれていれば Gemini で全文を推敲して上書きし、モデルに再読み込みを促す |
| `Stop` | 最終応答に未推敲の日本語が残っていれば推敲を行い、`decision: block` でその本文をそのまま出力するよう差し戻す |

モデルは `gemini-3.8-flash-high` に固定（`~/.gemini-polish/config.json` の `model` または環境変数 `GEMINI_POLISH_MODEL` で変更可能）。
コードブロック、インラインコード、URL、パス、frontmatter は推敲前にプレースホルダーへ退避されるため変更されない。

## 手動での使用

```bash
node <置き場所>/gemini-polish.js text <<'EOF'      # stdin の日本語を推敲して stdout へ
...
EOF
node <置き場所>/gemini-polish.js text --file draft.txt
node <置き場所>/gemini-polish.js file README.md docs/*.md   # ファイルをその場で推敲・上書き
```
