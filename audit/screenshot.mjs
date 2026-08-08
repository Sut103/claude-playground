// 監査チャネル②: 状態空間スクリーンショット行列
// UI の主要な分岐を機械的に列挙し、静止画として人間の目視監査に供する。
import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const BASE = 'http://127.0.0.1:8123/public/index.html';
const OUT = path.resolve(import.meta.dirname, 'shots');

/** 監査対象シナリオ。仕様の分岐を網羅するよう設計する。 */
const SCENARIOS = [
  {
    id: '01-boundary-100000',
    title: 'R1 境界: ちょうど 100,000 円',
    note: '仕様は「100,000 円以上で部長承認」。部長承認が出るのが正。',
    state: { amount: 100000, category: 'supplies', grade: 'staff', receipt: true, foreign: false },
  },
  {
    id: '02-boundary-100001',
    title: 'R1 境界: 100,001 円',
    note: '比較対象。境界の 1 円差で挙動が変わるかを目視で対比する。',
    state: { amount: 100001, category: 'supplies', grade: 'staff', receipt: true, foreign: false },
  },
  {
    id: '03-entertainment-no-receipt',
    title: 'R3+R4: 交際費 11,000 円・領収書なし',
    note: 'コンプライアンス承認と経理確認が併記されるか。控除税額 1,000 円。',
    state: { amount: 11000, category: 'entertainment', grade: 'staff', receipt: false, foreign: false },
  },
  {
    id: '04-director-self-approval',
    title: 'R5: 部長本人が 1,500,000 円を申請',
    note: '仕様は「同格以下を除外」。課長承認・部長承認とも消え、役員承認のみが正。',
    state: { amount: 1500000, category: 'travel', grade: 'director', receipt: true, foreign: false },
  },
  {
    id: '05-foreign',
    title: '国外取引 11,000 円',
    note: '控除税額は 0 円が正。',
    state: { amount: 11000, category: 'travel', grade: 'staff', receipt: true, foreign: true },
  },
];

async function applyState(page, state) {
  await page.fill('#amount', String(state.amount));
  await page.selectOption('#category', state.category);
  await page.selectOption('#grade', state.grade);
  await page.setChecked('#receipt', state.receipt);
  await page.setChecked('#foreign', state.foreign);
  await page.dispatchEvent('#amount', 'input');
}

// 環境に事前配置された Chromium を使う（ブラウザの再ダウンロードは行わない）
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
});
const page = await browser.newPage({ viewport: { width: 800, height: 640 }, deviceScaleFactor: 2 });

// 監査信号: コンソールエラー / ページ例外を収集する
const consoleErrors = [];
page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));
page.on('pageerror', (e) => consoleErrors.push(String(e)));

await mkdir(OUT, { recursive: true });
const report = [];

for (const s of SCENARIOS) {
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await applyState(page, s.state);
  await page.waitForTimeout(80);

  const file = path.join(OUT, `${s.id}.png`);
  await page.screenshot({ path: file, fullPage: true });

  // 画面から読み取れる値をテキストとしても抽出し、差分監査を可能にする
  const observed = await page.evaluate(() => ({
    steps: [...document.querySelectorAll('#steps .step')].map((n) => n.textContent.trim()),
    amount: document.getElementById('out-amount').textContent.trim(),
    tax: document.getElementById('out-tax').textContent.trim(),
  }));

  report.push({ id: s.id, title: s.title, note: s.note, state: s.state, observed, file });
  console.log(`[shot] ${s.id}  steps=${JSON.stringify(observed.steps)} amount=${observed.amount} tax=${observed.tax}`);
}

await browser.close();

await writeFile(
  path.join(OUT, 'observed.json'),
  JSON.stringify({ capturedAt: new Date().toISOString(), consoleErrors, report }, null, 2),
);

console.log(`\nconsole errors: ${consoleErrors.length}`);
console.log(`wrote ${report.length} shots to ${OUT}`);
