// 監査チャネル③: 仕様オラクルとの全数差分照合 (differential conformance test)
//
// 入力空間を境界値中心に総当りし、実装 evaluate() とオラクル oracleEvaluate() の
// 出力差分を列挙する。人間は「差分表」だけを読めばよく、実装全文を読む必要がない。
import { writeFile } from 'node:fs/promises';
import path from 'node:path';
import { evaluate } from '../src/rules.mjs';
import { oracleEvaluate } from './oracle.mjs';

// 境界値とその前後を明示的に含める（等号の取り違えを検出するため）
const AMOUNTS = [
  0, 1, 2_999, 3_000, 3_001,
  10_000, 11_000, 50_000,
  99_999, 100_000, 100_001,
  500_000,
  999_999, 1_000_000, 1_000_001,
  5_000_000,
];
const CATEGORIES = ['travel', 'entertainment', 'supplies', 'other'];
const GRADES = ['staff', 'manager', 'director'];
const BOOLS = [true, false];

const cases = [];
for (const amount of AMOUNTS)
  for (const category of CATEGORIES)
    for (const applicantGrade of GRADES)
      for (const hasReceipt of BOOLS)
        for (const isForeign of BOOLS)
          cases.push({ amount, category, applicantGrade, hasReceipt, isForeign });

const divergences = [];
for (const c of cases) {
  const actual = evaluate(c);
  const expected = oracleEvaluate(c);

  const approversDiff =
    actual.approvers.join('>') !== expected.approvers.join('>');
  const taxDiff = actual.deductibleTax !== expected.deductibleTax;

  if (approversDiff || taxDiff) {
    divergences.push({ input: c, actual, expected, approversDiff, taxDiff });
  }
}

// 差分は件数が多くなりうるので、原因パターンごとに束ねて人間に提示する
const groups = new Map();
for (const d of divergences) {
  const key = JSON.stringify({
    a: d.actual.approvers,
    e: d.expected.approvers,
    tax: d.taxDiff,
  });
  if (!groups.has(key)) groups.set(key, { sample: d, count: 0 });
  groups.get(key).count += 1;
}

const summary = [...groups.values()]
  .sort((x, y) => y.count - x.count)
  .map(({ sample, count }) => ({
    count,
    sampleInput: sample.input,
    actualApprovers: sample.actual.approvers,
    expectedApprovers: sample.expected.approvers,
    actualTax: sample.actual.deductibleTax,
    expectedTax: sample.expected.deductibleTax,
  }));

console.log(`検証ケース数: ${cases.length}`);
console.log(`差分件数    : ${divergences.length}`);
console.log(`差分パターン: ${summary.length}\n`);

for (const [i, s] of summary.entries()) {
  console.log(`--- パターン ${i + 1} (${s.count} 件) ---`);
  console.log(`  入力例  : ${JSON.stringify(s.sampleInput)}`);
  console.log(`  実装    : approvers=${JSON.stringify(s.actualApprovers)} tax=${s.actualTax}`);
  console.log(`  仕様期待: approvers=${JSON.stringify(s.expectedApprovers)} tax=${s.expectedTax}`);
}

await writeFile(
  path.resolve(import.meta.dirname, 'conformance-report.json'),
  JSON.stringify(
    { ranAt: new Date().toISOString(), total: cases.length, divergences: divergences.length, patterns: summary },
    null,
    2,
  ),
);

process.exitCode = divergences.length === 0 ? 0 : 1;
