# gemini-polish

Claude Code や Codex がユーザーに表示する日本語を、Google Antigravity CLI (`agy`) を非対話モードで起動して
Gemini 3.8 Flash に推敲させるフックです。依存関係は Node.js と `agy` のみです。

## 仕組み

| 対象 | フック | 動作 |
|---|---|---|
| ターミナルの応答 | `UserPromptSubmit` | 「最終応答は事前に `gemini-polish.js text` に通し、その出力をそのまま返せ」という指示をモデルに注入する（高速な経路。応答が二重に出力されない） |
| ターミナルの応答 | `Stop` | 最終応答に未推敲の日本語が残っている場合、Gemini で推敲したうえで `decision: block` により「この本文をそのまま出力せよ」と差し戻す（保険。元の応答と推敲後の双方が表示される） |
| ドキュメント | `PostToolUse` (Write / Edit / apply_patch / Bash …) | 作成・編集された `.md .txt .rst .adoc .mdx` に日本語が含まれていれば、Gemini で全文を推敲して上書きし、モデルに再読み込みを促す |

- コードブロック、インラインコード、URL、パス、frontmatter、HTML コメントは、プレースホルダーへ退避してから Gemini に渡すため変更されません。
- 推敲済みのテキストは `~/.gemini-polish/cache` に記録し、二重推敲や無限ループを防ぎます（`stop_hook_active` も参照します）。
- 上書き前のファイルは `~/.gemini-polish/backups/` に退避します。ログは `~/.gemini-polish/log.txt` に記録されます。
- `CLAUDE.md` / `AGENTS.md` / `MEMORY.md` および `.claude/` `.codex/` `.git/` `node_modules/` 配下はモデル向けのため対象外です。
- フックの仕様上、表示済みの応答をその場で書き換えることはできません（Claude Code、Codex ともに Stop フックでは「差し戻し」のみ可能なため）。そのため高速な経路（モデル自身が `text` を呼び出す）を主系統とし、Stop フックを保険として併用しています。

## セットアップ

```bash
node C:/llm-tools/gemini-polish/gemini-polish.js install          # ~/.claude/settings.json と ~/.codex/hooks.json に登録
node C:/llm-tools/gemini-polish/gemini-polish.js install --project # カレントプロジェクトの .claude/ .codex/ に登録
node C:/llm-tools/gemini-polish/gemini-polish.js test              # agy 経由で 1 文推敲してみる
node C:/llm-tools/gemini-polish/gemini-polish.js status
node C:/llm-tools/gemini-polish/gemini-polish.js uninstall
```

Codex は新規追加または変更されたフックを信頼するまで実行しません。Codex を開いて `/hooks` を実行し、
`gemini-polish.js` のエントリを trust してください（`codex exec` で試す場合は `--dangerously-bypass-hook-trust`）。

## 手動で使う

```bash
node gemini-polish.js text <<'EOF'      # stdin の日本語を推敲して stdout へ
...
EOF
node gemini-polish.js text --file draft.txt
node gemini-polish.js file README.md docs/*.md   # ファイルをその場で推敲・上書き
```

## 設定

`~/.gemini-polish/config.json`（環境変数が優先されます）:

| キー | 環境変数 | 既定 | 意味 |
|---|---|---|---|
| `model` | `GEMINI_POLISH_MODEL` | `gemini-3.8-flash-high` | `agy models` の ID。`-low` にすると数秒高速化 |
| `effort` | `GEMINI_POLISH_EFFORT` | (空) | `agy --effort low\|medium\|high` |
| `timeoutSec` | `GEMINI_POLISH_TIMEOUT` | 150 | agy の待機時間 |
| `minJaChars` | `GEMINI_POLISH_MIN_CHARS` | 20 | 日本語がこの文字数未満なら推敲しない |
| `docExts` | `GEMINI_POLISH_DOC_EXTS` | `.md,.markdown,.mdx,.txt,.rst,.adoc` | 推敲対象の拡張子 |
| `excludePattern` | – | (上記) | 対象外パスの正規表現 |
| `maxFileBytes` | – | 80000 | このサイズを超えるファイルは処理しない |
| `rewriteResponses` | `GEMINI_POLISH_RESPONSES` | true | Stop フックで応答を差し替える |
| `rewriteDocs` | `GEMINI_POLISH_DOCS` | true | ドキュメントを推敲する |
| `injectInstruction` | `GEMINI_POLISH_INJECT` | true | UserPromptSubmit で指示を注入する |
| `bashHeuristic` | `GEMINI_POLISH_BASH` | true | シェルコマンド文字列に含まれる直近で更新されたドキュメントも対象に含める |
| – | `GEMINI_POLISH_DISABLE=1` | – | 一時的に全機能を停止する |
| – | `GEMINI_POLISH_DEBUG=1` | – | フック入力をログに記録する |
