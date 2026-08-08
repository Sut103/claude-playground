import { test } from 'node:test';
import assert from 'node:assert/strict';
import { resolveApprovers, deductibleTax, evaluate } from './rules.mjs';

const base = {
  amount: 5_000,
  category: 'supplies',
  applicantGrade: 'staff',
  hasReceipt: true,
  isForeign: false,
};

const req = (over = {}) => ({ ...base, ...over });

test('R0: 既定は manager 承認のみ', () => {
  assert.deepEqual(resolveApprovers(req()), ['manager']);
});

test('R1: 少額(50,000円)では director 承認は不要', () => {
  assert.deepEqual(resolveApprovers(req({ amount: 50_000 })), ['manager']);
});

test('R1: 高額(150,000円)では director 承認が必要', () => {
  assert.deepEqual(resolveApprovers(req({ amount: 150_000 })), [
    'manager',
    'director',
  ]);
});

test('R2: 超高額(1,500,000円)では executive 承認が必要', () => {
  assert.deepEqual(resolveApprovers(req({ amount: 1_500_000 })), [
    'manager',
    'director',
    'executive',
  ]);
});

test('R3: 交際費は金額に関わらず compliance 承認', () => {
  assert.deepEqual(resolveApprovers(req({ category: 'entertainment' })), [
    'manager',
    'compliance',
  ]);
});

test('R4: 領収書なしは accounting 確認', () => {
  assert.deepEqual(resolveApprovers(req({ hasReceipt: false })), [
    'manager',
    'accounting',
  ]);
});

test('R4: 3,000円未満の領収書なしは accounting 不要', () => {
  assert.deepEqual(
    resolveApprovers(req({ amount: 2_999, hasReceipt: false })),
    ['manager'],
  );
});

test('R5: manager 本人の申請では manager 承認を除外', () => {
  assert.deepEqual(
    resolveApprovers(req({ amount: 150_000, applicantGrade: 'manager' })),
    ['director'],
  );
});

// --- 以下は監査（仕様オラクルとの全数照合／UI 照合）で検出された欠陥の回帰テスト ---

test('R1 境界: 99,999円では director 承認は不要', () => {
  assert.deepEqual(resolveApprovers(req({ amount: 99_999 })), ['manager']);
});

test('R1 境界: ちょうど 100,000円で director 承認が必要（以上）', () => {
  assert.deepEqual(resolveApprovers(req({ amount: 100_000 })), [
    'manager',
    'director',
  ]);
});

test('R5: director 本人の申請では manager・director 承認をともに除外', () => {
  assert.deepEqual(
    resolveApprovers(req({ amount: 150_000, applicantGrade: 'director' })),
    [],
  );
});

test('R5: 職能承認者(compliance/accounting)は役職に関わらず除外しない', () => {
  assert.deepEqual(
    resolveApprovers(
      req({
        amount: 150_000,
        category: 'entertainment',
        applicantGrade: 'director',
        hasReceipt: false,
      }),
    ),
    ['compliance', 'accounting'],
  );
});

test('R2 境界: ちょうど 1,000,000円で executive 承認が必要', () => {
  assert.ok(
    resolveApprovers(req({ amount: 1_000_000 })).includes('executive'),
  );
});

test('消費税: 11,000円の控除税額は 1,000円', () => {
  assert.equal(deductibleTax(req({ amount: 11_000 })), 1_000);
});

test('消費税: 端数は切り捨て', () => {
  assert.equal(deductibleTax(req({ amount: 10_000 })), 909);
});

test('消費税: 国外取引は課税対象外', () => {
  assert.equal(deductibleTax(req({ amount: 11_000, isForeign: true })), 0);
});

test('evaluate: 承認者と控除税額をまとめて返す', () => {
  const out = evaluate(req({ amount: 11_000 }));
  assert.deepEqual(out, { approvers: ['manager'], deductibleTax: 1_000 });
});
