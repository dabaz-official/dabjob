/**
 * BOSS 直聘 detail page → CaptureItem.
 *
 * Pure mapping: reads the DOM, returns an object. It does not fetch, does not
 * navigate, does not store, and must stay that way — the ingest endpoint owns
 * deduplication and persistence, which is what lets this file be tested
 * against a saved page instead of a live site.
 *
 * Selectors were written against a real page, not imagined. The fixture in
 * tests/fixtures/boss-detail.html is that page's DOM with every text node
 * replaced by placeholder content, so the structure is verbatim and the
 * fixture publishes nothing about what was browsed.
 */

export const meta = {
  platform: "boss",
  pageKind: "detail",
  version: 1,
};

const SELECTORS = {
  root: ".job-primary .info-primary",
  title: ".info-primary .name h1",
  titleFallback: ".info-primary .name",
  salary: ".info-primary .salary",
  city: ".info-primary .text-city",
  experience: ".info-primary .text-experiece",
  company: ".smallbanner .company-info .name .job-title",
  companyFallback: ".company-info .name",
  description: ".job-detail-section .job-sec-text",
};

const JOB_ID = /\/job_detail\/([0-9a-zA-Z]+)\.html/;

/** True when this page is a posting the adapter understands. */
export function matches(doc) {
  return Boolean(doc.querySelector(SELECTORS.root));
}

/**
 * @param {Document} doc
 * @param {string} [pageUrl] used when the page has no canonical link
 */
export function extract(doc, pageUrl = "") {
  const canonical = doc.querySelector('link[rel="canonical"]');
  const url = (canonical && canonical.getAttribute("href")) || pageUrl || "";
  const match = JOB_ID.exec(url);

  return {
    platform: meta.platform,
    pageKind: meta.pageKind,
    url: url || null,
    // The canonical URL carries the posting id, which is stable across
    // sessions. The page also embeds a securityId; that is session-bound and
    // must never be stored, so nothing here reads it.
    externalId: match ? match[1] : null,
    title: titleOf(doc),
    company: text(doc, SELECTORS.company) || text(doc, SELECTORS.companyFallback),
    city: text(doc, SELECTORS.city),
    salaryText: text(doc, SELECTORS.salary),
    seniority: text(doc, SELECTORS.experience),
    jdText: blockText(doc.querySelector(SELECTORS.description)),
  };
}

/**
 * The title lives in an h1 inside `.name`, next to the salary span. Text
 * first, then the h1's title attribute, then `.name` with the salary taken
 * out — a page that renders the h1 empty should not produce a salary as the
 * job title.
 */
function titleOf(doc) {
  const heading = doc.querySelector(SELECTORS.title);
  const headingText = heading && (heading.textContent || "").replace(/\s+/g, " ").trim();
  if (headingText) {
    return headingText;
  }
  const attribute = heading && heading.getAttribute("title");
  if (attribute && attribute.trim()) {
    return attribute.trim();
  }

  const block = doc.querySelector(SELECTORS.titleFallback);
  if (!block) {
    return null;
  }
  const clone = block.cloneNode(true);
  const salary = clone.querySelector(SELECTORS.salary);
  if (salary) {
    salary.remove();
  }
  const value = (clone.textContent || "").replace(/\s+/g, " ").trim();
  return value || null;
}

function text(doc, selector) {
  const node = doc.querySelector(selector);
  if (!node) {
    return null;
  }
  const value = (node.textContent || "").replace(/\s+/g, " ").trim();
  return value || null;
}

/** Description markup separates lines with <br>, which textContent drops. */
function blockText(node) {
  if (!node) {
    return "";
  }

  const lines = [];
  let current = "";

  for (const child of node.childNodes) {
    if (child.nodeType === 1 && child.nodeName === "BR") {
      lines.push(current);
      current = "";
      continue;
    }
    current += child.textContent || "";
  }
  lines.push(current);

  return lines
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => line.length > 0)
    .join("\n");
}
