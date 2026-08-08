# 経費承認ルーティング 仕様書 v1.0

監査の基準となる唯一の正典（single source of truth）。
実装・テスト・UI はすべて本書と突合して検証する。

## 1. 入力

| フィールド | 型 | 説明 |
|---|---|---|
| `amount` | 整数（円） | 申請金額。0 以上。 |
| `category` | `travel` \| `entertainment` \| `supplies` \| `other` | 費目 |
| `applicantGrade` | `staff` \| `manager` \| `director` | 申請者の役職 |
| `hasReceipt` | boolean | 領収書の有無 |
| `isForeign` | boolean | 国外取引か（消費税の課税対象外） |

## 2. 承認ルール

- **R1**: `amount` が **100,000 円以上** の場合、`director`（部長）承認を必須とする。
- **R2**: `amount` が **1,000,000 円以上** の場合、`executive`（役員）承認を R1 に **加えて** 必須とする。
- **R3**: `category` が `entertainment`（交際費）の場合、金額に関わらず `compliance`（コンプライアンス）承認を必須とする。
- **R4**: `hasReceipt` が false の場合、`accounting`（経理）の追加確認を必須とする。ただし `amount` が **3,000 円未満** の場合は不要。
- **R5**: 自己承認の禁止。**申請者の役職と同格またはそれ以下**の承認者は承認ステップから除外する。
  - 役職の序列: `staff` < `manager` < `director` < `executive`
  - 例: 申請者が `director` の場合、`manager` 承認も `director` 承認も除外される。
- **R0**: 上記いずれにも該当しない場合、既定の承認者は `manager` とする（R5 の除外対象になりうる）。

### 承認順序（固定）

`manager` → `director` → `compliance` → `accounting` → `executive`

## 3. 消費税の仕入控除額

- 控除税額 = `floor(amount * 10 / 110)`
- ただし `isForeign` が true の場合は課税対象外とし、控除税額は **0** とする。

## 4. 表示要件（UI）

- 金額および控除税額は **1 円単位** で、3 桁区切りのカンマを付して表示する。
- 金額を丸めて表示してはならない。
