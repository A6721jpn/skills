# A6721jpn/skills

Codex / Claude Code で使うスキルとフックをまとめたリポジトリです。
各スキルの詳細な手順、参照資料、スクリプト、テストは、それぞれのディレクトリにある `SKILL.md` から確認できます。

## スキル一覧

| スキル | 概要 | 使う場面・注意点 |
|---|---|---|
| [chrome-preference-profiler](./chrome-preference-profiler) | ユーザーが明示的に許可したChromeの閲覧履歴から、確認可能でプライバシーに配慮したニュース関心プロファイルを作成・更新します。 | Chrome履歴から関心分野を整理するときに使用します。Cookie、パスワード、セッション、ブックマークなどは読み取りません。 |
| [cognitive-rhythm-writing](./cognitive-rhythm-writing) | 説明的な文章に、認知モードの切替と未回収の緊張による緩急を設計する規範です。 | 読み物として読ませたい章・記事・解説文を書くとき、または平坦な文章を診断・修正するときに使用します。仕様書・手順書には使いません。japanese-tech-writing と併用し、衝突時はこちらが優先します。 |
| [fusion-upper-frame-annular-0p5](./fusion-upper-frame-annular-0p5) | Upper Frameの指定された環状領域を、局所法線方向の厚さ0.5 mmに修正する、固定済みFusion手順の準備・実行補助・検証を行います。 | 合格済みのBottom補正済みUpper Frame F3D専用です。別の厚さ、モデル、Bottom-to-Datum補正、一般的な面修復には使用しません。 |
| [fusion-upper-frame-bottom-datum-add](./fusion-upper-frame-bottom-datum-add) | Upper Frameに対する追加のみのBottom-to-Datum補正を準備・検証し、F3D/STEPの往復結果を確認します。 | 固定済みのその操作の再実行・監査専用です。環状厚さ補正や一般的な面修復には使用しません。 |
| [gemini-polish](./gemini-polish) | Claude Code / Codex の日本語応答と .md/.txt 出力を Gemini (agy) で推敲するフック一式を導入・更新・削除します。 | gemini-polish を入れたい／直したい／外したいときに使用します。`SKILL.md` と、先頭に `gemini-polish: skip` を持つ生成物は推敲しません。 |
| [html-report-pipeline](./html-report-pipeline) | 出典付きの根拠、最小限の図、検証済みマークアップを備えた単一ファイルのHTMLレポートを作成・改訂します。 | 成果物が1つのHTMLレポートファイルのときに使用します。MarkdownやChat回答には使いません。同じskillsディレクトリに technical-report-authoring / pink-elephant-guard / sanitize-artifacts / html が必要です（無い段階は省略して未検証と報告します）。 |
| [japanese-tech-writing](./japanese-tech-writing) | 日本語の技術文書・書籍原稿について、構成、論証の厳密さ、用語、視点、読み手の負荷、冗長さを整える文章規範です。 | 日本語で技術書の章、記事、解説文を書くときや、既存原稿を推敲・リライトするときに使用します。 |
| [maintaining-repo-context-docs](./maintaining-repo-context-docs) | 開発が進んで古くなったエージェント向けドキュメントを監査・更新します。 | そうしたドキュメントが既にあり、古くなったり矛盾したりしているときに使用します。ゼロから作る場合は repo-context-docs を使います。 |
| [personalized-news-collector](./personalized-news-collector) | 承認済みの関心プロファイルをもとに、最新ニュースをWebで検証し、出典付きの日本語ダイジェストとして整理します。 | ニュース収集時の重複排除と話題の多様性を扱います。Chrome履歴を直接読んだり、プロファイルを自動生成したりはしません。 |
| [rams-gui-design](./rams-gui-design) | ディーター・ラムス／ブラウンに通じる、抑制された機能主義的なGUIを設計・実装・リファクタリング・監査します。 | ユーザーまたはリポジトリがラムス風／機能主義のUI方向性を明示的に求めたときのみ使用します。一般的なGUI作業には適用しません。 |
| [repo-context-docs](./repo-context-docs) | エージェント向けドキュメントの骨格（読み方ガイド、アーキテクチャ概要、ADR、マイルストーン、runbook）をまだ持たないリポジトリに新規作成します。 | リポジトリをコーディングエージェントが読めるようにしたいときに使用します。既存ドキュメントの更新は maintaining-repo-context-docs を使います。 |
| [semantic-generation](./semantic-generation) | 設計文書・調査報告・対策案・命名を書く前に、語より先に指示対象と役割を対応表で固定します。 | 新しい概念や名前を導入する文書を書くときに使用します。引用、機械的な編集、既存名の再利用、定型出力には使いません。 |
| [show-me](./show-me) | 現在の話題を、最小限の見取り図（擬似コード、呼び出しツリー、ファイルツリー、diff、Mermaid、単一HTMLページ）で視覚的に説明します。 | 「見せて」「図にして」と言われたとき、または文章だけでは伝わらないときに使用します。 |
| [web-research-orchestrator](./web-research-orchestrator) | Web調査を、範囲確認・出典収集・相互検証・図表・推敲を経て、出典付きの静的HTMLレポートにまとめます。 | 現在のWeb情報を調査・比較し、出典付きでまとめてほしいときに使用します。単一の事実確認には使いません。 |

## 使い分けの目安

- リポジトリの説明を新しく作る場合は `repo-context-docs`、既存の説明を現状に合わせて更新する場合は `maintaining-repo-context-docs` を使います。
- 日本語の文章品質を整える場合は `japanese-tech-writing`、文章の読み進めるリズムまで設計する場合は `cognitive-rhythm-writing` を使います。
- ニュース関心のプロファイル作成は `chrome-preference-profiler`、そのプロファイルを使ったニュース収集は `personalized-news-collector` に分けます。
- `fusion-upper-frame-annular-0p5` と `fusion-upper-frame-bottom-datum-add` は、対象モデルと操作が固定された検証済み手順です。一般用途のFusion修復スキルではありません。
## 補足

- `fusion-upper-frame-annular-0p5` と `fusion-upper-frame-bottom-datum-add` は、特定のプロジェクト（Upper Frame の F3D、SHA-256 固定）専用の再現用コントローラです。汎用スキルではなく、fail-closed な CAD 操作スキルの実装例として公開しています。
- Windows で `personalized-news-collector` や `fusion-*` のテスト・実行が `FileNotFoundError` / `WinError 206` で失敗する場合は、パス長が 260 文字を超えています。長いパスを有効化（`LongPathsEnabled`）するか、リポジトリやデータルートを短いパス（例: `C:\skills`）に置いてください。

更新日: 2026-09-18
