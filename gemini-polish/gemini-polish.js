#!/usr/bin/env node
/*
 * gemini-polish — Claude Code / Codex が人間に見せる日本語を、Google Antigravity CLI (`agy`) を
 * 非対話モードで起動して Gemini に書き直させるフック兼 CLI。
 *
 *   node gemini-polish.js hook            # Claude Code / Codex のフックとして stdin の JSON を処理
 *   node gemini-polish.js text [--file F] # stdin (または F) の日本語を推敲して stdout に出力
 *   node gemini-polish.js file <path>...  # ドキュメントファイルをその場で推敲・上書き
 *   node gemini-polish.js install [--project] / uninstall [--project]
 *   node gemini-polish.js test / status
 *
 * 依存: Node.js, agy (PATH 上にあること)。外部パッケージなし。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

// ---------------------------------------------------------------------------
// 設定
// ---------------------------------------------------------------------------
const HOME = os.homedir();
const STATE_DIR = process.env.GEMINI_POLISH_HOME || path.join(HOME, '.gemini-polish');
const CACHE_DIR = path.join(STATE_DIR, 'cache');
const BACKUP_DIR = path.join(STATE_DIR, 'backups');
const LOG_FILE = path.join(STATE_DIR, 'log.txt');
const CONFIG_FILE = path.join(STATE_DIR, 'config.json');
const RECENT_FILE = path.join(STATE_DIR, 'recent.jsonl');
const SELF = path.resolve(__filename);
const SELF_FWD = SELF.replace(/\\/g, '/');

const DEFAULTS = {
  model: 'gemini-3.8-flash-high', // `agy models` で確認できる ID
  agyCommand: 'agy',
  effort: '', // agy --effort (low|medium|high)。空ならモデル ID の接尾辞に任せる
  timeoutSec: 150,
  minJaChars: 20, // これ未満の日本語文字数なら推敲しない
  docExts: ['.md', '.markdown', '.mdx', '.txt', '.rst', '.adoc'],
  // モデル向け指示ファイルやツール自身は対象外
  excludePattern:
    '(^|[\\\\/])(\\.claude|\\.codex|\\.git|node_modules|\\.gemini-polish)([\\\\/]|$)|(^|[\\\\/])(CLAUDE|AGENTS|MEMORY|SKILL)\\.md$',
  maxFileBytes: 80000,
  // 先頭 512 バイトにこの文字列を含むファイル（機械生成物など）は推敲しない
  skipMarker: 'gemini-polish: skip',
  rewriteResponses: true, // Stop フックで応答を差し替える
  rewriteDocs: true, // PostToolUse でドキュメントを書き直す
  bashHeuristic: true, // シェルコマンド文字列から書かれたドキュメントを推定する
  injectInstruction: true, // UserPromptSubmit で「先に推敲せよ」という指示を注入する
  recentMtimeSec: 180, // bashHeuristic: この秒数以内に更新されたファイルだけを対象にする
};

function loadConfig() {
  const cfg = { ...DEFAULTS };
  try {
    if (fs.existsSync(CONFIG_FILE)) Object.assign(cfg, JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')));
  } catch (e) {
    log(`config.json の読み込みに失敗: ${e.message}`);
  }
  const env = process.env;
  const bool = (v, d) => (v === undefined || v === '' ? d : !/^(0|false|no|off)$/i.test(v));
  if (env.GEMINI_POLISH_MODEL) cfg.model = env.GEMINI_POLISH_MODEL;
  if (env.GEMINI_POLISH_AGY) cfg.agyCommand = env.GEMINI_POLISH_AGY;
  if (env.GEMINI_POLISH_EFFORT) cfg.effort = env.GEMINI_POLISH_EFFORT;
  if (env.GEMINI_POLISH_TIMEOUT) cfg.timeoutSec = Number(env.GEMINI_POLISH_TIMEOUT) || cfg.timeoutSec;
  if (env.GEMINI_POLISH_MIN_CHARS) cfg.minJaChars = Number(env.GEMINI_POLISH_MIN_CHARS) || cfg.minJaChars;
  if (env.GEMINI_POLISH_DOC_EXTS) cfg.docExts = env.GEMINI_POLISH_DOC_EXTS.split(',').map((s) => s.trim()).filter(Boolean);
  cfg.rewriteResponses = bool(env.GEMINI_POLISH_RESPONSES, cfg.rewriteResponses);
  cfg.rewriteDocs = bool(env.GEMINI_POLISH_DOCS, cfg.rewriteDocs);
  cfg.injectInstruction = bool(env.GEMINI_POLISH_INJECT, cfg.injectInstruction);
  cfg.bashHeuristic = bool(env.GEMINI_POLISH_BASH, cfg.bashHeuristic);
  cfg.disabled = bool(env.GEMINI_POLISH_DISABLE, false);
  return cfg;
}

// ---------------------------------------------------------------------------
// 共通ユーティリティ
// ---------------------------------------------------------------------------
function ensureDirs() {
  for (const d of [STATE_DIR, CACHE_DIR, BACKUP_DIR]) {
    try {
      fs.mkdirSync(d, { recursive: true });
    } catch (_) {}
  }
}

function log(msg) {
  try {
    ensureDirs();
    fs.appendFileSync(LOG_FILE, `${new Date().toISOString()} [${process.pid}] ${msg}\n`);
  } catch (_) {}
}

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch (e) {
    return '';
  }
}

const JA_CHAR_SRC = '[\\u3041-\\u3096\\u30a1-\\u30fa\\u30fc\\u3005\\u3400-\\u4dbf\\u4e00-\\u9fff\\uf900-\\ufaff\\uff66-\\uff9f]';
const JA_CHARS_G = new RegExp(JA_CHAR_SRC, 'g');

function jaOnly(s) {
  return (String(s || '').match(JA_CHARS_G) || []).join('');
}
function jaCount(s) {
  return jaOnly(s).length;
}
function sha(s) {
  return crypto.createHash('sha256').update(s, 'utf8').digest('hex');
}

// ---------------------------------------------------------------------------
// 「すでに推敲済み」キャッシュ
//   推敲結果の日本語文字だけを取り出した文字列のハッシュを記録しておき、
//   Stop フックで同じ内容が来たら二重に推敲しない。
// ---------------------------------------------------------------------------
function recordPolished(text) {
  const n = jaOnly(text);
  if (!n) return;
  ensureDirs();
  try {
    fs.writeFileSync(path.join(CACHE_DIR, sha(n)), new Date().toISOString());
    fs.appendFileSync(RECENT_FILE, JSON.stringify({ t: Date.now(), n: n.slice(0, 20000) }) + '\n');
    // 肥大化防止
    const lines = fs.readFileSync(RECENT_FILE, 'utf8').split('\n').filter(Boolean);
    if (lines.length > 200) fs.writeFileSync(RECENT_FILE, lines.slice(-100).join('\n') + '\n');
  } catch (e) {
    log(`cache 書き込み失敗: ${e.message}`);
  }
}

function alreadyPolished(text) {
  const n = jaOnly(text);
  if (!n) return true;
  if (fs.existsSync(path.join(CACHE_DIR, sha(n)))) return true;
  try {
    if (!fs.existsSync(RECENT_FILE)) return false;
    const lines = fs.readFileSync(RECENT_FILE, 'utf8').split('\n').filter(Boolean).slice(-100);
    for (const line of lines) {
      let e;
      try {
        e = JSON.parse(line);
      } catch (_) {
        continue;
      }
      // モデルが推敲結果に一言添えた程度なら推敲済みとみなす
      if (e.n && e.n.length >= 0.8 * n.length && n.includes(e.n)) return true;
    }
  } catch (_) {}
  return false;
}

// ---------------------------------------------------------------------------
// コード・URL・パスの保護（プレースホルダに置き換えて Gemini に触らせない）
// ---------------------------------------------------------------------------
const PH_RE = /\[\[\s*JP\s*#\s*(\d+)\s*\]\]/g;

function protect(text) {
  const slots = [];
  const put = (m) => {
    slots.push(m);
    return `[[JP#${slots.length - 1}]]`;
  };
  let t = text;
  t = t.replace(/^---\r?\n[\s\S]*?\r?\n---(?=\r?\n|$)/, put); // frontmatter
  t = t.replace(/(^|\n)([ \t]*)(```|~~~)[^\n]*\n[\s\S]*?\n[ \t]*\3[ \t]*(?=\r?\n|$)/g, (m, pre) => pre + put(m.slice(pre.length)));
  t = t.replace(/<!--[\s\S]*?-->/g, put); // HTML コメント
  t = t.replace(/`[^`\n]+`/g, put); // インラインコード
  t = t.replace(/https?:\/\/[^\s<>)\]"']+/g, put); // URL
  t = t.replace(/(?:[A-Za-z]:)?[\w.~\-]*(?:[\\/][\w.~\-]+)+/g, put); // パス (C:\a\b, /a/b, src/x.js)
  return { text: t, slots };
}

function restore(text, slots) {
  const seen = new Array(slots.length).fill(0);
  const out = text.replace(PH_RE, (m, i) => {
    const k = Number(i);
    if (k >= slots.length) return m;
    seen[k]++;
    return slots[k];
  });
  const missing = seen.map((c, i) => (c === 1 ? -1 : i)).filter((i) => i >= 0);
  if (missing.length) {
    log(`プレースホルダの復元に失敗 (欠落/重複: ${missing.join(',')})`);
    return null;
  }
  return out;
}

// ---------------------------------------------------------------------------
// agy (Antigravity CLI) の呼び出し
// ---------------------------------------------------------------------------
const BEGIN = '=====原文ここから=====';
const END = '=====原文ここまで=====';

function buildPrompt(body, kind) {
  const common = [
    'あなたは日本語の校閲者です。以下の「原文」を、意味・情報・構成を一切変えずに、自然で読みやすく、簡潔で品のある日本語に書き直してください。',
    '',
    '厳守事項:',
    '- 出力は書き直した本文のみ。前置き、説明、感想、区切り線、コードフェンスで全体を囲むことは禁止。',
    `- ${BEGIN} と ${END} の行は出力しない。`,
    '- [[JP#数字]] という形式のトークンは伏せ字です。内容を変えず、同じ位置にそのまま残す（増減させない）。',
    '- Markdown の構造（見出し記号、箇条書き、番号、表、引用、リンク、強調、改行位置）はそのまま維持する。',
    '- 英単語、識別子、コマンド、数値、ファイル名、記号、日本語以外の文はそのまま残す。',
    '- 内容の追加・削除・要約・意訳はしない。文の数と段落構成はできるだけ保つ。',
    '- 敬体（です・ます）/常体は原文に合わせる。',
    '- ツールやファイル操作は一切使わない。',
  ];
  if (kind === 'doc') {
    common.push('- これはファイル全体です。先頭から末尾まで省略せず、全文を出力する。');
  } else {
    common.push('- これは AI アシスタントがユーザーに返す応答文です。口調は丁寧で簡潔に。');
  }
  return [...common, '', BEGIN, body, END].join('\n');
}

function callAgy(prompt, cfg) {
  ensureDirs();
  const msg = JSON.stringify({ event: 'user', message: { role: 'user', content: prompt } }) + '\n';
  const args = [
    '--input-format', 'stream-json',
    '--output-format', 'stream-json',
    '--model', cfg.model,
    '--disable-slash-commands',
    '--print-timeout', `${cfg.timeoutSec}s`,
    '--print=',
  ];
  if (cfg.effort) args.push('--effort', cfg.effort);
  const t0 = Date.now();
  const r = spawnSync(cfg.agyCommand, args, {
    input: msg,
    encoding: 'utf8',
    cwd: STATE_DIR, // プロジェクトの中身を agy に読ませない
    timeout: cfg.timeoutSec * 1000 + 15000,
    windowsHide: true,
    maxBuffer: 64 * 1024 * 1024,
  });
  const ms = Date.now() - t0;
  if (r.error) {
    log(`agy 起動失敗: ${r.error.message}`);
    return null;
  }
  let response = null;
  let status = null;
  for (const line of String(r.stdout || '').split('\n')) {
    if (!line.includes('"event":"result"')) continue;
    try {
      const j = JSON.parse(line);
      if (j.event === 'result' && j.result) {
        response = j.result.response;
        status = j.result.status;
      }
    } catch (_) {}
  }
  if (status !== 'SUCCESS' || typeof response !== 'string') {
    log(`agy 失敗 status=${status} exit=${r.status} ${ms}ms stderr=${String(r.stderr || '').slice(0, 500)}`);
    return null;
  }
  log(`agy OK model=${cfg.model} ${ms}ms in=${prompt.length}ch out=${response.length}ch`);
  return response;
}

function stripWrapper(out) {
  let s = out.replace(/\r\n/g, '\n').trim();
  s = s.replace(new RegExp(`^${BEGIN}\\s*\\n?`), '').replace(new RegExp(`\\n?\\s*${END}$`), '').trim();
  const m = s.match(/^(```|~~~)[^\n]*\n([\s\S]*?)\n\1\s*$/);
  if (m && !m[2].includes(m[1])) s = m[2];
  return s;
}

/**
 * 日本語テキストを推敲して返す。失敗時は null。
 * kind: 'chat' | 'doc'
 */
function polishText(text, kind, cfg) {
  const src = String(text).replace(/\r\n/g, '\n');
  const { text: guarded, slots } = protect(src);
  if (jaCount(guarded) < cfg.minJaChars) return src; // 日本語がコードや URL の中にしかない
  const out = callAgy(buildPrompt(guarded, kind), cfg);
  if (out === null) return null;
  const cleaned = stripWrapper(out);
  const restored = restore(cleaned, slots);
  if (restored === null) return null;
  const ratio = restored.length / Math.max(1, src.length);
  if (!restored.trim() || ratio < 0.4 || ratio > 2.5) {
    log(`推敲結果の長さが不自然 (ratio=${ratio.toFixed(2)})。破棄`);
    return null;
  }
  return restored;
}

// ---------------------------------------------------------------------------
// ドキュメントファイルの推敲
// ---------------------------------------------------------------------------
function isDocFile(file, cfg) {
  const ext = path.extname(file).toLowerCase();
  if (!cfg.docExts.includes(ext)) return false;
  if (new RegExp(cfg.excludePattern, 'i').test(file)) return false;
  return true;
}

function polishFile(file, cfg) {
  const abs = path.resolve(file);
  if (!isDocFile(abs, cfg)) return { file: abs, status: 'skip', reason: '対象外' };
  let st;
  try {
    st = fs.statSync(abs);
  } catch (_) {
    return { file: abs, status: 'skip', reason: '存在しない' };
  }
  if (!st.isFile()) return { file: abs, status: 'skip', reason: 'ファイルでない' };
  if (st.size > cfg.maxFileBytes) return { file: abs, status: 'skip', reason: `サイズ超過 (${st.size}B)` };
  const original = fs.readFileSync(abs, 'utf8');
  if (cfg.skipMarker && original.slice(0, 512).includes(cfg.skipMarker)) return { file: abs, status: 'skip', reason: 'skip マーカー' };
  if (jaCount(original) < cfg.minJaChars) return { file: abs, status: 'skip', reason: '日本語が少ない' };
  if (alreadyPolished(original)) return { file: abs, status: 'cached' };

  const polished = polishText(original, 'doc', cfg);
  if (polished === null) return { file: abs, status: 'error', reason: '推敲失敗 (log.txt 参照)' };
  const crlf = /\r\n/.test(original);
  let out = polished;
  if (/\n$/.test(original) && !/\n$/.test(out)) out += '\n';
  if (crlf) out = out.replace(/\r?\n/g, '\r\n');
  if (out === original) {
    recordPolished(original);
    return { file: abs, status: 'unchanged' };
  }
  // 上書き前に元ファイルを退避
  ensureDirs();
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const bak = path.join(BACKUP_DIR, `${stamp}_${path.basename(abs)}`);
  try {
    fs.writeFileSync(bak, original);
  } catch (e) {
    log(`バックアップ失敗: ${e.message}`);
  }
  fs.writeFileSync(abs, out);
  recordPolished(out);
  log(`ファイル推敲: ${abs} (backup: ${bak})`);
  return { file: abs, status: 'rewritten', backup: bak };
}

// ---------------------------------------------------------------------------
// フック入力からドキュメント候補パスを抽出
// ---------------------------------------------------------------------------
function candidateFilesFromToolInput(toolInput, cwd, cfg) {
  const found = new Set();
  const toAbs = (p) => {
    // Git Bash 流の /c/Users/... を Windows パスに直す
    if (process.platform === 'win32' && /^\/[a-zA-Z]\//.test(p)) p = `${p[1].toUpperCase()}:${p.slice(2)}`;
    return path.normalize(path.isAbsolute(p) ? p : path.join(cwd || process.cwd(), p));
  };
  const addPath = (p) => {
    if (!p || typeof p !== 'string') return;
    found.add(toAbs(p));
  };
  const parsePatch = (s) => {
    const re = /^\*\*\* (?:Add|Update) File: (.+)$/gm;
    let m;
    while ((m = re.exec(s))) addPath(m[1].trim());
  };
  const heuristic = (s) => {
    if (!cfg.bashHeuristic) return;
    const extAlt = cfg.docExts.map((e) => e.replace(/^\./, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const re = new RegExp(`(?:[A-Za-z]:)?[\\w.~\\-\\\\/]+\\.(?:${extAlt})(?![\\w.])`, 'gi');
    const now = Date.now();
    for (const tok of s.match(re) || []) {
      const abs = toAbs(tok);
      try {
        const st = fs.statSync(abs);
        if (st.isFile() && now - st.mtimeMs < cfg.recentMtimeSec * 1000) found.add(abs);
      } catch (_) {}
    }
  };

  if (typeof toolInput === 'string') {
    if (toolInput.includes('*** Begin Patch')) parsePatch(toolInput);
    else heuristic(toolInput);
  } else if (toolInput && typeof toolInput === 'object') {
    addPath(toolInput.file_path);
    addPath(toolInput.notebook_path);
    addPath(toolInput.path);
    for (const [k, v] of Object.entries(toolInput)) {
      const s = Array.isArray(v) ? v.filter((x) => typeof x === 'string').join(' ') : v;
      if (typeof s !== 'string') continue;
      if (s.includes('*** Begin Patch')) parsePatch(s);
      else if (/^(command|cmd|script|input|args)$/i.test(k)) heuristic(s);
    }
  }
  return [...found].filter((f) => isDocFile(f, cfg));
}

// ---------------------------------------------------------------------------
// フック本体
// ---------------------------------------------------------------------------
function instructionText() {
  return [
    '[gemini-polish] 人間に見せる日本語はすべて Gemini に書き直させる運用です。',
    'ユーザーに返す最終応答を日本語で書く場合は、必ず先に Bash ツールで次の形式のコマンドを実行し（heredoc を直接付ける。パイプ・cat・PowerShell は許可されない）、その標準出力を一字一句そのまま最終応答として出力してください:',
    `node "${SELF_FWD}" text <<'GEMINIPOLISH'`,
    '<応答本文>',
    'GEMINIPOLISH',
    `Bash ツールが使えない場合は本文を一時ファイルに書き、\`node "${SELF_FWD}" text --file <パス>\` を実行します。`,
    'コードブロック・パス・URL は自動で保護されます。実行を省いた場合は Stop フックが応答を差し替えるため、応答が二重に表示されます。',
    '日本語を含む .md/.txt などのドキュメントを書いた場合はフックが自動で推敲して上書きするので、続けて編集する前に必ず再読込してください。',
  ].join('\n');
}

function lastAssistantTextFromTranscript(transcriptPath) {
  try {
    if (!transcriptPath || !fs.existsSync(transcriptPath)) return null;
    const lines = fs.readFileSync(transcriptPath, 'utf8').split('\n').filter(Boolean);
    for (let i = lines.length - 1; i >= 0; i--) {
      let j;
      try {
        j = JSON.parse(lines[i]);
      } catch (_) {
        continue;
      }
      if (j.type !== 'assistant' || !j.message || !Array.isArray(j.message.content)) continue;
      const texts = j.message.content.filter((c) => c.type === 'text' && c.text).map((c) => c.text);
      if (texts.length) return texts.join('\n');
    }
  } catch (_) {}
  return null;
}

function hookMain(cfg) {
  const raw = readStdin();
  let input = {};
  try {
    input = JSON.parse(raw || '{}');
  } catch (e) {
    log(`hook: JSON 解析失敗: ${e.message}`);
    return 0;
  }
  const ev = input.hook_event_name || '';
  if (process.env.GEMINI_POLISH_DEBUG) log(`hook ${ev}: ${raw.slice(0, 2000)}`);
  if (cfg.disabled) return 0;

  if (ev === 'UserPromptSubmit') {
    if (!cfg.injectInstruction) return 0;
    emit({ hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: instructionText() } });
    return 0;
  }

  if (ev === 'PostToolUse') {
    if (!cfg.rewriteDocs) return 0;
    const files = candidateFilesFromToolInput(input.tool_input, input.cwd, cfg);
    if (!files.length) return 0;
    const results = files.map((f) => polishFile(f, cfg));
    const rewritten = results.filter((r) => r.status === 'rewritten');
    log(`PostToolUse ${input.tool_name}: ${results.map((r) => `${path.basename(r.file)}=${r.status}`).join(', ')}`);
    if (!rewritten.length) return 0;
    const list = rewritten.map((r) => r.file).join(', ');
    emit({
      systemMessage: `gemini-polish: Gemini が推敲して上書きしました: ${rewritten.map((r) => path.basename(r.file)).join(', ')}`,
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: `[gemini-polish] 次のファイルの日本語を Gemini が推敲して上書きしました: ${list}\n内容が変わっているので、続けて編集する場合は先に再読込してください。推敲前の内容に戻す必要はありません。`,
      },
    });
    return 0;
  }

  if (ev === 'Stop') {
    if (!cfg.rewriteResponses) return 0;
    if (input.stop_hook_active) return 0; // 差し替え後の再 Stop。無限ループ防止
    let msg = typeof input.last_assistant_message === 'string' ? input.last_assistant_message : null;
    if (!msg) msg = lastAssistantTextFromTranscript(input.transcript_path);
    if (!msg || jaCount(msg) < cfg.minJaChars) return 0;
    if (alreadyPolished(msg)) {
      log('Stop: 推敲済みのため通過');
      return 0;
    }
    const polished = polishText(msg, 'chat', cfg);
    if (polished === null) return 0; // agy が失敗しても会話は止めない
    recordPolished(polished);
    if (jaOnly(polished) === jaOnly(msg)) {
      log('Stop: 推敲しても同一');
      return 0;
    }
    log(`Stop: 応答を差し替え (${msg.length} -> ${polished.length}ch)`);
    emit({
      decision: 'block',
      reason:
        '[gemini-polish] 直前の応答を Gemini が推敲しました。次の本文だけを、一字一句変えずにそのまま出力してください。' +
        '前置き・後書き・補足・謝罪・コードフェンスでの囲みは禁止。ツールは使わないこと。\n\n' +
        polished,
    });
    return 0;
  }

  return 0;
}

function emit(obj) {
  process.stdout.write(JSON.stringify(obj));
}

// ---------------------------------------------------------------------------
// CLI: text / file / test / status
// ---------------------------------------------------------------------------
function textMain(argv, cfg) {
  const fi = argv.indexOf('--file');
  let src;
  if (fi >= 0 && argv[fi + 1]) src = fs.readFileSync(argv[fi + 1], 'utf8');
  else src = readStdin();
  if (!src.trim()) {
    process.stderr.write('gemini-polish: 入力が空です\n');
    return 1;
  }
  if (cfg.disabled || jaCount(src) < cfg.minJaChars || alreadyPolished(src)) {
    process.stdout.write(src);
    return 0;
  }
  const polished = polishText(src, 'chat', cfg);
  if (polished === null) {
    process.stderr.write('gemini-polish: 推敲に失敗したため原文をそのまま出力します (~/.gemini-polish/log.txt 参照)\n');
    process.stdout.write(src);
    return 0;
  }
  recordPolished(polished);
  process.stdout.write(polished.endsWith('\n') ? polished : polished + '\n');
  return 0;
}

function fileMain(argv, cfg) {
  const files = argv.filter((a) => !a.startsWith('--'));
  if (!files.length) {
    process.stderr.write('使い方: gemini-polish.js file <path>...\n');
    return 1;
  }
  let code = 0;
  for (const f of files) {
    const r = polishFile(f, cfg);
    process.stdout.write(`${r.status}\t${r.file}${r.reason ? `\t${r.reason}` : ''}${r.backup ? `\t(backup: ${r.backup})` : ''}\n`);
    if (r.status === 'error') code = 1;
  }
  return code;
}

function testMain(cfg) {
  const sample = 'ファイルの書き込みが完了しました。テストを走らせた結果、3つのケースが失敗しています。原因を調査中ですので、`npm test` の結果は C:\\dev\\app\\log.txt を見てください。';
  process.stdout.write(`model: ${cfg.model}\nagy:   ${cfg.agyCommand}\n--- 原文 ---\n${sample}\n--- 推敲 ---\n`);
  const t0 = Date.now();
  const out = polishText(sample, 'chat', cfg);
  process.stdout.write((out === null ? '(失敗: ~/.gemini-polish/log.txt を確認)' : out) + `\n--- ${Date.now() - t0}ms ---\n`);
  return out === null ? 1 : 0;
}

function statusMain(cfg) {
  const claude = path.join(HOME, '.claude', 'settings.json');
  const codex = path.join(HOME, '.codex', 'hooks.json');
  const has = (f) => {
    try {
      return fs.readFileSync(f, 'utf8').includes('gemini-polish.js');
    } catch (_) {
      return false;
    }
  };
  const agy = spawnSync(cfg.agyCommand, ['--version'], { encoding: 'utf8', windowsHide: true });
  process.stdout.write(
    [
      `script:            ${SELF}`,
      `state dir:         ${STATE_DIR}`,
      `agy:               ${agy.error ? '見つからない (' + agy.error.message + ')' : String(agy.stdout).trim()}`,
      `model:             ${cfg.model}`,
      `Claude Code hooks: ${has(claude) ? '有効' : '未設定'} (${claude})`,
      `Codex hooks:       ${has(codex) ? '有効' : '未設定'} (${codex})`,
      `config:            ${JSON.stringify({ ...cfg }, null, 0)}`,
      '',
    ].join('\n')
  );
  return 0;
}

// ---------------------------------------------------------------------------
// install / uninstall
// ---------------------------------------------------------------------------
const HOOK_CMD = `node "${SELF_FWD}" hook`;
const isOurs = (h) => h && typeof h.command === 'string' && h.command.includes('gemini-polish.js');

function hookEntries(kind) {
  // 1 イベント 1 エントリにまとめる（Codex の /hooks で信頼する数を減らすため）。
  // Codex は Windows では commandWindows を優先するので同じ内容を入れておく。
  const cmd = (timeout, statusMessage) => ({
    type: 'command',
    command: HOOK_CMD,
    ...(kind === 'codex' ? { commandWindows: HOOK_CMD } : {}),
    timeout,
    statusMessage,
  });
  const tools = kind === 'claude'
    ? ['Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash', 'PowerShell']
    : ['apply_patch', 'Write', 'Edit', 'Bash', 'shell', 'local_shell', 'exec_command'];
  return {
    UserPromptSubmit: [{ hooks: [cmd(20, 'gemini-polish: 推敲ルールを注入')] }],
    Stop: [{ hooks: [cmd(200, 'gemini-polish: 応答を Gemini で推敲中')] }],
    PostToolUse: [{ matcher: `^(${tools.join('|')})$`, hooks: [cmd(300, 'gemini-polish: ドキュメントを Gemini で推敲中')] }],
  };
}

function stripOurs(hooks) {
  if (!hooks || typeof hooks !== 'object') return {};
  for (const ev of Object.keys(hooks)) {
    if (!Array.isArray(hooks[ev])) continue;
    hooks[ev] = hooks[ev]
      .map((g) => ({ ...g, hooks: Array.isArray(g.hooks) ? g.hooks.filter((h) => !isOurs(h)) : g.hooks }))
      .filter((g) => Array.isArray(g.hooks) && g.hooks.length);
    if (!hooks[ev].length) delete hooks[ev];
  }
  return hooks;
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (_) {
    return {};
  }
}

function writeJson(file, obj) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  if (fs.existsSync(file)) {
    try {
      fs.copyFileSync(file, `${file}.gemini-polish.bak`);
    } catch (_) {}
  }
  fs.writeFileSync(file, JSON.stringify(obj, null, 2) + '\n');
}

function installMain(argv, remove) {
  const project = argv.includes('--project');
  const base = project ? process.cwd() : HOME;
  const claudeFile = path.join(base, '.claude', 'settings.json');
  const codexFile = path.join(base, '.codex', 'hooks.json');
  const permRules = [`Bash(node "${SELF_FWD}":*)`, `PowerShell(node "${SELF_FWD}":*)`];

  // Claude Code
  const cs = readJson(claudeFile);
  cs.hooks = stripOurs(cs.hooks);
  cs.permissions = cs.permissions || {};
  cs.permissions.allow = (cs.permissions.allow || []).filter((r) => !String(r).includes('gemini-polish.js'));
  if (!remove) {
    for (const [ev, groups] of Object.entries(hookEntries('claude'))) cs.hooks[ev] = [...(cs.hooks[ev] || []), ...groups];
    cs.permissions.allow.push(...permRules);
  }
  writeJson(claudeFile, cs);

  // Codex
  const cx = readJson(codexFile);
  cx.hooks = stripOurs(cx.hooks);
  if (!remove) {
    for (const [ev, groups] of Object.entries(hookEntries('codex'))) cx.hooks[ev] = [...(cx.hooks[ev] || []), ...groups];
    if (!cx.description) cx.description = 'gemini-polish: 人間に見せる日本語を Gemini (agy) で推敲する';
  }
  writeJson(codexFile, cx);

  ensureDirs();
  if (!fs.existsSync(CONFIG_FILE)) fs.writeFileSync(CONFIG_FILE, JSON.stringify({ model: DEFAULTS.model }, null, 2) + '\n');

  process.stdout.write(
    [
      `${remove ? 'アンインストール' : 'インストール'}しました。`,
      `  Claude Code: ${claudeFile}`,
      `  Codex:       ${codexFile}`,
      `  設定:        ${CONFIG_FILE} (model など)`,
      remove ? '' : `  Codex 側は ~/.codex/config.toml の [features] hooks = false になっていないことを確認してください。`,
      '',
    ].join('\n')
  );
  return 0;
}

// ---------------------------------------------------------------------------
function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  const cfg = loadConfig();
  switch (cmd) {
    case 'hook':
      return hookMain(cfg);
    case 'text':
      return textMain(rest, cfg);
    case 'file':
      return fileMain(rest, cfg);
    case 'test':
      return testMain(cfg);
    case 'status':
      return statusMain(cfg);
    case 'install':
      return installMain(rest, false);
    case 'uninstall':
      return installMain(rest, true);
    default:
      process.stderr.write(
        'usage: gemini-polish.js <hook|text [--file F]|file <path>...|test|status|install [--project]|uninstall [--project]>\n'
      );
      return cmd ? 1 : 0;
  }
}

try {
  process.exitCode = main();
} catch (e) {
  log(`致命的エラー: ${e.stack || e.message}`);
  process.stderr.write(`gemini-polish: ${e.message}\n`);
  process.exitCode = process.argv[2] === 'hook' ? 0 : 1; // フックでは会話を止めない
}
