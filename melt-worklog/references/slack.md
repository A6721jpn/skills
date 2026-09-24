# Melt Connect Slackを読む

対象日の本人投稿を起点に関連スレッドを読む。本人は `from:me` で特定し、表示名から推測しない。

1. `mcp__melt__slack_search` の実際のスキーマを確認する。現在は `query`, `count` (最大100), `page`, `sort` が使える。
2. 対象日Dの前日から翌々日まで広げて検索する。例：9/24なら `from:me after:2026-09-23 before:2026-09-26`。Slack検索側のタイムゾーン差を吸収し、取り込み側でSlackのtsをJSTの `[D 00:00,D+1 00:00)` に厳密に絞る。
3. `count:100, page:1, sort:"newest"` で読み、返された `pages` まで取得する。0件でも正常応答を保存する。失敗を0件扱いしない。大量で一度に読めない場合はページ取得を続けるか、未取得ページを明記する。
4. `to:me` でも同じ期間を検索する。これはSlack検索が返す受信・関係メッセージの範囲であり、あらゆるメンションを網羅する保証はない。メンションされたチャンネルやユーザー指定のチャンネルがあるときは補助検索・historyを追加する。
5. 実務に関係する本人投稿の `channel_id`, `thread_ts` (なければ `ts`) を使い `slack_thread` で文脈を読む。同じスレッドは1回。雑談・出欠・勤怠だけの投稿は日報の作業項目から除く。DMの文脈が不足する場合はそのDMの当日の `slack_history` を読む。
6. 結果のMCP textをJSONとして解釈し、改変せず次の包みで保存する。ツール結果の `isError` も確認する。

```json
{"query":"from:me after:2026-09-23 before:2026-09-26", "result":{"total":14,"page":1,"pages":1,"messages":[]}}
```

スレッドは `{"query":"thread:C_CHANNEL:親ts","result":[実際のメッセージ配列]}`。
historyは `{"query":"history:C_CHANNEL","result":{"messages":[実際の配列]}}` としてchannel_idがない各メッセージには実際に指定したチャンネルIDを付ける。取り込みに必要な包み以外の内容を作り直さない。

検索とスレッドで同一投稿の本文が違う場合、後で取得したスレッドの編集済み本文を優先する。`from:me` 結果にあった投稿は本人発言として保持する。それ以外は相手の成果を本人の成果にしない。

全ファイルを `report.py import-slack --input ...` で取り込む。`manifest.slack.status` と `missing_pages` を確認する。取得エラー・検索仕様の制約・スレッド応答に続きを示す情報がある場合は日報の不足として記す。

Melt Connectが不調なときは次の診断結果をユーザーへ示す。アップデートの案内があれば `update` の実行を案内する。別のAPI経路に切り替えない。

```powershell
& 'C:/Users/backo/AppData/Local/Programs/Python/Python313/python.exe' 'C:/Users/backo/.melt-connect/melt_connect.py' doctor
```
