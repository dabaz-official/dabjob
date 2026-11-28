/**
 * Build the bookmarklet.
 *
 * The output is a `javascript:` URL the user drags to the bookmarks bar. It
 * contains the adapter source inline and the ingest token, so it is personal
 * to one machine — which is why it is generated from the local .env and never
 * committed.
 *
 * Usage: node capture/build.mjs <adapter> [--out file]
 *   reads DABJOB_TOKEN and DABJOB_ENDPOINT from the environment
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const snapshotMode = process.argv.includes("--snapshot");
const adapterName = snapshotMode ? "snapshot" : (process.argv[2] ?? "boss-detail");
const adapterPath = join(here, "adapters", `${adapterName}.js`);

const token = process.env.DABJOB_TOKEN ?? "";
const endpoint = process.env.DABJOB_ENDPOINT || "http://127.0.0.1:8000";

if (!token) {
  console.error("DABJOB_TOKEN is not set. Run this through `make bookmarklet`.");
  process.exit(1);
}

const source = snapshotMode ? "" : readFileSync(adapterPath, "utf8");
// The adapter is a module for the tests; in a bookmarklet it is just code.
const inlined = source.replace(/^export /gm, "");

const snapshotSender = `
(async () => {
  try {
    const html = "<!doctype html>\n" + document.documentElement.outerHTML;
    const response = await fetch(${JSON.stringify(endpoint)} + "/api/ingest/snapshot?token=" + encodeURIComponent(${JSON.stringify(token)}) + "&adapter=" + encodeURIComponent(new URL(location.href).pathname.replace(/\\W+/g, "-").slice(0, 40)), {
      method: "POST",
      headers: { "content-type": "text/plain;charset=UTF-8" },
      body: html
    });
    if (!response.ok) {
      alert("DabJob snapshot: 后端返回 " + response.status + "\\n" + (await response.text()).slice(0, 300));
      return;
    }
    const result = await response.json();
    alert("DabJob snapshot: 已保存 " + result.bytes + " 字节\\n" + result.file);
  } catch (error) {
    alert("DabJob snapshot: 请求失败\\n" + error);
  }
})();
`;

const sender = `
(async () => {
  try {
    if (!matches(document)) {
      alert("DabJob: 这个页面不是它能识别的岗位页");
      return;
    }
    const item = extract(document, location.href);
    const response = await fetch(${JSON.stringify(endpoint)} + "/api/ingest/browser?token=" + encodeURIComponent(${JSON.stringify(token)}), {
      method: "POST",
      headers: { "content-type": "text/plain;charset=UTF-8" },
      body: JSON.stringify({ adapter: ${JSON.stringify(adapterName)}, adapter_version: ${"${VERSION}"}, items: [item] })
    });
    if (!response.ok) {
      alert("DabJob: 后端返回 " + response.status + "\\n" + (await response.text()).slice(0, 300));
      return;
    }
    const result = await response.json();
    alert("DabJob: 新增 " + result.accepted + "，重复 " + result.duplicates + "，失败 " + result.failed);
  } catch (error) {
    alert("DabJob: 请求失败\\n" + error + "\\n\\n可能被浏览器的本地网络访问策略拦截了。");
  }
})();
`;

const versionMatch = /version:\s*(\d+)/.exec(inlined);
const version = versionMatch ? versionMatch[1] : "1";

const script = snapshotMode
  ? `(() => {\n${snapshotSender}\n})();`
  : `(() => {\n${inlined}\n${sender.replace("${VERSION}", version)}\n})();`;
const url = "javascript:" + encodeURIComponent(script);

const outDir = join(here, "dist");
mkdirSync(outDir, { recursive: true });
const outFile = join(outDir, `${basename(adapterName)}.txt`);
writeFileSync(outFile, url + "\n", "utf8");

console.log(`adapter : ${adapterName}@${version}`);
console.log(`source  : ${script.length} chars`);
console.log(`url     : ${url.length} chars`);
console.log(`written : ${outFile}`);
console.log("");
console.log("Open the file, copy the single line, create a bookmark whose URL is that line.");
