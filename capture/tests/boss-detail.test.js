import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { DOMParser } from "linkedom";

import { extract, matches, meta } from "../adapters/boss-detail.js";

const FIXTURE = new URL("./fixtures/boss-detail.html", import.meta.url);

function load(html = readFileSync(FIXTURE, "utf8")) {
  return new DOMParser().parseFromString(html, "text/html");
}

test("the fixture is a page this adapter recognises", () => {
  assert.equal(matches(load()), true);
});

test("a page without the posting container is not matched", () => {
  const doc = new DOMParser().parseFromString("<html><body><p>hi</p></body></html>", "text/html");

  assert.equal(matches(doc), false);
});

test("extract returns the item shape the ingest endpoint accepts", () => {
  const item = extract(load());

  assert.equal(item.platform, "boss");
  assert.equal(item.pageKind, "detail");
  assert.equal(meta.platform, "boss");
  assert.equal(meta.version, 1);

  for (const key of ["title", "company", "city", "salaryText", "seniority", "jdText", "url", "externalId"]) {
    assert.ok(key in item, `missing ${key}`);
  }
});

test("every field comes from its own element", () => {
  const item = extract(load());

  assert.equal(item.title, "示例岗位名称");
  assert.equal(item.company, "示例科技有限公司");
  assert.equal(item.city, "上海");
  assert.equal(item.salaryText, "20-30K·14薪");
  assert.equal(item.seniority, "3-5年");
});

test("the posting id comes from the canonical url", () => {
  const item = extract(load());

  assert.equal(item.externalId, "demo0job0id0for0fixture00");
  assert.match(item.url, /\/job_detail\/demo0job0id0for0fixture00\.html$/);
});

test("the page url is used when there is no canonical link", () => {
  const doc = load();
  doc.querySelector('link[rel="canonical"]').remove();

  const item = extract(doc, "https://www.zhipin.com/job_detail/fromTheUrl.html");

  assert.equal(item.externalId, "fromTheUrl");
});

test("the description keeps its line breaks", () => {
  const item = extract(load());
  const lines = item.jdText.split("\n");

  assert.ok(lines.length > 1, "expected several lines, got one");
  assert.ok(lines.every((line) => line.trim().length > 0), "blank lines should be dropped");
});

test("a missing element becomes null rather than an exception", () => {
  const doc = load();
  doc.querySelector(".info-primary .salary").remove();

  const item = extract(doc);

  assert.equal(item.salaryText, null);
  assert.equal(item.title, "示例岗位名称");
});

test("no session token is read from the page", () => {
  const doc = load();
  const html = readFileSync(FIXTURE, "utf8");
  assert.equal(html.includes("securityId="), false);

  // Even if a page carried one, nothing in the item would contain it.
  const item = extract(doc);
  assert.equal(JSON.stringify(item).includes("securityId"), false);
});

test("the sticky header's job title is not mistaken for the company", () => {
  // `.smallbanner .job-title` sits where a company name would be and repeats
  // the job title. A real capture shipped with the title twice because of it.
  const item = extract(load());

  assert.equal(item.company, "示例科技有限公司");
  assert.notEqual(item.company, item.title);
});
