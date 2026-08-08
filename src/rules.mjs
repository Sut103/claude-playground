// 経費承認ルーティング エンジン
// 仕様: SPEC.md v1.0

export const GRADE_ORDER = ['staff', 'manager', 'director', 'executive'];

export const APPROVAL_ORDER = [
  'manager',
  'director',
  'compliance',
  'accounting',
  'executive',
];

const DIRECTOR_THRESHOLD = 100_000;
const EXECUTIVE_THRESHOLD = 1_000_000;
const RECEIPT_EXEMPT_BELOW = 3_000;

// R5 の除外対象は役職ベースの承認者のみ。compliance / accounting は職能であり
// 申請者の役職に関わらず除外しない。
const GRADE_APPROVERS = new Set(['manager', 'director', 'executive']);

function gradeRank(grade) {
  return GRADE_ORDER.indexOf(grade);
}

/**
 * 申請内容から必要な承認ステップを決定する。
 * @returns {string[]} APPROVAL_ORDER に沿って整列済みの承認者リスト
 */
export function resolveApprovers(request) {
  const { amount, category, applicantGrade, hasReceipt } = request;
  const required = new Set();

  // R0: 既定の承認者
  required.add('manager');

  // R1: 高額申請は部長承認（SPEC.md R1 は「100,000 円以上」＝境界を含む）
  if (amount >= DIRECTOR_THRESHOLD) {
    required.add('director');
  }

  // R2: 超高額申請は役員承認
  if (amount >= EXECUTIVE_THRESHOLD) {
    required.add('executive');
  }

  // R3: 交際費はコンプライアンス承認
  if (category === 'entertainment') {
    required.add('compliance');
  }

  // R4: 領収書なしは経理確認
  if (!hasReceipt && amount >= RECEIPT_EXEMPT_BELOW) {
    required.add('accounting');
  }

  // R5: 自己承認の禁止（申請者と同格「以下」の役職承認者を除外）
  for (const approver of [...required]) {
    if (
      GRADE_APPROVERS.has(approver) &&
      gradeRank(approver) <= gradeRank(applicantGrade)
    ) {
      required.delete(approver);
    }
  }

  return APPROVAL_ORDER.filter((role) => required.has(role));
}

/**
 * 仕入控除税額を算出する。
 * @returns {number} 円単位の整数
 */
export function deductibleTax(request) {
  const { amount, isForeign } = request;
  if (isForeign) return 0;
  return Math.floor((amount * 10) / 110);
}

export function evaluate(request) {
  return {
    approvers: resolveApprovers(request),
    deductibleTax: deductibleTax(request),
  };
}
