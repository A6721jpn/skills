# A6721jpn/skills

Codex / Claude Code で使うスキルとフックをまとめたリポジトリです。
各スキルの詳細な手順、参照資料、スクリプト、テストは、それぞれのディレクトリにある `SKILL.md` から確認できます。

## スキル一覧

| スキル | 概要 | 使う場面・注意点 |
|---|---|---|
| [chrome-preference-profiler](./chrome-preference-profiler) | ユーザーが明示的に許可したChromeの閲覧履歴から、確認可能でプライバシーに配慮したニュース関心プロファイルを作成・更新します。 | Chrome履歴から関心分野を整理するときに使用します。Cookie、パスワード、セッション、ブックマークなどは読み取りません。 |
| [cognitive-rhythm-writing](./cognitive-rhythm-writing) | 読者の認知モードを切り替えながら、説明文や記事に緩急と読み進める推進力を設計します。 | 情報量はあるのに平坦で読みにくい文章の診断・改善や、読み物として読ませる解説文の執筆に使用します。 |
| [fusion-upper-frame-annular-0p5](./fusion-upper-frame-annular-0p5) | Upper Frameの指定された環状領域を、局所法線方向の厚さ0.5 mmに修正する、固定済みFusion手順の準備・実行補助・検証を行います。 | 合格済みのBottom補正済みUpper Frame F3D専用です。別の厚さ、モデル、Bottom-to-Datum補正、一般的な面修復には使用しません。 |
| [fusion-upper-frame-bottom-datum-add](./fusion-upper-frame-bottom-datum-add) | Upper Frameに対する追加のみのBottom-to-Datum補正を準備・検証し、F3D/STEPの往復結果を確認します。 | 固定済みのその操作の再実行・監査専用です。環状厚さ補正や一般的な面修復には使用しません。 |
| [gemini-polish](./gemini-polish) | Claude Code / Codex が人間に見せる日本語（応答と .md/.txt などのドキュメント）を、Antigravity CLI (agy) 経由で Gemini 3.8 Flash に自動で推敲させるフック一式です。 | Node.js と agy が必要です。`node gemini-polish/gemini-polish.js install` でユーザー設定に登録し、Codex では `/hooks` で trust します。スキルというよりフックの導入・管理手順です。 |
| [html-report-pipeline](./html-report-pipeline) | 根拠に基づく文章、視覚的な説明、意味的HTML、成果物のサニタイズ、構造・ブラウザQAをつないで、単独で読めるHTMLレポートを作成します。 | 技術報告、設計レビュー、調査概要、意思決定メモなど、納品用HTMLが必要なときに使用します。 |
| [japanese-tech-writing](./japanese-tech-writing) | 日本語の技術文書・書籍原稿について、構成、論証の厳密さ、用語、視点、読み手の負荷、冗長さを整える文章規範です。 | 日本語で技術書の章、記事、解説文を書くときや、既存原稿を推敲・リライトするときに使用します。 |
| [maintaining-repo-context-docs](./maintaining-repo-context-docs) | 開発の進行で古くなったリポジトリ説明、ADR、マイルストーン、所有関係、手順書などを監査・更新します。 | 既存のLLM向けドキュメント基盤を保ったまま、実装・テストとのずれを直すときに使用します。 |
| [personalized-news-collector](./personalized-news-collector) | 承認済みの関心プロファイルをもとに、最新ニュースをWebで検証し、出典付きの日本語ダイジェストとして整理します。 | ニュース収集時の重複排除と話題の多様性を扱います。Chrome履歴を直接読んだり、プロファイルを自動生成したりはしません。 |
| [rams-gui-design](./rams-gui-design) | ディーター・ラムス／ブラウンに通じる、抑制された機能主義的なGUIを設計・実装・リファクタリング・監査します。 | ユーザーまたはリポジトリがラムス風／機能主義のUI方向性を明示的に求めたときのみ使用します。一般的なGUI作業には適用しません。 |
| [repo-context-docs](./repo-context-docs) | 初めて読むコーディングエージェントが、リポジトリの目的、制約、所有関係、現状、意思決定を把握できるドキュメント基盤を作ります。 | オンボーディング、アーキテクチャ引き継ぎ、ADR作成、コンテキスト削減、リポジトリ文書の評価に使用します。 |
| [semantic-generation](./semantic-generation) | 用語や名前を先に決めず、指示対象と役割の対応表を先に固定してから、設計文書・調査報告・命名・推論順序を組み立てます。 | 対象の取り違えや、その場限りの造語が設計・文章・コードへ波及しそうなときに使用します。 |
| [show-me](./show-me) | 論理、処理フロー、UI構造、ファイル責務などを、最小限で効果的な図、擬似コード、ツリー、HTMLとして視覚化します。 | 文章だけでは関係が把握しにくいテーマを、短く分かりやすく説明するときに使用します。 |
| [web-research-orchestrator](./web-research-orchestrator) | Web調査の範囲確認、情報源の評価、出典付きレポート、図表、動画・ポッドキャストなどの非テキスト情報を含む調査を構成します。 | 最新情報の調査、複数ソースの比較、可視化付きの静的HTMLレポート作成に使用します。広いテーマは先に調査範囲を確認します。 |

## 使い分けの目安

- リポジトリの説明を新しく作る場合は `repo-context-docs`、既存の説明を現状に合わせて更新する場合は `maintaining-repo-context-docs` を使います。
- 日本語の文章品質を整える場合は `japanese-tech-writing`、文章の読み進めるリズムまで設計する場合は `cognitive-rhythm-writing` を使います。
- ニュース関心のプロファイル作成は `chrome-preference-profiler`、そのプロファイルを使ったニュース収集は `personalized-news-collector` に分けます。
- `fusion-upper-frame-annular-0p5` と `fusion-upper-frame-bottom-datum-add` は、対象モデルと操作が固定された検証済み手順です。一般用途のFusion修復スキルではありません。

更新日: 2026-09-14
