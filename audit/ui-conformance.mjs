// 監査チャネル④: UI 実描画値 × 仕様オラクル の自動照合
//
// 人間が画面を手で操作して目視確認する行為を機械化する。
// 実ブラウザで DOM に描画された文字列を読み取り、SPEC.md 由来のオラクルが
// 期待する表示文字列と突合する。ロジック層のテストでは絶対に捕まらない
// 「表示層だけのバグ」をここで捕捉する。
import { chromium } from 'playwright';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';
import { oracleEvaluate } from './oracle.mjs';

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:8123/public/index.html';

const LABELS = {
  manager: '課長承認',
  director: '部長承認',
  compliance: 'コンプライアンス承認',
  accounting: '経理確認',
  executive: '役員承認',
};

// SPEC 4.: 1 円単位・3 桁区切り。丸め表示は禁止。
const expectedYen = (n) => '¥' + n.toLocaleString('ja-JP');

const AMOUNTS = [0, 2_999, 3_000, 9_999, 11_000, 99_999, 100_000, 100_001, 1_000_000];
const CATEGORIES = ['travel', 'entertainment', 'supplies'];
const GRADES = ['staff', 'manager', 'director'];

const cases = [];
for (const amount of AMOUNTS)
  for (const category of CATEGORIES)
    for (const applicantGrade of GRADES)
      for (const hasReceipt of [true, false])
        for (const isForeign of [true, false])
          cases.push({ amount, category, applicantGrade, hasReceipt, isForeign });

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
});
const page = await browser.newPage({ viewport: { width: 800, height: 640 } });

const pageErrors = [];
page.on('pageerror', (e) => pageErrors.push(String(e)));

await page.goto(BASE, { waitUntil: 'networkidle' });

const failures = [];

for (const c of cases) {
  await page.fill('#amount', String(c.amount));
  await page.selectOption('#category', c.category);
  await page.selectOption('#grade', c.applicantGrade);
  await page.setChecked('#receipt', c.hasReceipt);
  await page.setChecked('#foreign', c.isForeign);
  await page.dispatchEvent('#amount', 'input');

  const observed = await page.evaluate(() => ({
    steps: [...document.querySelectorAll('#steps .step')].map((n) => n.textContent.trim()),
    amount: document.getElementById('out-amount').textContent.trim(),
    tax: document.getElementById('out-tax').textContent.trim(),
  }));

  const spec = oracleEvaluate(c);
  const expectedSteps =
    spec.approvers.length === 0 ? ['承認不要'] : spec.approvers.map((r) => LABELS[r]);

  const problems = [];
  if (observed.steps.join('|') !== expectedSteps.join('|')) {
    problems.push({ field: '承認ステップ', observed: observed.steps, expected: expectedSteps });
  }
  if (observed.amount !== expectedYen(c.amount)) {
    problems.push({ field: '申請金額表示', observed: observed.amount, expected: expectedYen(c.amount) });
  }
  if (observed.tax !== expectedYen(spec.deductibleTax)) {
    problems.push({ field: '控除税額表示', observed: observed.tax, expected: expectedYen(spec.deductibleTax) });
  }

  if (problems.length) failures.push({ input: c, problems });
}

await browser.close();

// 不一致を「フィールド × 症状」で束ねる
const byField = new Map();
for (const f of failures) {
  for (const p of f.problems) {
    const key = `${p.field}`;
    if (!byField.has(key)) byField.set(key, { field: key, count: 0, sample: { input: f.input, ...p } });
    byField.get(key).count += 1;
  }
}

console.log(`UI 検証ケース数: ${cases.length}`);
console.log(`不一致ケース数 : ${failures.length}`);
console.log(`ページ例外     : ${pageErrors.length}\n`);

for (const g of [...byField.values()].sort((a, b) => b.count - a.count)) {
  console.log(`--- ${g.field}: ${g.count} 件不一致 ---`);
  console.log(`  入力例: ${JSON.stringify(g.sample.input)}`);
  console.log(`  画面表示: ${JSON.stringify(g.sample.observed)}`);
  console.log(`  仕様期待: ${JSON.stringify(g.sample.expected)}`);
}

await writeFile(
  path.resolve(import.meta.dirname, 'ui-conformance-report.json'),
  JSON.stringify(
    { ranAt: new Date().toISOString(), total: cases.length, failed: failures.length, pageErrors, byField: [...byField.values()] },
    null,
    2,
  ),
);

process.exitCode = failures.length === 0 ? 0 : 1;
