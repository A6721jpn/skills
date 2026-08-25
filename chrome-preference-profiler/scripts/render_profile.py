#!/usr/bin/env python3
"""Render profile.md deterministically from a validated interest profile."""

from __future__ import annotations

import argparse
import html
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from validate_profile import load_json_strict, validate_profile


STATUS_LABELS = {"insufficient": "不足", "provisional": "暫定", "usable": "利用可能"}
APPROVAL_LABELS = {"draft": "未承認（ドラフト）", "approved": "承認済み"}
ATTENTION_LABELS = {"usable": "利用可能", "limited": "限定的", "unavailable": "推定不能"}
ENSEMBLE_LABELS = {"not-run": "未実施", "converged": "収束", "contested": "不一致あり"}
INTENT_LABELS = {"personal": "個人関心寄り", "professional": "業務文脈寄り", "mixed": "混合", "unknown": "不明"}
HORIZON_LABELS = {"durable": "継続", "emerging": "新興", "transient": "一時的", "uncertain": "不確実"}


def table_cell(value: Any) -> str:
    """Render user-controlled text as inert Markdown/HTML content."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = html.escape(text, quote=True)
    replacements = {
        "\\": "&#92;",
        "`": "&#96;",
        "*": "&#42;",
        "_": "&#95;",
        "[": "&#91;",
        "]": "&#93;",
        "(": "&#40;",
        ")": "&#41;",
        "|": "&#124;",
        "!": "&#33;",
        "~": "&#126;",
    }
    return "".join(replacements.get(character, character) for character in text)


def render_profile(data: dict[str, Any]) -> str:
    coverage = data["coverage"]
    approval = data["approval"]
    is_v2 = data["schema_version"] == "interest-profile/v2"
    requested_shortfall = max(0, coverage["requested_days"] - coverage["observed_days"])
    retention_text = "Chrome履歴の想定保持上限" if is_v2 else "Chromeの通常の履歴表示上限"
    lines = [
        "# ニュース嗜好プロファイル",
        "",
        f"生成日時: {table_cell(data['generated_at'])}",
        f"承認状態: {APPROVAL_LABELS[approval['status']]}",
        "",
        "## 取得範囲",
        "",
        f"- 指定期間: {table_cell(coverage['requested_start'])}〜{table_cell(coverage['requested_end'])}（約{coverage['requested_days']}日）",
        f"- 実取得期間: {table_cell(coverage['actual_start'])}〜{table_cell(coverage['actual_end'])}（{coverage['observed_days']}暦日）",
        f"- 処理件数: {coverage['processed_visits']:,}件（公開情報候補 {coverage['public_visits']:,}件、除外・低減 {coverage['excluded_or_downweighted_visits']:,}件）",
        f"- 取得上限: {coverage['history_query_limit']:,}件、上限到達: {'はい' if coverage['history_limit_hit'] else 'いいえ'}、結果打切り: {'はい' if coverage['result_truncated'] else 'いいえ'}",
        f"- 評価: {STATUS_LABELS[coverage['status']]}。指定より約{requested_shortfall}日短く、{retention_text}は{coverage['retention_limit_days']}日です。",
    ]

    if is_v2:
        inference = data["inference"]
        attention = inference["attention"]
        ensemble = inference["ensemble"]
        lines.extend(
            [
                "",
                "## 推定品質",
                "",
                f"- 固定分類で説明できた公開履歴: {inference['taxonomy_coverage_ratio']:.0%}（未分類 {inference['unmapped_public_visits']:,}件）",
                f"- 推定注意時間: {ATTENTION_LABELS[attention['status']]}、推定可能率 {attention['coverage_ratio']:.0%}、観測候補 {attention['observable_visits']:,}件",
                f"- 注意時間の扱い: 次の訪問までの間隔を1件最大{attention['per_visit_cap_minutes']:g}分、セッション間隔最大{attention['session_gap_minutes']:g}分で丸めた代理指標です。実測滞在時間ではありません。",
                f"- 信頼度校正: {inference['calibration']['status']}（上限 {inference['calibration']['confidence_cap']:.2f}）",
                f"- 集約レビュー: {ENSEMBLE_LABELS[ensemble['status']]}、{ensemble['review_count']}件・{ensemble['role_count']}役割、最大不一致 {ensemble['max_disagreement']:.2f}",
            ]
        )

    lines.extend(["", "## 推定ニュース分野", ""])
    if is_v2:
        lines.extend(["| 分野 | 重み | 確信度 | 文脈 | 時間軸 | ユーザー確認 |", "|---|---:|---:|---|---|---|"])
    else:
        lines.extend(["| 分野 | 重み | 確信度 | ユーザー確認 |", "|---|---:|---:|---|"])

    for topic in data["topics"]:
        confirmed = "確認済み" if topic["user_confirmed"] is True else "除外確認済み" if topic["user_confirmed"] is False else "未確認"
        if is_v2:
            lines.append(
                f"| {table_cell(topic['label'])} | {topic['weight']:.2f} | {topic['confidence']:.2f} | "
                f"{INTENT_LABELS[topic['intent']]} | {HORIZON_LABELS[topic['time_horizon']]} | {confirmed} |"
            )
        else:
            lines.append(f"| {table_cell(topic['label'])} | {topic['weight']:.2f} | {topic['confidence']:.2f} | {confirmed} |")

    lines.extend(["", "### 推定理由", ""])
    for topic in data["topics"]:
        lines.append(f"- {table_cell(topic['label'])}: {table_cell(topic['rationale'])}")

    if is_v2:
        lines.extend(["", "### 集約シグナル", ""])
        for topic in data["topics"]:
            attention = topic["attention"]
            horizon = topic["horizon"]
            intent_scores = topic["intent_scores"]
            lines.append(
                f"- {table_cell(topic['label'])}: 注意時間代理 {attention['estimated_minutes_capped']:.1f}分・推定可能率 {attention['coverage_ratio']:.0%}、"
                f"短期 {horizon['short_score']:.2f}／長期 {horizon['long_score']:.2f}、安定度 {horizon['stability']:.2f}、"
                f"一時性 {intent_scores['transient']:.2f}、業務文脈らしさ {intent_scores['work_like']:.2f}"
            )

    exclusions = data["exclusions"]
    lines.extend(["", "## 除外・優先度低下", ""])
    if exclusions["terms"]:
        lines.append("- 原則として扱わない一般カテゴリ: " + "、".join(table_cell(x) for x in exclusions["terms"]))
    else:
        lines.append("- 明示的な除外語はありません。")
    if exclusions["topic_ids"]:
        lines.append("- 除外トピックID: " + "、".join(table_cell(x) for x in exclusions["topic_ids"]))
    lines.append("- 認証、メール、私用・社内ワークスペース、決済、検索ナビゲーションは嗜好根拠から除外または大幅に低減しています。")

    defaults = data["digest_defaults"]
    lines.extend(
        [
            "",
            "## ニュース収集の既定値",
            "",
            f"- 対象期間: 過去{defaults['lookback_hours']}時間",
            f"- 最大件数: {defaults['max_items']}件",
            f"- 同一発行元ドメイン: 最大{defaults['max_per_domain']}件",
            f"- 言語順: {' → '.join(table_cell(language) for language in defaults['language_order'])}",
            "",
            "## プライバシー",
            "",
            "- 生の閲覧履歴、URL、ページタイトル、検索語、正確な閲覧時刻は保存していません。",
            "- ニュース検索語には閲覧履歴の原文をコピーせず、公開検索に適した固定の一般語だけを使用します。" if is_v2 else "- ニュース検索語には閲覧履歴の原文をコピーせず、公開検索に適した一般語だけを使用します。",
            "- センシティブ属性は推定しません。",
        ]
    )
    if is_v2:
        lines.append("- エージェントには集約済みプロファイルだけを渡し、生の履歴やページ別の注意時間は渡しません。")
    lines.extend(["", "## 確認", ""])
    if approval["status"] == "approved":
        lines.append(f"このプロファイルは明示承認済みです（{table_cell(approval['approved_at'])}）。")
    else:
        lines.append("このプロファイルはドラフトです。修正だけでは承認済みになりません。内容を確認し、ニュース収集に継続利用してよい場合は明示的に承認してください。")
    return "\n".join(lines) + "\n"


def write_text_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)


def paths_alias(left: Path, right: Path) -> bool:
    """Reject direct, resolved-symlink, and existing-hardlink source/output collisions."""
    if left.resolve() == right.resolve():
        return True
    if not left.exists() or not right.exists():
        return False
    try:
        return left.samefile(right)
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if output differs from the rendered profile")
    parser.add_argument("profile", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if paths_alias(args.profile, args.output):
            raise ValueError("render output must not alias the profile input")
        if args.profile.stat().st_size > 2_000_000:
            raise ValueError("profile exceeds the 2 MB safety limit")
        data = load_json_strict(args.profile)
        errors = validate_profile(data)
        if errors:
            raise ValueError("invalid profile: " + "; ".join(errors))
        rendered = render_profile(data)
        if args.check:
            current = args.output.read_text(encoding="utf-8")
            if current != rendered:
                raise ValueError("Markdown is not synchronized with profile JSON")
            print(f"SYNCHRONIZED: {args.output}")
        else:
            write_text_atomic(args.output, rendered)
            print(f"RENDERED: {args.output}")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
