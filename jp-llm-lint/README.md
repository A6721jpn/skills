# jp-llm-lint（クライアント用スキル）

JP-LLM-LINT は、Codex の日本語回答を「読み手のために再構成」して返すローカルサービス（結論先出し・経緯の圧縮・冗長や翻訳調の解消。数値・コード・URL・条件は決定的 Guard が検査し、疑わしければ原文をそのまま返す）。このスキルは **クライアント側のエントリーポイント**だけを含む。サービス本体（モデル・LoRA・Guard）は 設定済みのサービス用PC（Tailscale内）で動いている。

## インストール（別 PC）

```powershell
# このリポジトリを clone 済みなら
Copy-Item -Recurse -Force .\jp-llm-lint $env:USERPROFILE\.codex\skills\jp-llm-lint
# 非公開設定に接続先を保存した後、Tailscale経由で動作確認
python $env:USERPROFILE\.codex\skills\jp-llm-lint\scripts\rewrite.py --health
```

macOS / Linux：`cp -r jp-llm-lint ~/.codex/skills/` の後、`python3 ~/.codex/skills/jp-llm-lint/scripts/rewrite.py --health`。

## 接続先

- `JPLLMLINT_URL`、または `$CODEX_HOME/private/jp-llm-lint.json` の `url` に接続先を設定する。CODEX_HOME未設定時は `~/.codex`。別の非公開ファイルは `JPLLMLINT_CONFIG` で指定する。環境変数のURLが優先される。未設定なら外部へ送信せず原文を返す。設定ファイルは公開リポジトリに入れない。
- 生成待ちは `JPLLMLINT_TIMEOUT`（秒、既定 180）、接続確認は `JPLLMLINT_PROBE`（秒、既定 3）。応答は 1000 字あたり 35〜40 秒
- **ネットワーク障害時の挙動**：まず 3 秒の `/health` 確認に失敗した時点で原文をそのまま出力（終了コード 3）。名前解決失敗・接続拒否・経路断のいずれも数秒以内にフォールバックし、回答は失われない

## 使い方

Codex で `$jp-llm-lint` と明示するか、「日本語の回答を読みやすくして」と頼む。Codex は回答の下書きを `scripts/rewrite.py` に渡し、返ってきた本文を最終回答にする。サービスが拒否（フォールバック）または停止していれば原文のまま返る（終了コード 2／3）。

## 注意

- MVP 段階（評価セット実測：改善 37.5%、意味変更 15%）。数値・否定・条件が変わっていないか最終回答を一読すること
- 入出力はサービス側のログに残る。機密を含む本文には使わない
