#!/usr/bin/env python3
"""Heuristic source audit for Rams-informed GUI work.

The audit flags patterns that commonly undermine functional restraint,
state clarity, semantic controls, or motion discipline. It is deliberately
conservative: findings require human review and a clean report is not a
quality or accessibility certification.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

TEXT_EXTENSIONS = {
    ".astro",
    ".cjs",
    ".cs",
    ".cts",
    ".css",
    ".dart",
    ".htm",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".less",
    ".mdx",
    ".mjs",
    ".mts",
    ".qml",
    ".razor",
    ".sass",
    ".scss",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
    ".xaml",
    ".xhtml",
    ".xml",
}

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "out",
    "coverage",
    "target",
}

MAX_FILE_BYTES = 2_000_000
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}

HEX_COLOR_RE = re.compile(r"(?<![\w-])#[0-9a-fA-F]{3,8}(?![\w-])")
CSS_COLOR_FUNCTION_RE = re.compile(
    r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)\([^;{}]+\)", re.I
)
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}{]+)", re.I)


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    line: int
    message: str
    excerpt: str = ""


@dataclass
class FileRecord:
    path: Path
    text: str
    lines: list[str]


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Flag common visual, motion, and semantic anti-patterns in UI source files. "
            "The result is a review aid, not certification."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to scan recursively.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero for any finding. By default, only high/critical findings fail.",
    )
    parser.add_argument(
        "--max-files",
        type=positive_int,
        default=5000,
        help="Safety limit for scanned files (default: 5000).",
    )
    return parser.parse_args(argv)


def is_excluded(path: Path) -> bool:
    return any(part.casefold() in EXCLUDED_DIRS for part in path.parts)


def iter_source_files(paths: Iterable[Path], max_files: int) -> Iterable[Path]:
    seen: set[Path] = set()
    count = 0

    for supplied in paths:
        path = supplied.expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        candidates: Iterable[Path]
        if path.is_file():
            candidates = (path,)
        else:
            candidates = path.rglob("*")

        for candidate in candidates:
            if not candidate.is_file() or is_excluded(candidate):
                continue
            if candidate.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            count += 1
            if count > max_files:
                raise RuntimeError(
                    f"Scan exceeds --max-files={max_files}; narrow the paths or raise the limit."
                )
            yield candidate


def read_record(path: Path) -> FileRecord | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return FileRecord(path=path, text=text, lines=text.splitlines())


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def clean_excerpt(line: str, width: int = 180) -> str:
    compact = " ".join(line.strip().split())
    return compact if len(compact) <= width else compact[: width - 3] + "..."


def full_line_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("//", "/*", "*", "<!--"))


def add_line_finding(
    findings: list[Finding],
    record: FileRecord,
    index: int,
    severity: str,
    rule: str,
    message: str,
) -> None:
    findings.append(
        Finding(
            severity=severity,
            rule=rule,
            path=display_path(record.path),
            line=index + 1,
            message=message,
            excerpt=clean_excerpt(record.lines[index]),
        )
    )


def scan_lines(record: FileRecord, findings: list[Finding]) -> None:
    rules: list[tuple[re.Pattern[str], str, str, str]] = [
        (
            re.compile(r"(?:-webkit-)?backdrop-filter\s*:\s*[^;]*(?:blur|saturate)", re.I),
            "medium",
            "visual.glass-effect",
            "Backdrop filtering usually creates decorative glass; retain only with a functional rationale.",
        ),
        (
            re.compile(r"\b(?:linear|radial|conic|repeating-linear|repeating-radial)-gradient\s*\(", re.I),
            "medium",
            "visual.decorative-gradient",
            "Review the gradient: Rams-informed task UI defaults to flat, semantic color fields.",
        ),
        (
            re.compile(r"\btext-shadow\s*:\s*(?!none\b)", re.I),
            "medium",
            "visual.text-shadow",
            "Text shadow generally reduces typographic honesty and precision.",
        ),
        (
            re.compile(r"(?<!backdrop-)\bfilter\s*:\s*[^;]*(?:blur|drop-shadow)\s*\(", re.I),
            "medium",
            "visual.blur-or-glow",
            "Blur or drop-shadow effects need a functional, state-related justification.",
        ),
        (
            re.compile(r"\btransition(?:-property)?\s*:\s*all\b", re.I),
            "medium",
            "motion.transition-all",
            "Animate named properties only; transition-all can create accidental motion and performance cost.",
        ),
        (
            re.compile(r"\banimation(?:-iteration-count)?\s*:\s*[^;]*(?:infinite|\binfinite\b)", re.I),
            "medium",
            "motion.infinite",
            "Continuous animation is normally visual noise in task-oriented interfaces.",
        ),
        (
            re.compile(r"\b(?:outline\s*:\s*(?:0|none)|outline-width\s*:\s*0)(?:\s*!important)?", re.I),
            "high",
            "accessibility.focus-outline-removed",
            "A focus outline is removed; confirm an equally visible :focus-visible replacement exists.",
        ),
        (
            re.compile(r"\btransform\s*:\s*[^;]*scale\(\s*(1\.(?:0[4-9]|[1-9]\d)|[2-9])", re.I),
            "low",
            "motion.hover-scale",
            "Large scale feedback can feel promotional or unstable; prefer tonal, border, or small positional feedback.",
        ),
        (
            re.compile(r"\b(?:border-radius|cornerRadius)\s*[:=]\s*(?:999\d*px|999\d*rem|50%|\.5\s*\*\s*[^;,)]+)", re.I),
            "low",
            "geometry.generic-pill",
            "Confirm that fully rounded geometry expresses status, selection, a switch, or another real semantic role.",
        ),
        (
            re.compile(r"\b(?:border-radius|cornerRadius)\s*[:=]\s*(?:1[6-9]|[2-9]\d|(?!999)\d{3,})px", re.I),
            "low",
            "geometry.large-radius",
            "Large radii should be reserved for touch comfort or a specific semantic role, not used as a default container style.",
        ),
        (
            re.compile(r"\bfont-size\s*:\s*(?:[4-9](?:\.\d+)?rem|(?:6[4-9]|[7-9]\d|\d{3,})px)", re.I),
            "low",
            "typography.oversized-display-type",
            "Very large type can overpower task content; confirm that this is presentation content rather than application chrome.",
        ),
        (
            re.compile(r"\b(?:box-shadow|shadow)\s*:\s*[^;]*(?:0\s+0\s+(?:[1-9]\d|\d{3,})px|#[0-9a-f]{3,8}|rgba?\([^)]*,\s*(?:0\.[3-9]|1)\s*\))", re.I),
            "low",
            "visual.prominent-shadow",
            "Prominent or colored shadow needs to communicate temporary elevation or manipulation, not decoration.",
        ),
    ]

    for index, line in enumerate(record.lines):
        if full_line_comment(line):
            continue
        for pattern, severity, rule, message in rules:
            if pattern.search(line):
                add_line_finding(findings, record, index, severity, rule, message)

    # JSX/HTML-like semantic checks, evaluated per opening tag.
    for match in re.finditer(r"<(div|span)\b([^>]*)>", record.text, re.I | re.S):
        attrs = match.group(2)
        if re.search(r"\bon(?:click|tap|press)\s*=", attrs, re.I):
            line_no = record.text.count("\n", 0, match.start()) + 1
            findings.append(
                Finding(
                    severity="high",
                    rule="semantics.clickable-generic-element",
                    path=display_path(record.path),
                    line=line_no,
                    message="Use a native button or link unless a custom composite widget is genuinely required.",
                    excerpt=clean_excerpt(match.group(0)),
                )
            )

    for match in re.finditer(r"<img\b([^>]*)>", record.text, re.I | re.S):
        attrs = match.group(1)
        if not re.search(r"\balt\s*=", attrs, re.I):
            line_no = record.text.count("\n", 0, match.start()) + 1
            findings.append(
                Finding(
                    severity="high",
                    rule="semantics.image-without-alt",
                    path=display_path(record.path),
                    line=line_no,
                    message="Add an appropriate alt attribute; use alt=\"\" for a truly decorative image.",
                    excerpt=clean_excerpt(match.group(0)),
                )
            )

    for match in re.finditer(r"<button\b([^>]*)>(.*?)</button\s*>", record.text, re.I | re.S):
        attrs, content = match.group(1), match.group(2)
        textual_content = re.sub(r"<[^>]+>", " ", content)
        # A JSX/template expression such as {label} or {t("save")} usually
        # renders visible text; static analysis cannot prove otherwise.
        has_expression_child = bool(re.search(r"\{[^{}]*\}", textual_content))
        textual_content = re.sub(r"\{[^{}]*\}", " ", textual_content).strip()
        has_accessible_name = re.search(r"\b(?:aria-label|aria-labelledby)\s*=", attrs, re.I)
        if not textual_content and not has_accessible_name and not has_expression_child:
            line_no = record.text.count("\n", 0, match.start()) + 1
            has_title_only = re.search(r"\btitle\s*=", attrs, re.I)
            message = (
                "A title tooltip does not reliably replace a programmatic accessible name; add visible text, aria-label, or aria-labelledby."
                if has_title_only
                else "This button appears to have no persistent or programmatic accessible name."
            )
            findings.append(
                Finding(
                    severity="high",
                    rule="semantics.unnamed-button",
                    path=display_path(record.path),
                    line=line_no,
                    message=message,
                    excerpt=clean_excerpt(match.group(0)),
                )
            )


def normalized_font_family(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip('"\'' )).lower()


def scan_project(records: Sequence[FileRecord], findings: list[Finding]) -> None:
    all_text = "\n".join(record.text for record in records)

    has_motion = bool(
        re.search(
            r"\b(?:animation(?:-name)?\s*:|@keyframes\b|transition(?:-property)?\s*:)",
            all_text,
            re.I,
        )
    )
    has_reduced_motion = "prefers-reduced-motion" in all_text or "accessibilityReduceMotion" in all_text
    if has_motion and not has_reduced_motion:
        findings.append(
            Finding(
                severity="high",
                rule="motion.no-reduced-motion-path",
                path="<project>",
                line=0,
                message="Motion was detected, but no reduced-motion handling was found in the scanned paths.",
            )
        )

    removes_outline = bool(
        re.search(r"\boutline\s*:\s*(?:0|none)\b|outline-width\s*:\s*0\b", all_text, re.I)
    )
    has_focus_replacement = bool(
        re.search(r":focus-visible|focusVisible|focused\s*\?", all_text, re.I)
    )
    if removes_outline and has_focus_replacement:
        # A visible replacement exists; per-line outline findings are advisory only.
        for i, finding in enumerate(findings):
            if finding.rule == "accessibility.focus-outline-removed":
                findings[i] = Finding(
                    severity="medium",
                    rule=finding.rule,
                    path=finding.path,
                    line=finding.line,
                    message="A focus outline is removed; a :focus-visible replacement was found elsewhere, so confirm it covers this selector.",
                    excerpt=finding.excerpt,
                )
    if removes_outline and not has_focus_replacement:
        findings.append(
            Finding(
                severity="critical",
                rule="accessibility.no-visible-focus-replacement",
                path="<project>",
                line=0,
                message="Focus outlines are removed and no visible focus replacement was found in the scanned paths.",
            )
        )

    colors: set[str] = set()
    for record in records:
        colors.update(value.lower() for value in HEX_COLOR_RE.findall(record.text))
        colors.update(
            re.sub(r"\s+", "", value.lower()) for value in CSS_COLOR_FUNCTION_RE.findall(record.text)
        )
    if len(colors) > 32:
        findings.append(
            Finding(
                severity="medium",
                rule="tokens.excess-raw-colors",
                path="<project>",
                line=0,
                message=(
                    f"Found {len(colors)} distinct raw color literals. Consolidate values into a small semantic token set "
                    "or document why the feature requires this many data/brand colors."
                ),
            )
        )

    font_families: set[str] = set()
    for record in records:
        for match in FONT_FAMILY_RE.finditer(record.text):
            font_families.add(normalized_font_family(match.group(1)))
    if len(font_families) > 4:
        findings.append(
            Finding(
                severity="medium",
                rule="typography.excess-font-stacks",
                path="<project>",
                line=0,
                message=(
                    f"Found {len(font_families)} distinct font-family declarations. "
                    "Rationalize them into UI, data/code, and justified brand roles."
                ),
            )
        )


def deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    unique = {
        (f.severity, f.rule, f.path, f.line, f.message, f.excerpt): f for f in findings
    }
    return sorted(
        unique.values(),
        key=lambda f: (-SEVERITY_RANK[f.severity], f.path, f.line, f.rule),
    )


def output_text(findings: Sequence[Finding], scanned: int, skipped: int) -> None:
    print("Rams UI source audit")
    print(f"Scanned: {scanned} file(s); skipped unreadable/oversized: {skipped}")

    if not findings:
        print("No heuristic findings.")
        print("This does not certify visual quality, behavior, or accessibility.")
        return

    counts = Counter(f.severity for f in findings)
    count_text = ", ".join(
        f"{severity}={counts.get(severity, 0)}"
        for severity in ("critical", "high", "medium", "low")
    )
    print(f"Findings: {len(findings)} ({count_text})")
    print()

    for finding in findings:
        location = finding.path if finding.line <= 0 else f"{finding.path}:{finding.line}"
        print(f"[{finding.severity.upper()}] {finding.rule} - {location}")
        print(f"  {finding.message}")
        if finding.excerpt:
            print(f"  > {finding.excerpt}")
        print()

    print("Review findings in context. A clean report is not certification.")


def output_json(findings: Sequence[Finding], scanned: int, skipped: int) -> None:
    counts = Counter(f.severity for f in findings)
    payload = {
        "tool": "rams_ui_audit",
        "scanned_files": scanned,
        "skipped_files": skipped,
        "summary": {
            "total": len(findings),
            "critical": counts.get("critical", 0),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "low": counts.get("low", 0),
        },
        "findings": [asdict(finding) for finding in findings],
        "certification": False,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    # Console encodings such as cp932 cannot represent every character in
    # findings or excerpts; never let output encoding abort the audit.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    try:
        source_files = list(iter_source_files(args.paths, args.max_files))
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    records: list[FileRecord] = []
    skipped = 0
    for path in source_files:
        record = read_record(path)
        if record is None:
            skipped += 1
        else:
            records.append(record)

    findings: list[Finding] = []
    for record in records:
        scan_lines(record, findings)
    scan_project(records, findings)
    findings = deduplicate(findings)

    if args.format == "json":
        output_json(findings, len(records), skipped)
    else:
        output_text(findings, len(records), skipped)

    if args.strict:
        return 1 if findings else 0
    return 1 if any(SEVERITY_RANK[f.severity] >= SEVERITY_RANK["high"] for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
