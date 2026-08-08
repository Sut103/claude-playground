// 監査用オラクル
//
// 重要: このファイルは SPEC.md の条文「だけ」を根拠に、実装(src/rules.mjs)を
// 一切参照せずに書き起こす。実装と独立であることが監査価値の源泉であり、
// 人間の監査対象はこの短いオラクルと SPEC.md の突合に絞り込める。

const RANK = { staff: 0, manager: 1, director: 2, executive: 3 };
const ORDER = ['manager', 'director', 'compliance', 'accounting', 'executive'];

// R5 の対象となるのは役職ベースの承認者のみ（compliance / accounting は職能）
const GRADE_APPROVERS = new Set(['manager', 'director', 'executive']);

export function oracleApprovers({ amount, category, applicantGrade, hasReceipt }) {
  const required = new Set();

  required.add('manager');                                  // R0
  if (amount >= 100_000) required.add('director');          // R1: 「以上」
  if (amount >= 1_000_000) required.add('executive');       // R2: 「以上」
  if (category === 'entertainment') required.add('compliance'); // R3
  if (!hasReceipt && amount >= 3_000) required.add('accounting'); // R4

  // R5: 申請者の役職と「同格またはそれ以下」の役職承認者を除外
  for (const role of [...required]) {
    if (GRADE_APPROVERS.has(role) && RANK[role] <= RANK[applicantGrade]) {
      required.delete(role);
    }
  }

  return ORDER.filter((r) => required.has(r));
}

export function oracleDeductibleTax({ amount, isForeign }) {
  if (isForeign) return 0;                       // 仕様 3.
  return Math.floor((amount * 10) / 110);
}

export function oracleEvaluate(request) {
  return {
    approvers: oracleApprovers(request),
    deductibleTax: oracleDeductibleTax(request),
  };
}
