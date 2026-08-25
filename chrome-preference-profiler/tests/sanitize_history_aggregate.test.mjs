import assert from "node:assert/strict";
import test from "node:test";

import { sanitizeChromeHistory } from "../scripts/sanitize_history_aggregate.mjs";


const options = {
  requestedStart: "2026-06-01",
  requestedEnd: "2026-08-24",
  requestedDays: 84,
  historyQueryLimit: 1000,
  retentionLimitDays: 90,
  generatedAt: "2026-08-24T12:00:00+09:00",
  timeZone: "Asia/Tokyo",
};


function visit(url, title, timestamp, extra = {}) {
  return { url, title, dateVisited: timestamp, isLocal: true, ...extra };
}


function fixtureRows() {
  const rows = [];
  const days = ["2026-08-01", "2026-08-05", "2026-08-12", "2026-08-20"];
  for (const [index, day] of days.entries()) {
    const first = Date.parse(`${day}T01:00:00Z`);
    rows.push(visit("https://autodesk.com/products/fusion-360/overview", "Fusion 360 manufacturing", first));
    rows.push(visit("https://accounts.google.com/signin", "CanaryZephyr private sign in", first + 120_000));
    rows.push(visit("https://solidworks.com/product/whats-new", "SolidWorks mechanical CAD update", first + 240_000));
    rows.push(visit("https://google.com/search?q=CanaryZephyr", "CanaryZephyr search", first + 360_000));
    if (index === 0) {
      rows.push(visit("https://secret.internal/project/CanaryZephyr", "CanaryZephyr private title", first + 480_000));
    }
  }
  rows.push(visit("https://nasa.gov/aerospace", "Aerospace technology", Date.parse("2025-01-01T00:00:00Z")));
  return rows;
}


test("produces deterministic v2 aggregates without raw canaries", () => {
  const rows = fixtureRows();
  const first = sanitizeChromeHistory(rows, options);
  const second = sanitizeChromeHistory([...rows].reverse(), options);
  assert.deepEqual(first, second);
  assert.equal(first.schema_version, "interest-profile/v2");
  assert.equal(first.coverage.actual_start, "2026-08-01");
  assert.equal(first.coverage.actual_end, "2026-08-20");
  const topic = first.topics.find((item) => item.id === "cad-cae-manufacturing");
  assert.ok(topic);
  assert.ok(topic.attention.estimated_minutes_capped > 0);
  assert.ok(topic.attention.observable_visits > 0);
  assert.ok(topic.horizon.stability >= 0 && topic.horizon.stability <= 1);
  const serialized = JSON.stringify(first);
  assert.equal(serialized.includes("CanaryZephyr"), false);
  assert.equal(serialized.includes("secret.internal"), false);
  assert.equal(serialized.includes("https://"), false);
  assert.equal(serialized.includes("2025-01-01"), false);
});


test("marks aggregate history rows as limited attention", () => {
  const rows = fixtureRows().map(({ dateVisited, ...row }) => ({ ...row, lastVisitTime: dateVisited, visitCount: 3 }));
  const profile = sanitizeChromeHistory(rows, options);
  assert.equal(profile.inference.attention.status, "limited");
  assert.ok(profile.inference.attention.coverage_ratio > 0);
});


test("treats counted rows as aggregate even with visit-level hints", () => {
  const rows = fixtureRows().map((row, index) => ({ ...row, visitId: `visit-${index}`, visitCount: 2 }));
  const profile = sanitizeChromeHistory(rows, options);
  assert.equal(profile.inference.attention.status, "limited");
  assert.ok(profile.inference.attention.observable_visits > 0);
});


test("sorts identical URL/title/timestamp collisions by all raw behavior fields", () => {
  const rows = [];
  for (const day of ["2026-08-01", "2026-08-05", "2026-08-12", "2026-08-20"]) {
    const first = Date.parse(`${day}T01:00:00Z`);
    rows.push(visit(
      "https://autodesk.com/products/fusion-360/overview",
      "Collision CAD row",
      first,
      { isLocal: false, transition: "reload", visitCount: 3 },
    ));
    rows.push(visit(
      "https://autodesk.com/products/fusion-360/overview",
      "Collision CAD row",
      first,
      { isLocal: true, transition: "link", visitCount: 1 },
    ));
    rows.push(visit("https://solidworks.com/product/whats-new", "Collision CAD source", first + 120_000));
  }
  const first = sanitizeChromeHistory(rows, options);
  const reversed = sanitizeChromeHistory([...rows].reverse(), options);
  assert.deepEqual(first, reversed);
  assert.equal(first.inference.attention.status, "limited");
  const serialized = JSON.stringify(first);
  assert.equal(serialized.includes("stableTie"), false);
  assert.equal(serialized.includes("Collision CAD row"), false);
});


test("fails closed for invalid retention and empty eligible evidence", () => {
  assert.throws(() => sanitizeChromeHistory(fixtureRows(), { ...options, retentionLimitDays: 91 }));
  assert.throws(() => sanitizeChromeHistory([
    visit("https://example.org/general", "General page", Date.parse("2026-08-10T00:00:00Z")),
  ], options));
});
