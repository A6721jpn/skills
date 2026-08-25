/**
 * Reduce Chrome history rows to a privacy-minimized interest-profile/v2 draft.
 * Raw URLs, titles, queries, hostnames, and timestamps never leave this module.
 */

import { isIP } from "node:net";

const DAY_MS = 86_400_000;
const SHORT_WINDOW_DAYS = 7;
const MAX_VISITS_PER_TOPIC_DAY_DOMAIN = 3;
const MAX_ATTENTION_SECONDS_PER_VISIT = 600;
const MAX_SESSION_GAP_SECONDS = 1_800;
const MAX_ATTENTION_SECONDS_PER_TOPIC_DAY_DOMAIN = 1_800;

const TOPIC_RULES = [
  {
    id: "cad-cae-manufacturing",
    parent_id: "engineering-design",
    label: "機械CAD・CAE・製造技術",
    patterns: ["solidworks", "fusion 360", "autodesk", "mechanical cad", " cae ", " step ", "b-rep", "brep", "opencascade", "dfm", "manufacturing", "machining"],
    news_query_terms: ["mechanical CAD CAE", "SolidWorks Fusion 360 update", "STEP B-Rep Open CASCADE", "mechanical design DFM manufacturing"],
    preferred_primary_domains: ["autodesk.com", "solidworks.com", "3ds.com", "opencascade.com"],
    rationale: "設計・解析・製造技術について、複数日と複数公開ソースの集計根拠がある。",
    work_prior: 0.45,
    intent_prior: "mixed",
    news_priority: 1.0,
  },
  {
    id: "industrial-components-materials",
    parent_id: "manufacturing-technology",
    label: "機械部品・材料・接合技術",
    patterns: ["misumi", "fastener", "screw", "bolt", "connector", "adhesive", "molex", "bearing", "spring", "actuator", "engineering material"],
    news_query_terms: ["industrial components materials", "fasteners connectors adhesives", "mechanical components supplier technology"],
    preferred_primary_domains: ["misumi-ec.com", "3m.com", "molex.com"],
    rationale: "機械部品・材料・接合技術について、継続性と公開ソース分散の集計根拠がある。",
    work_prior: 0.5,
    intent_prior: "mixed",
    news_priority: 0.95,
  },
  {
    id: "electronics-pcb-haptics",
    parent_id: "engineering-electronics",
    label: "電子回路・PCB・触覚デバイス",
    patterns: [" pcb ", "jlcpcb", "circuit", "battery", "sensor", "embedded", "haptic", "tactile", "electronics"],
    news_query_terms: ["electronics PCB manufacturing", "battery sensor embedded hardware", "haptics tactile actuator technology"],
    preferred_primary_domains: ["jlcpcb.com", "molex.com", "eemb.com"],
    rationale: "電子回路・PCB・触覚技術について、複数日の公開情報調査を示す集計根拠がある。",
    work_prior: 0.35,
    intent_prior: "mixed",
    news_priority: 1.0,
  },
  {
    id: "robotics-mechatronics",
    parent_id: "engineering-electronics",
    label: "ロボティクス・メカトロニクス",
    patterns: ["robotics", "robot arm", "mechatronics", "servo motor", "stepper motor", "motion control", "ros2", "ros 2"],
    news_query_terms: ["robotics mechatronics", "robot motion control", "ROS 2 robotics update"],
    preferred_primary_domains: ["ros.org", "ifr.org", "nvidia.com"],
    rationale: "ロボティクスとメカトロニクスについて、複数公開ソースの反復的な調査根拠がある。",
    work_prior: 0.4,
    intent_prior: "mixed",
    news_priority: 0.95,
  },
  {
    id: "ai-software-automation",
    parent_id: "software-ai",
    label: "生成AI・開発ツール・業務自動化",
    patterns: ["openai", "chatgpt", "codex", "claude", "github", "python", " mcp ", "ai agent", "developer tool", "software automation"],
    news_query_terms: ["OpenAI Codex update", "AI developer tools agents", "MCP software automation", "Python engineering automation"],
    preferred_primary_domains: ["openai.com", "github.com", "python.org"],
    rationale: "生成AI・開発・自動化技術について、継続性と公開ソース分散の集計根拠がある。",
    work_prior: 0.4,
    intent_prior: "mixed",
    news_priority: 1.0,
  },
  {
    id: "software-security-infrastructure",
    parent_id: "software-ai",
    label: "ソフトウェア基盤・セキュリティ",
    patterns: ["cybersecurity", "security advisory", "vulnerability", " cve ", "cloudflare", "docker", "kubernetes", "linux kernel", "devops"],
    news_query_terms: ["software security advisory", "developer infrastructure update", "cloud native security"],
    preferred_primary_domains: ["cisa.gov", "nvd.nist.gov", "cloudflare.com", "kubernetes.io"],
    rationale: "ソフトウェア基盤とセキュリティについて、複数日の公開技術情報を調べた集計根拠がある。",
    work_prior: 0.45,
    intent_prior: "mixed",
    news_priority: 0.9,
  },
  {
    id: "hardware-input-devices",
    parent_id: "consumer-technology",
    label: "入力デバイス・PCハードウェア",
    patterns: ["keyboard", "mouse", "pointing device", "3dconnexion", "lofree", "lenovo", "workstation", "ergonomic"],
    news_query_terms: ["keyboard mouse input device technology", "ergonomic pointing device", "mobile workstation hardware"],
    preferred_primary_domains: ["lenovo.com", "3dconnexion.com", "lofree.co.jp"],
    rationale: "入力デバイスとPCハードウェアについて、日付と公開ソースに広がりのある集計根拠がある。",
    work_prior: 0.2,
    intent_prior: "mixed",
    news_priority: 0.9,
  },
  {
    id: "digital-fabrication-prototyping",
    parent_id: "manufacturing-technology",
    label: "デジタル製造・試作サービス",
    patterns: ["3d print", "additive manufacturing", " cnc ", "prototype", "jlc3dp", "jlccnc", "rapid prototyping", "fabrication service"],
    news_query_terms: ["digital manufacturing prototyping", "CNC machining service update", "3D printing rapid prototyping", "PCB fabrication service"],
    preferred_primary_domains: ["jlcpcb.com", "jlc3dp.com", "jlccnc.com", "make.dmm.com"],
    rationale: "デジタル製造と試作について、複数日と複数公開ソースの集計根拠がある。",
    work_prior: 0.45,
    intent_prior: "mixed",
    news_priority: 0.95,
  },
  {
    id: "product-design-human-factors",
    parent_id: "engineering-design",
    label: "プロダクトデザイン・人間工学",
    patterns: ["industrial design", "product design", "human factors", "usability", "ergonomics", "interaction design", "design system"],
    news_query_terms: ["industrial product design", "human factors ergonomics", "product design technology"],
    preferred_primary_domains: ["designcouncil.org.uk", "interaction-design.org"],
    rationale: "プロダクトデザインと人間工学について、複数公開ソースにまたがる集計根拠がある。",
    work_prior: 0.3,
    intent_prior: "mixed",
    news_priority: 0.85,
  },
  {
    id: "science-engineering-research",
    parent_id: "science-research",
    label: "科学・工学研究",
    patterns: ["arxiv", "nature.com", "science.org", "research paper", "materials science", "mechanical engineering research", "applied physics"],
    news_query_terms: ["engineering research", "materials science research", "applied physics technology"],
    preferred_primary_domains: ["arxiv.org", "nature.com", "science.org"],
    rationale: "科学・工学研究について、複数日の公開研究情報を参照した集計根拠がある。",
    work_prior: 0.25,
    intent_prior: "unknown",
    news_priority: 0.9,
  },
  {
    id: "standards-regulation",
    parent_id: "business-industry",
    label: "技術標準・製品規制",
    patterns: [" iso ", " iec ", " jis ", "standardization", "product regulation", "compliance", "certification", "fcc.gov", "europa.eu"],
    news_query_terms: ["engineering standards update", "product compliance regulation", "ISO IEC technology standard"],
    preferred_primary_domains: ["iso.org", "iec.ch", "europa.eu", "fcc.gov"],
    rationale: "技術標準と製品規制について、複数公開ソースにわたる調査の集計根拠がある。",
    work_prior: 0.65,
    intent_prior: "professional",
    news_priority: 0.9,
  },
  {
    id: "work-tools-collaboration",
    parent_id: "software-ai",
    label: "業務ツール・コラボレーション",
    patterns: ["google workspace", "slack", "notion", "linear.app", "collaboration tool", "task management"],
    news_query_terms: ["Google Workspace update", "Slack productivity update", "Notion Linear workflow automation"],
    preferred_primary_domains: ["workspace.google.com", "slack.com", "notion.so", "linear.app"],
    rationale: "業務ツールに関する集計根拠があるが、必須利用の可能性を考慮して優先度を抑える。",
    work_prior: 0.9,
    intent_prior: "professional",
    news_priority: 0.72,
  },
  {
    id: "industrial-business-supply-chain",
    parent_id: "business-industry",
    label: "製造業の企業動向・調達・供給網",
    patterns: ["supply chain", "procurement", "manufacturing regulation", "meti.go.jp", "jetro.go.jp", "industrial business", "factory investment"],
    news_query_terms: ["manufacturing supply chain Japan", "industrial procurement technology", "Japan manufacturing investment"],
    preferred_primary_domains: ["meti.go.jp", "jetro.go.jp", "misumi-ec.com"],
    rationale: "製造業の企業動向・調達・供給網について、複数日の公開情報調査を示す集計根拠がある。",
    work_prior: 0.7,
    intent_prior: "professional",
    news_priority: 0.85,
  },
  {
    id: "mobility-aerospace",
    parent_id: "engineering-mobility",
    label: "モビリティ・航空宇宙技術",
    patterns: ["automotive engineering", "electric vehicle", "mobility technology", "aerospace", "spacecraft", "rocket engine", "aviation technology"],
    news_query_terms: ["mobility engineering technology", "aerospace technology update", "electric vehicle engineering"],
    preferred_primary_domains: ["nasa.gov", "esa.int", "jaxa.jp"],
    rationale: "モビリティと航空宇宙技術について、複数公開ソースにまたがる集計根拠がある。",
    work_prior: 0.2,
    intent_prior: "unknown",
    news_priority: 0.85,
  },
  {
    id: "creative-digital-tools",
    parent_id: "creative-technology",
    label: "映像・音響・デジタル制作ツール",
    patterns: ["video editing", "audio production", "music production", "photography", "camera technology", "davinci resolve", "adobe premiere", "blender"],
    news_query_terms: ["digital creative tools update", "video audio production technology", "camera imaging technology"],
    preferred_primary_domains: ["adobe.com", "blackmagicdesign.com", "blender.org"],
    rationale: "映像・音響・デジタル制作ツールについて、複数日の公開情報調査を示す集計根拠がある。",
    work_prior: 0.1,
    intent_prior: "unknown",
    news_priority: 0.8,
  },
];

const PRIVATE_SUFFIXES = [".internal", ".local", ".lan", ".corp", ".home", ".localhost", ".invalid", ".test", ".example"];
const UTILITY_HOSTS = ["accounts.google.com", "docs.google.com", "drive.google.com", "mail.google.com", "calendar.google.com"];
const UTILITY_TEXT = ["login", "sign in", "checkout", "cart", "billing", "password", "intranet", "localhost"];
const SEARCH_HOST_PATTERNS = [
  /^google\.[a-z.]+$/i,
  /^(?:www\.)?bing\.com$/i,
  /^search\.yahoo\.[a-z.]+$/i,
  /^(?:www\.)?duckduckgo\.com$/i,
  /^(?:www\.)?baidu\.com$/i,
  /^(?:www\.)?yandex\.[a-z.]+$/i,
];
const PRIVATE_WORKSPACE_HOST_PATTERNS = [
  /^(?!slack\.com$).+\.slack\.com$/i,
  /^(?:.+\.)?notion\.site$/i,
  /^(?:.+\.)?atlassian\.net$/i,
  /^(?:.+\.)?sharepoint\.com$/i,
  /^app\.(?:asana|miro)\.com$/i,
];
const PUBLIC_PRODUCT_PATHS = new Map([
  ["notion.so", /^\/(?:$|product|releases?|blog|help|pricing)(?:\/|$)/i],
  ["linear.app", /^\/(?:$|features|changelog|pricing|method|blog)(?:\/|$)/i],
  ["trello.com", /^\/(?:$|home|guide|pricing|platform|views)(?:\/|$)/i],
]);
const SEARCH_PATH_RE = /(?:^|\/)(?:search|results|web)(?:\/|$)/i;
const PRIVATE_PATH_RE = /(?:^|\/)(?:workspace|document|docs|file|board|issue|project|team|channel|messages|inbox)(?:\/|$)/i;
const SEARCH_QUERY_KEYS = ["q", "query", "search", "keyword", "keywords", "text"];
const DNS_LABEL_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i;
const LEGACY_IP_LABEL_RE = /^(?:\d+|0x[0-9a-f]+)$/i;
const MULTI_LABEL_PUBLIC_SUFFIXES = new Set([
  "ac.jp", "co.jp", "go.jp", "ne.jp", "or.jp", "co.uk", "org.uk",
  "com.au", "net.au", "com.br", "com.cn", "com.sg",
]);

function clamp(value, minimum = 0, maximum = 1) {
  return Math.max(minimum, Math.min(maximum, value));
}

function round(value, digits = 2) {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function sigmoid(value) {
  return 1 / (1 + Math.exp(-value));
}

function rowTimestamp(row) {
  const value = row?.visitTime ?? row?.dateVisited ?? row?.lastVisitTime ?? row?.visitedAt ?? row?.visited_at ?? row?.timestamp ?? row?.time;
  if (typeof value === "number" && Number.isFinite(value)) {
    const milliseconds = value < 10_000_000_000 ? value * 1000 : value;
    const parsed = new Date(milliseconds);
    return Number.isNaN(parsed.valueOf()) ? null : parsed;
  }
  if (typeof value === "string") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.valueOf()) ? null : parsed;
  }
  return null;
}

function stableCanonicalValue(value, ancestors = new Set()) {
  if (value === null) return null;
  if (typeof value === "undefined") return { __type: "undefined" };
  if (typeof value === "number" && !Number.isFinite(value)) return { __type: String(value) };
  if (typeof value === "bigint") return { __type: "bigint", value: String(value) };
  if (typeof value !== "object") return value;
  if (ancestors.has(value)) return { __type: "circular" };
  const nextAncestors = new Set(ancestors);
  nextAncestors.add(value);
  if (Array.isArray(value)) return value.map((item) => stableCanonicalValue(item, nextAncestors));
  return Object.fromEntries(
    Object.keys(value)
      .sort()
      .map((key) => [key, stableCanonicalValue(value[key], nextAncestors)]),
  );
}

function stableTieKey(row) {
  // This key is sanitizer-local only; it is never returned in the safe profile.
  return JSON.stringify(stableCanonicalValue(row));
}

function dateOnly(value, timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const fields = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${fields.year}-${fields.month}-${fields.day}`;
}

function dateOrdinal(value) {
  return Math.floor(Date.parse(`${value}T00:00:00Z`) / DAY_MS);
}

function domainBucket(host) {
  const labels = host.split(".").filter(Boolean);
  if (labels.length <= 2) return host;
  const suffix = labels.slice(-2).join(".");
  return MULTI_LABEL_PUBLIC_SUFFIXES.has(suffix) ? labels.slice(-3).join(".") : suffix;
}

function parsePublicRow(row) {
  if (!row || typeof row !== "object" || typeof row.url !== "string") return null;
  let parsed;
  try {
    parsed = new URL(row.url);
  } catch {
    return null;
  }
  const host = parsed.hostname.toLowerCase().replace(/^www\./, "").replace(/\.$/, "");
  if (!["http:", "https:"].includes(parsed.protocol) || !host || !host.includes(".")) return null;
  if (isIP(host.replace(/^\[/, "").replace(/\]$/, "")) !== 0) return null;
  const labels = host.split(".");
  if (host.length > 253 || !/[a-z]/i.test(labels.at(-1)) || labels.some((label) => !DNS_LABEL_RE.test(label))) return null;
  if (labels.every((label) => LEGACY_IP_LABEL_RE.test(label))) return null;
  if (host === "localhost" || PRIVATE_SUFFIXES.some((suffix) => host.endsWith(suffix))) return null;
  if (UTILITY_HOSTS.some((utility) => host === utility || host.endsWith(`.${utility}`))) return null;
  if (SEARCH_HOST_PATTERNS.some((pattern) => pattern.test(host))) return null;
  if (PRIVATE_WORKSPACE_HOST_PATTERNS.some((pattern) => pattern.test(host))) return null;
  if (PUBLIC_PRODUCT_PATHS.has(host) && !PUBLIC_PRODUCT_PATHS.get(host).test(parsed.pathname)) return null;
  if (host.startsWith("search.") || SEARCH_PATH_RE.test(parsed.pathname)) return null;
  if (SEARCH_QUERY_KEYS.some((key) => parsed.searchParams.has(key))) return null;
  if (PRIVATE_PATH_RE.test(parsed.pathname)) return null;
  const text = ` ${host} ${parsed.pathname.replaceAll(/[-_./]+/g, " ")} ${String(row.title ?? "")} `.toLowerCase();
  if (UTILITY_TEXT.some((term) => text.includes(term))) return null;
  return {
    host,
    text,
    pageKey: `${parsed.protocol}//${host}${parsed.pathname}`,
  };
}

function attentionEstimate(current, next) {
  if (!next) return null;
  const gapSeconds = (next.timestamp.valueOf() - current.timestamp.valueOf()) / 1000;
  if (!(gapSeconds > 0) || gapSeconds > MAX_SESSION_GAP_SECONDS) return null;
  if (current.row?.isLocal === false || next.row?.isLocal === false) return null;
  let reliability = gapSeconds < 5 ? 0.25 : gapSeconds > MAX_ATTENTION_SECONDS_PER_VISIT ? 0.5 : 1;
  if (current.row?.isLocal === undefined || next.row?.isLocal === undefined) reliability *= 0.75;
  const transition = String(current.row?.transition ?? current.row?.transitionType ?? "").toLowerCase();
  if (transition.includes("reload") || transition.includes("redirect")) reliability *= 0.25;
  if (current.publicRow && next.publicRow && current.publicRow.pageKey === next.publicRow.pageKey) reliability *= 0.25;
  return Math.min(gapSeconds, MAX_ATTENTION_SECONDS_PER_VISIT) * reliability;
}

function recencyBand(daysSinceLast) {
  return daysSinceLast <= 7 ? "recent" : daysSinceLast <= 30 ? "mixed" : "older";
}

function decayScore(state, endOrdinal, windowDays, halfLifeDays) {
  const effectiveDays = Math.max(1, windowDays);
  let numerator = 0;
  let denominator = 0;
  for (let age = 0; age < effectiveDays; age += 1) {
    const decay = 2 ** (-age / halfLifeDays);
    denominator += decay;
    const day = state.daily.get(endOrdinal - age);
    if (!day) continue;
    const dailySignal =
      0.55 * Math.min(day.capped / 3, 1)
      + 0.25 * Math.min(day.domains.size / 2, 1)
      + 0.2 * Math.min(day.attentionSeconds / MAX_ATTENTION_SECONDS_PER_TOPIC_DAY_DOMAIN, 1);
    numerator += decay * dailySignal;
  }
  return denominator > 0 ? clamp(numerator / denominator) : 0;
}

/**
 * @param {Array<object>} rows raw chrome.user.history result, held in memory only
 * @param {object} options requestedStart, requestedEnd, requestedDays,
 *   historyQueryLimit, generatedAt, timeZone, and optional retentionLimitDays
 * @returns {object} complete privacy-minimized interest-profile/v2 draft
 */
export function sanitizeChromeHistory(rows, options) {
  if (!Array.isArray(rows)) throw new TypeError("history result must be an array");
  const requiredOptions = ["requestedStart", "requestedEnd", "requestedDays", "historyQueryLimit", "generatedAt", "timeZone"];
  if (!options || requiredOptions.some((key) => options[key] === undefined)) throw new TypeError("sanitizer options are incomplete");
  if (rows.length === 0) throw new Error("no Chrome history rows returned; do not create a profile");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(options.requestedStart) || !/^\d{4}-\d{2}-\d{2}$/.test(options.requestedEnd)) {
    throw new TypeError("requested dates must use YYYY-MM-DD");
  }
  if (!Number.isInteger(options.requestedDays) || options.requestedDays <= 0) throw new TypeError("requestedDays must be positive");
  if (!Number.isInteger(options.historyQueryLimit) || options.historyQueryLimit <= 0 || rows.length > options.historyQueryLimit) {
    throw new TypeError("historyQueryLimit must be positive and bound the result");
  }
  const retentionLimitDays = options.retentionLimitDays ?? 90;
  if (!Number.isInteger(retentionLimitDays) || retentionLimitDays <= 0 || retentionLimitDays > 90) {
    throw new TypeError("retentionLimitDays must be between 1 and 90");
  }

  const events = rows
    .map((row) => {
      const timestamp = rowTimestamp(row);
      return {
        row,
        timestamp,
        day: timestamp === null ? null : dateOnly(timestamp, options.timeZone),
        publicRow: parsePublicRow(row),
        stableTie: stableTieKey(row),
      };
    })
    .filter((event) => (
      event.timestamp !== null
      && event.day >= options.requestedStart
      && event.day <= options.requestedEnd
    ))
    .sort((a, b) => a.timestamp - b.timestamp || a.stableTie.localeCompare(b.stableTie));
  if (events.length === 0) throw new Error("history rows have no usable timestamps; do not create a profile");

  const actualStart = dateOnly(events[0].timestamp, options.timeZone);
  const actualEnd = dateOnly(events.at(-1).timestamp, options.timeZone);
  const startOrdinal = dateOrdinal(actualStart);
  const endOrdinal = dateOrdinal(actualEnd);
  const observedDays = endOrdinal - startOrdinal + 1;
  const longWindowDays = Math.min(Math.max(observedDays, 1), retentionLimitDays);

  const topicState = new Map(TOPIC_RULES.map((rule) => [rule.id, {
    capped: 0,
    recentCapped: 0,
    matchedRows: 0,
    attentionSeconds: 0,
    attentionObservable: 0,
    days: new Set(),
    recentDays: new Set(),
    domains: new Set(),
    capKeys: new Map(),
    attentionCapKeys: new Map(),
    daily: new Map(),
    mostRecentOrdinal: startOrdinal,
    maxDailyCapped: 0,
  }]));

  let publicVisits = 0;
  let matchedPublicVisits = 0;
  let attentionObservableVisits = 0;

  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    if (!event.publicRow) continue;
    publicVisits += 1;
    const day = event.day;
    const ordinal = dateOrdinal(day);
    const bucket = domainBucket(event.publicRow.host);
    const matches = TOPIC_RULES.filter((rule) => rule.patterns.some((pattern) => event.publicRow.text.includes(pattern)));
    if (matches.length === 0) continue;
    matchedPublicVisits += 1;
    const estimatedAttention = attentionEstimate(event, events[index + 1]);
    if (estimatedAttention !== null) attentionObservableVisits += 1;

    for (const rule of matches) {
      const state = topicState.get(rule.id);
      state.matchedRows += 1;
      state.days.add(day);
      state.domains.add(bucket);
      state.mostRecentOrdinal = Math.max(state.mostRecentOrdinal, ordinal);
      if (endOrdinal - ordinal < SHORT_WINDOW_DAYS) state.recentDays.add(day);
      const capKey = `${day}|${bucket}`;
      const prior = state.capKeys.get(capKey) ?? 0;
      let counted = 0;
      if (prior < MAX_VISITS_PER_TOPIC_DAY_DOMAIN) {
        state.capKeys.set(capKey, prior + 1);
        state.capped += 1;
        counted = 1;
        if (endOrdinal - ordinal < SHORT_WINDOW_DAYS) state.recentCapped += 1;
      }

      const daily = state.daily.get(ordinal) ?? { capped: 0, domains: new Set(), attentionSeconds: 0 };
      daily.capped += counted;
      daily.domains.add(bucket);
      if (estimatedAttention !== null) {
        state.attentionObservable += 1;
        const attentionPrior = state.attentionCapKeys.get(capKey) ?? 0;
        const attentionAdded = Math.min(
          estimatedAttention,
          Math.max(0, MAX_ATTENTION_SECONDS_PER_TOPIC_DAY_DOMAIN - attentionPrior),
        );
        if (attentionAdded > 0) {
          state.attentionCapKeys.set(capKey, attentionPrior + attentionAdded);
          state.attentionSeconds += attentionAdded;
          daily.attentionSeconds += attentionAdded;
        }
      }
      state.daily.set(ordinal, daily);
      state.maxDailyCapped = Math.max(state.maxDailyCapped, daily.capped);
    }
  }

  const eligible = TOPIC_RULES.map((rule) => ({ rule, state: topicState.get(rule.id) }))
    .filter(({ state }) => (
      (state.days.size >= 3 && state.domains.size >= 2)
      || (state.recentDays.size >= 2 && state.domains.size >= 2 && state.recentCapped >= 6)
    ));
  if (eligible.length === 0) throw new Error("no stable public-news topic met the evidence threshold; do not create a profile");

  const hasAggregateCounts = rows.some((row) => Number(row?.visitCount) > 1);
  const taxonomyCoverageRatio = publicVisits > 0 ? matchedPublicVisits / publicVisits : 0;
  const attentionCoverageRatio = matchedPublicVisits > 0 ? attentionObservableVisits / matchedPublicVisits : 0;
  const attentionStatus = attentionObservableVisits === 0
    ? "unavailable"
    : hasAggregateCounts || attentionCoverageRatio < 0.5
      ? "limited"
      : "usable";

  const features = eligible.map(({ rule, state }) => {
    const attentionMinutes = state.attentionSeconds / 60;
    const attentionScore = attentionStatus === "unavailable"
      ? 0
      : clamp(Math.log1p(Math.min(attentionMinutes, 90)) / Math.log1p(90));
    const shortScore = decayScore(state, endOrdinal, Math.min(SHORT_WINDOW_DAYS, observedDays), 7);
    const longScore = decayScore(state, endOrdinal, longWindowDays, 30);
    const burstiness = clamp(state.maxDailyCapped / Math.max(state.capped, 1));
    const daySpread = clamp(state.days.size / 14);
    const domainSpread = clamp(state.domains.size / 4);
    const stability = clamp(0.4 * daySpread + 0.25 * domainSpread + 0.2 * (1 - burstiness) + 0.15 * Math.min(state.capped / 20, 1));
    const transient = clamp(0.5 * burstiness + 0.3 * Math.max(shortScore - longScore, 0) + 0.2 * (1 - daySpread));
    const workLike = clamp(0.65 * rule.work_prior + 0.2 * burstiness + 0.15 * (1 - domainSpread));
    const durable = clamp(0.45 * daySpread + 0.25 * domainSpread + 0.2 * stability + 0.1 * (1 - transient));
    const visitSignal = 1 - Math.exp(-state.capped / 12);
    const coverageSignal = clamp(observedDays / 45);
    const rawConfidence = sigmoid(
      -2 + 1.2 * visitSignal + 1.6 * daySpread + 0.8 * domainSpread + 0.6 * attentionScore
      + 0.8 * coverageSignal - transient - 0.6 * workLike,
    );
    const effectiveEvidence = Math.min(50, 0.7 * state.days.size + 0.5 * state.domains.size + 0.2 * [...state.daily.values()].filter((x) => x.attentionSeconds >= 300).length);
    const confidence = Math.min(0.75, ((effectiveEvidence * rawConfidence + 4 * 0.5) / (effectiveEvidence + 4)) * (0.5 + 0.5 * coverageSignal));
    const rawWeight = (
      0.32 * visitSignal + 0.22 * daySpread + 0.14 * domainSpread + 0.12 * attentionScore
      + 0.12 * longScore + 0.08 * shortScore
    ) * rule.news_priority * clamp(1 - 0.25 * workLike - 0.35 * transient, 0.45, 1);
    const trend = observedDays < 14 ? "unknown" : shortScore - longScore >= 0.15 ? "rising" : shortScore - longScore <= -0.15 ? "fading" : "steady";
    const timeHorizon = observedDays < 14
      ? "uncertain"
      : stability >= 0.65 && state.days.size >= 6
        ? "durable"
        : transient >= 0.6 || burstiness >= 0.6
          ? "transient"
          : shortScore > longScore + 0.1
            ? "emerging"
            : "uncertain";
    const intent = workLike >= 0.68 ? "professional" : workLike >= 0.35 ? "mixed" : rule.intent_prior;
    return {
      rule,
      state,
      attentionMinutes,
      attentionScore,
      shortScore,
      longScore,
      trend,
      timeHorizon,
      stability,
      burstiness,
      transient,
      workLike,
      durable,
      confidence,
      rawWeight,
      intent,
    };
  });

  const maxRawWeight = Math.max(...features.map((feature) => feature.rawWeight), 0.001);
  const topics = features
    .map((feature) => {
      const { rule, state } = feature;
      const daysSinceLast = Math.max(0, endOrdinal - state.mostRecentOrdinal);
      const engagedDays = [...state.daily.values()].filter((value) => value.attentionSeconds >= 300).length;
      const attentionBand = feature.attentionScore >= 0.66 ? "high" : feature.attentionScore >= 0.33 ? "medium" : "low";
      return {
        id: rule.id,
        parent_id: rule.parent_id,
        label: rule.label,
        weight: round(clamp(0.15 + 0.55 * (feature.rawWeight / maxRawWeight) + 0.3 * feature.rawWeight)),
        confidence: round(feature.confidence),
        user_confirmed: null,
        news_eligible: true,
        intent: feature.intent,
        time_horizon: feature.timeHorizon,
        news_query_terms: [...rule.news_query_terms],
        preferred_primary_domains: [...rule.preferred_primary_domains],
        rationale: rule.rationale,
        attention: {
          score: round(feature.attentionScore),
          band: attentionBand,
          estimated_minutes_capped: round(feature.attentionMinutes, 1),
          observable_visits: state.attentionObservable,
          coverage_ratio: round(state.matchedRows > 0 ? state.attentionObservable / state.matchedRows : 0),
          engaged_days: engagedDays,
        },
        horizon: {
          short_score: round(feature.shortScore),
          long_score: round(feature.longScore),
          trend: feature.trend,
          stability: round(feature.stability),
          burstiness: round(feature.burstiness),
        },
        intent_scores: {
          durable: round(feature.durable),
          transient: round(feature.transient),
          work_like: round(feature.workLike),
        },
        evidence: {
          capped_visits: state.capped,
          distinct_days: state.days.size,
          domain_diversity: state.domains.size,
          recency_band: recencyBand(daysSinceLast),
        },
      };
    })
    .sort((a, b) => b.weight - a.weight || b.confidence - a.confidence || a.id.localeCompare(b.id));

  const historyLimitHit = rows.length === options.historyQueryLimit;
  const requestedToken = String(options.requestedEnd).replaceAll("-", "");
  return {
    schema_version: "interest-profile/v2",
    profile_id: `personal-news-${requestedToken}-draft-01`,
    generated_at: options.generatedAt,
    coverage: {
      source_kind: "chrome-history-api",
      requested_days: options.requestedDays,
      requested_start: options.requestedStart,
      requested_end: options.requestedEnd,
      actual_start: actualStart,
      actual_end: actualEnd,
      observed_days: observedDays,
      processed_visits: rows.length,
      public_visits: publicVisits,
      excluded_or_downweighted_visits: rows.length - publicVisits,
      retention_limit_days: retentionLimitDays,
      history_query_limit: options.historyQueryLimit,
      history_limit_hit: historyLimitHit,
      result_truncated: historyLimitHit,
      status: observedDays < 14 ? "insufficient" : observedDays <= 45 ? "provisional" : "usable",
    },
    privacy: {
      raw_history_retained: false,
      exact_urls_retained: false,
      exact_titles_retained: false,
      exact_visit_times_retained: false,
      search_queries_retained: false,
      sensitive_attribute_inference: false,
      raw_tokens_copied_to_queries: false,
      raw_tokens_copied_to_profile_text: false,
      raw_history_shared_with_reviewers: false,
      aggregate_only_agent_reviews: true,
      public_search_terms_reviewed: true,
    },
    inference: {
      method: "privacy-safe-history-signals/v2",
      taxonomy_version: "public-news-taxonomy/v2",
      taxonomy_coverage_ratio: round(taxonomyCoverageRatio),
      unmapped_public_visits: Math.max(0, publicVisits - matchedPublicVisits),
      short_window_days: Math.min(SHORT_WINDOW_DAYS, longWindowDays),
      long_window_days: longWindowDays,
      attention: {
        estimator: "adjacent-gap-proxy/v1",
        status: attentionStatus,
        observable_visits: attentionObservableVisits,
        coverage_ratio: round(attentionCoverageRatio),
        per_visit_cap_minutes: MAX_ATTENTION_SECONDS_PER_VISIT / 60,
        session_gap_minutes: MAX_SESSION_GAP_SECONDS / 60,
      },
      calibration: {
        method: "prior-only/v1",
        status: "uncalibrated",
        confidence_cap: 0.75,
      },
      ensemble: {
        status: "not-run",
        review_count: 0,
        role_count: 0,
        max_disagreement: 0,
      },
    },
    languages: ["ja", "en"],
    topics,
    exclusions: {
      topic_ids: [],
      terms: [],
      domains: ["accounts.google.com", "docs.google.com", "drive.google.com", "mail.google.com"],
    },
    source_policy: {
      prefer: ["公式リリースと一次資料", "標準化団体・規制当局・研究機関", "信頼できる専門メディア"],
      deprioritize: ["出典のないまとめ記事", "広告目的のランキング", "未検証のSNS投稿"],
    },
    digest_defaults: {
      lookback_hours: 72,
      max_items: 8,
      max_per_domain: 2,
      language_order: ["ja", "en"],
    },
    approval: { status: "draft", approved_at: null },
  };
}
