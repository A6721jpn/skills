---
name: jp-llm-lint
description: Use when the user invokes $jp-llm-lint, or asks to polish / rewrite / make readable a Japanese answer, report, or summary before showing it. Sends the drafted Japanese text to the local JP-LLM-LINT service (Tailscale) and returns the rewritten text; falls back to the original when the service rejects or is unavailable.
---

# JP-LLM-LINT（日本語の最終出力レイヤー）

自分が書いた日本語の回答・作業報告を、ユーザーに見せる前に **読み手のために再構成**する（結論先出し、経緯の圧縮、冗長・翻訳調の解消）。意味・数値・条件・コード・URL は保持し、Guard が疑わしいと判断した場合は原文がそのまま返る（fail-safe）。

## 使い方

1. まず通常どおり日本語の回答本文を書き上げる（下書き）。コードブロック・数値・コマンド・パスはそのまま含めてよい
2. 下書き全文を標準入力で渡す：

   ```bash
   python "$CODEX_HOME/skills/jp-llm-lint/scripts/rewrite.py" <<'EOF'
   （下書き本文）
   EOF
   ```

   Windows PowerShell では一時ファイル経由：

   ```powershell
   Set-Content -Encoding utf8 $env:TEMP\draft.txt @'
   （下書き本文）
   '@
   python "$env:USERPROFILE\.codex\skills\jp-llm-lint\scripts\rewrite.py" --file $env:TEMP\draft.txt
   ```

3. **標準出力の本文をそのまま最終回答にする**。標準エラーの 1 行（`rewritten` / `fallback (...)` / `unavailable`）は判断材料であり、ユーザーには見せない
4. 終了コード 2（フォールバック）または 3（接続失敗）のときは原文が出力されるので、下書きをそのまま使う。**再試行や自前の修正はしない**（Guard の判断を尊重する）

## 対象と除外

- 対象：ユーザーへの日本語の説明・報告・要約（300 字以上が効果的。2,000 字超は自動で分割処理）
- 対象外：コードのみの回答、英語の回答、ユーザーが「原文のまま」「そのまま貼って」と指示した文章、機密情報を含む本文（サービスは同一 Tailscale 内のローカル PC だが、入出力はそのマシンのログに残る）

## 動作確認

```bash
python "$CODEX_HOME/skills/jp-llm-lint/scripts/rewrite.py" --health
```

`{"model": ..., "adapter": ..., "guard_mode": ...}` が返れば稼働中。接続先は環境変数 `JPLLMLINT_URL`（既定 `http://hub:8765`。MagicDNS が使えない場合は `http://100.91.209.1:8765`）。応答には 1000 字あたり 35〜40 秒かかる。

## 注意

- 出力は改善率約 4 割・意味変更約 1〜2 割（評価セット実測）の MVP 段階。数値・否定・条件が変わっていないか、最終回答を送る前に一読すること
- サービスが落ちている・遅いときは待たず、原文で回答する（スクリプトが自動でそうする）
