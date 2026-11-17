import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "../../../../erpnext.official/node_modules/playwright/index.mjs";

const source = await fs.readFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/public/js/list_horizontal_scroll.js", "utf8");
const css = await fs.readFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/public/css/data_import.css", "utf8");
const browser = await chromium.launch({
  headless: true,
  executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
const results = [];

try {
  await page.setContent(`<!doctype html><style>${css}</style><style>
    body { margin: 0; } .result-container { position: relative; margin-left: 320px; width: 900px; height: 500px; }
    .result { width: 900px; height: 450px; overflow-x: auto; overflow-y: hidden; }
    .wide { width: 1600px; height: 20px; }
  </style><main class="result-container"><div class="result"><div class="wide"></div></div></main>`);
  await page.evaluate((script) => { (0, eval)(script); }, source);
  await page.waitForTimeout(500);

  const bar = page.locator(".client-list-horizontal-scroll");
  assert.equal(await bar.count(), 1);
  const state = await bar.evaluate((node) => ({
    position: getComputedStyle(node).position,
    left: node.getBoundingClientRect().left,
    right: window.innerWidth - node.getBoundingClientRect().right,
    bottom: window.innerHeight - node.getBoundingClientRect().bottom,
    hidden: node.hidden,
  }));
  assert.equal(state.position, "fixed");
  assert.ok(state.left >= 319 && state.left <= 321);
  assert.ok(state.right >= 59 && state.right <= 61);
  assert.equal(state.bottom, 0);
  assert.equal(state.hidden, false);
  results.push({ name: "视口固定横向滚动条", status: "passed", details: "滚动条固定在窗口底部，并与列表内容区左右边界对齐" });

  await bar.evaluate((node) => { node.scrollLeft = 180; node.dispatchEvent(new Event("scroll")); });
  assert.equal(await page.locator(".result").evaluate((node) => node.scrollLeft), 180);
  await page.locator(".result").evaluate((node) => { node.scrollLeft = 260; node.dispatchEvent(new Event("scroll")); });
  assert.equal(await bar.evaluate((node) => node.scrollLeft), 260);
  results.push({ name: "双向滚动同步", status: "passed", details: "固定代理条与原列表横向位置保持同步" });

  await page.screenshot({ path: "/tmp/fixed-horizontal-scroll-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(100);
  const mobileState = await bar.evaluate((node) => ({ position: getComputedStyle(node).position, left: node.getBoundingClientRect().left, right: window.innerWidth - node.getBoundingClientRect().right }));
  assert.equal(mobileState.position, "fixed");
  assert.ok(mobileState.left >= 0 && mobileState.right >= 0);
  results.push({ name: "移动端固定条", status: "passed", details: "窄屏下仍固定在视口底部，不超出视口" });
  await page.screenshot({ path: "/tmp/fixed-horizontal-scroll-mobile.png", fullPage: true });
  console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
  await browser.close();
}
