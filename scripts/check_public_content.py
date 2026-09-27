#!/usr/bin/env python3
"""Reject private workstation details and generated logs before publishing skills.

This is a focused publication check, not a complete secret or PII detector.
Diagnostics contain locations and categories, never matched private values.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def private_terms(path=None):
    supplied = path or os.environ.get('SKILLS_PRIVACY_DENYLIST')
    home = Path(os.environ['CODEX_HOME']) if os.environ.get('CODEX_HOME') else Path.home() / '.codex'
    source = Path(supplied).expanduser() if supplied else home / 'private/public-skills-denylist.json'
    if not source.exists() and not supplied:
        return []
    data = json.loads(source.read_text(encoding='utf-8-sig'))
    if not isinstance(data, list) or any(not isinstance(x, str) or not x for x in data):
        raise ValueError('Private denylist must be an array of nonempty strings')
    return data


def inspect(path, content, terms=()):
    findings = []
    normalized_path = path.replace('\\', '/')
    parts = normalized_path.split('/')
    if (set(parts) & {'private', 'outputs', 'work', 'logs'}
            or re.search(r'(?:^|/)(?:\.env(?:\..*)?|evidence\.jsonl|sessions\.json|.*\.local\.json)$', normalized_path)
            or re.search(r'-(?:sources\.html|evidence\.json|tasks\.json|source-check\.json|日報\.md|Notion貼付用\.html)$', normalized_path)):
        findings.append({'path': path, 'line': 0, 'category': 'private_or_generated_file'})
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return findings + [{'path': path, 'line': 0, 'category': 'unreviewed_binary'}]
    for number, original in enumerate(text.splitlines(), 1):
        line = original
        while '\\\\' in line:
            line = line.replace('\\\\', '\\')
        categories = set()
        if any(term.casefold() in original.casefold() for term in terms):
            categories.add('private_term')
        for match in re.finditer(r'\b[A-Za-z]:[/\\]([^\s<>"\'`]+)', line):
            value = match[1].replace('\\', '/')
            # Explicit synthetic fixtures/examples only; real workspaces must use configuration.
            if not re.match(r'(?:Users/example/|Users/private/|dev/app/|work(?:/|$|["\'])|path/to/|skills\b|llm-tools/|a/b\b|CanaryZephyr\b)', value):
                categories.add('absolute_workspace_path')
        if re.search(r'/(?:home|Users)/(?!example\b|\.\.\.)[^/\s"\'`]+/', line) and not re.search(r'\b[A-Za-z]:[/\\]', line):
            categories.add('absolute_home_path')
        if re.search(r'\b(?:[LD]PC|DESKTOP|LAPTOP)-[A-Za-z0-9]+\b', line, re.I):
            categories.add('workstation_name')
        if re.search(r'[一-龥々]{1,8}さん', line):
            categories.add('person_name_example')
        for email in re.findall(r'[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}', line):
            if not email.endswith(('@example.com', '@example.org', '@users.noreply.github.com')):
                categories.add('personal_email')
        for url in re.findall(r'https?://[^\s<>"\'`),;]+', line):
            try:
                host = urlsplit(url).hostname or ''
                if '.' not in host and host not in ('localhost',):
                    categories.add('internal_service_host')
                try:
                    address = ipaddress.ip_address(host)
                except ValueError:
                    continue
                if not address.is_loopback and (not address.is_global):
                    categories.add('internal_service_address')
            except ValueError:
                continue
        if re.search(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,})\b', line):
            categories.add('credential_pattern')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----', line):
            categories.add('private_key')
        findings.extend({'path': path, 'line': number, 'category': category} for category in sorted(categories))
    return findings


def entries(root, args):
    if args.worktree:
        for path in sorted(set(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''}):
            source = root / path
            if source.is_file():
                yield path, source.read_bytes()
    elif args.history:
        seen = set()
        for row in git(root, 'rev-list', '--objects', args.ref or 'HEAD').decode().splitlines():
            fields = row.split(' ', 1)
            if len(fields) == 2 and fields[0] not in seen:
                oid, path = fields
                seen.add(oid)
                if git(root, 'cat-file', '-t', oid).strip() == b'blob':
                    yield path, git(root, 'cat-file', 'blob', oid)
    else:
        command = ('ls-files', '--stage', '-z') if args.staged else ('ls-tree', '-r', '-z', args.ref or 'HEAD')
        for record in git(root, *command).split(b'\0'):
            if record:
                meta, raw_path = record.split(b'\t', 1)
                fields = meta.decode().split()
                oid = fields[1] if args.staged else fields[2]
                yield raw_path.decode(), git(root, 'cat-file', 'blob', oid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--worktree', action='store_true')
    group.add_argument('--staged', action='store_true')
    group.add_argument('--history', action='store_true')
    parser.add_argument('--ref')
    parser.add_argument('--denylist', type=Path)
    args = parser.parse_args()
    try:
        terms = private_terms(args.denylist)
        findings, count = [], 0
        for path, content in entries(args.root.resolve(), args):
            count += 1
            findings.extend(inspect(path, content, terms))
    except (OSError, ValueError, subprocess.CalledProcessError):
        print('Publication check failed to read files or private configuration; nothing was approved.')
        return 2
    print(json.dumps({'status': 'failed' if findings else 'passed', 'files_checked': count, 'findings': findings}, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
