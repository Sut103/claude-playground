---
name: regex-tester
status: backlog
created: 2026-08-11T14:30:55Z
updated: 2026-08-11T14:44:54Z
progress: 0%
prd: .claude/prds/regex-tester.md
github:
---

# Epic: regex-tester

## Overview

依存ゼロの正規表現テスターを、`file://` で直接開ける静的ファイル群として実装する。ブラウザ組み込みの `RegExp` を評価エンジンとして使い、その結果を「マッチ範囲のハイライト」「キャプチャグループ表」「置換プレビュー」の 3 ビューに描画する。入力は localStorage に保存する。

技術的な核心は 2 点に絞られる。

1. **評価結果を単一のデータ構造に正規化すること。** `RegExp.prototype.exec` の反復（幅ゼロマッチ、`u` フラグ下のサロゲートペア、`y` フラグの sticky 挙動、件数上限）を 1 箇所に閉じ込め、下流の 3 ビューは正規化済みのマッチレコード列だけを受け取る。ここを分離できれば、ビューは互いに独立して実装・テストできる。
2. **描画を DOM 非依存の純粋関数と DOM 操作に分けること。** ハイライトは「マッチ範囲の列 → セグメント列」という純粋な変換と、「セグメント列 → DOM 要素」という副作用に分かれる。前者は DOM なしで単体テストでき、境界条件（隣接マッチ、幅ゼロ、マッチなし）の検証はここに集約される。

## Architecture Decisions

### AD-1: ES Modules を使わず、classic script + 単一グローバル名前空間で層を分割する

PRD の C-3 で保留した論点を実測で決着させた。Chromium で `file://` から HTML を開いた場合の挙動を検証した結果:

| 読み込み方式 | 結果 |
|---|---|
| classic `<script src="lib.js">` | ✅ 読み込み成功 |
| `<script type="module">` + `import './mod.js'` | ❌ CORS で失敗（`Access to script ... from origin 'null' has been blocked`） |

`file://` のオリジンは `null` として扱われ、モジュール読み込みは CORS チェックを通らない。一方 classic script はチェック対象外で読み込める。

**決定**: 各層を独立した `.js` ファイルに置き、IIFE で単一のグローバル名前空間 `window.RT` に登録する。`index.html` が `<script src>` で順に読み込む。

```js
// src/evaluate.js
(function (RT) {
  RT.evaluate = function (pattern, flags, text) { /* ... */ };
})(window.RT);
```

この決定は 3 つの要件を同時に満たす。NFR-3.1（`file://` で動く）、NFR-3.3（純粋ロジックが DOM 非依存で単体テスト可能）、そして並列実装（1 タスク = 1 ファイル所有で衝突しない）。

**却下した代替案**: ES Modules を使い、テストとローカル利用を `python3 -m http.server` 経由にする案。SC-9「サーバなしで `file://` から全機能が動作する」を満たせないため却下。ビルドで単一ファイルにバンドルする案も、C-1（ビルドツールを使わない）に反するため却下。

### AD-2: 評価結果を「マッチレコード列」に正規化し、これを唯一の下流契約にする

`exec()` の戻り値をそのまま下流に流すと、各ビューが `lastIndex` の反復ロジックや `groups` の `undefined` 判定を個別に持ってしまう。評価層が以下の形に正規化し、ビューはこれだけを読む。

```js
// 成功時
{
  ok: true,
  matches: [
    {
      index: 4,              // 開始インデックス
      end: 9,                // 終了インデックス（index + match[0].length）
      match: "hello",        // 全体一致（match[0]）
      groups: [              // 番号付きグループ（$1 から順）
        { label: "$1", value: "ell", participated: true },
        { label: "$2", value: undefined, participated: false }
      ],
      named: [               // 名前付きグループ
        { label: "word", value: "ell", participated: true }
      ]
    }
  ],
  truncated: false           // 件数上限で打ち切ったか
}
// 失敗時
{ ok: false, error: "Invalid regular expression: /(/: Unterminated group" }
```

`participated` を明示的に持たせるのが要点。`undefined`（グループが一致に参加しなかった）と `""`（参加したが空文字を捕捉した）は意味が違い、FR-3.3 はこの区別の表示を要求している。ビュー側で `=== undefined` を判定させると 3 箇所に同じ判定が散るため、評価層で 1 度だけ判定する。

### AD-3: 反復の安全装置を評価層に集約する

無限ループと暴走の防御を、評価層の反復ループ 1 箇所に置く。

- **幅ゼロマッチ**: `match[0].length === 0` のとき `lastIndex` が進まず無限ループになる。手動で進める（FR-1.3）
- **サロゲートペア**: `u` フラグ有効時にコードユニット単位で進めるとサロゲートペアを割り、不正な位置から再開する。`codePointAt` の結果が `0xFFFF` を超えるなら 2 進める（FR-1.4）
- **件数上限**: 10,000 件で打ち切り、`truncated: true` を返す（FR-1.5）
- **`y` フラグ**: sticky では `lastIndex` の位置でしか一致しないため、一致失敗で即座に反復を終える

これらは全て「反復の制御」であり、ビューには一切漏らさない。

### AD-4: 描画は「純粋な区間変換」と「DOM 生成」に分割する

ハイライトを 2 段構えにする。

- **`RT.buildSegments(text, matches)`** — 純粋関数。マッチ範囲の列から `[{ kind: "plain"|"match"|"empty", text, matchIndex }]` のセグメント列を返す。DOM に触らない。隣接マッチ、幅ゼロ、マッチなし、文字列末尾のマッチといった境界条件のテストは全てここに集まる
- **`RT.renderHighlight(container, segments)`** — DOM 生成のみ。`createElement` と `textContent` で組み立てる

`textContent` に文字列を渡すことで、HTML エスケープは**ブラウザに任せる**。`innerHTML` + 手書きエスケープ関数は、エスケープ漏れが直接 XSS になる。`textContent` なら markup が解釈される経路自体が存在しない。FR-2.2 は「`<`, `>`, `&`, `"`, `'` をエスケープする」と書かれているが、要件の意図は NFR-2.1（markup が実行されない）であり、`textContent` はそれをより強く保証する。エスケープ関数も併せて実装するが、用途は「置換結果を `<pre>` に流し込む際の表示」に限定せず、同じく `textContent` を使う。

### AD-5: テストは 2 層構成、いずれもプリインストール済みの Chromium で動かす

- **単体テスト**: `tests/unit.html` を `file://` で開くと、純粋関数（`evaluate`, `buildSegments`, `escape`, `replace` の展開結果, `storage` のシリアライズ）に対するアサーションが走り、結果を DOM に出力する。ブラウザで直接開いても読めるし、Playwright から結果を読み取ることもできる
- **E2E テスト**: `tests/e2e.spec.js` を Playwright の Node API（`require('playwright')`）で実行する。`@playwright/test` のテストランナーは使わず、素の `chromium.launch()` + 自前の assert で書く

**`@playwright/test` を使わない理由**: `playwright` は `/opt/node22/lib/node_modules` にグローバル配置されており、`NODE_PATH=/opt/node22/lib/node_modules` を付ければ `require('playwright')` で解決できることを確認済み。一方 `@playwright/test` は解決できなかった。プロジェクトに `npm install` を持ち込まない（C-4）ため、解決できるものだけを使う。

### AD-6: DOM のコンテナ ID を最初のタスクで全て確定させる

`index.html` を複数タスクが編集すると衝突する。スキャフォールドのタスクで、全ビューの入力欄とコンテナ要素の `id` を確定させ、以降のタスクは**自分の描画モジュールだけを触る**。これが並列実行の前提条件になる。

確定させる ID: `#pattern`, `#flags-g`〜`#flags-y`, `#test-text`, `#replacement`, `#pattern-display`, `#error`, `#highlight`, `#groups`, `#replace-output`, `#match-count`, `#truncated-notice`, `#reset`

## Technical Approach

### Frontend Components

すべてがフロントエンドである。ファイル構成と責務:

```
regex-tester/
├── index.html                  # アプリシェル。全 DOM コンテナと script 読み込み順を定義
├── styles.css                  # レイアウトとハイライトの配色
├── src/
│   ├── namespace.js            # window.RT = {} の初期化（最初に読み込む）
│   ├── evaluate.js             # FR-1: RegExp 構築と exec 反復 → マッチレコード列
│   ├── segments.js             # FR-2.1/2.4: マッチ範囲 → セグメント列（純粋）+ escape
│   ├── highlight.js            # FR-2.3/2.5/2.6: セグメント列 → DOM
│   ├── groups.js               # FR-3: マッチレコード列 → グループ表 DOM
│   ├── replace.js              # FR-5: 置換プレビュー
│   ├── storage.js              # FR-6: localStorage 保存・復元・フォールバック
│   └── app.js                  # FR-4: フラグ制御と全体の結線、入力イベント → 再評価 → 再描画
└── tests/
    ├── unit.html               # 単体テストランナー（file:// で開ける）
    ├── unit.js                 # 純粋関数のアサーション
    ├── assert.js               # 最小限の assert ヘルパ
    └── e2e.spec.js             # Playwright E2E（Node 実行）
```

**層の依存方向**: `app.js` → 各機能モジュール → `namespace.js`。機能モジュール間の依存は `highlight.js` → `segments.js` の 1 本のみ（セグメント列の形を介する）。それ以外は互いを知らない。

**再描画の流れ**: 入力イベント → `app.js` が `evaluate()` を呼ぶ → 結果を `highlight` / `groups` / `replace` の 3 モジュールに渡す → 各モジュールが自分のコンテナを描画。エラー時は 3 モジュールすべてに「空状態」を描かせる（FR-2.6 / FR-3.4 / FR-5.3）。

### Backend Services

**なし。** PRD の C-5 でバックエンドを持たないことを制約として確定済み。サーバサイドのコードを書かない。評価は全てブラウザ内の `RegExp` で行い、入力はブラウザ外に出ない（NFR-2.2）。

この判断の帰結として、外部通信を行うコードが 1 行も存在しないため、SC-8（外部通信ゼロ）は「ネットワークリクエストを監視して 0 件を確認する」という受動的な検証で足りる。

### Infrastructure

**デプロイ基盤なし。** 成果物は静的ファイル群で、`index.html` を開くこと自体が実行手段である。ビルド、バンドル、トランスパイル、パッケージインストールのいずれも行わない（C-1）。

開発時のみ以下を使う。

- **Chromium** — `/opt/pw-browsers/chromium`（プリインストール済み）
- **Playwright** — `/opt/node22/lib/node_modules/playwright`。実行時に `NODE_PATH=/opt/node22/lib/node_modules` を指定する
- **テスト実行**: `tests/run.sh` を用意し、単体テスト（`unit.html` を Playwright で開いて結果を読む）と E2E を通しで回す

CI は本エピックのスコープに含めない。

## Implementation Strategy

3 フェーズに分ける。フェーズ 2 が並列実行の本体になる。

**フェーズ 1 — 契約の確定（直列、1 タスク）**
`index.html` の DOM コンテナ ID、`window.RT` 名前空間、マッチレコードのデータ形、テストハーネスを確定させる。ここで決めた契約が以降の全タスクの前提になるため、単独で先行させる。並列化の余地はなく、するべきでもない。

**フェーズ 2 — 機能モジュールの並列実装（6 タスク並列）**
評価コア、セグメント変換、ハイライト描画、グループ表、置換プレビュー、永続化を同時に進める。各タスクは自分の `.js` ファイル 1 つと、`tests/unit.js` 内の自分の担当セクションのみを触る。`index.html` と `app.js` には触らない。

フェーズ 1 でマッチレコードの形を確定させてあるため、下流のビュー実装は評価コアの完成を待たない。ビュー側はフィクスチャ（手書きのマッチレコード）に対してテストを書ける。これが並列化を成立させている要点である。

**フェーズ 3 — 結線と検証（直列、2 タスク）**
`app.js` でイベントとモジュールを繋ぎ、フラグ制御を実装する。その後 E2E で 6 ユーザーストーリーと NFR（性能、XSS、無限ループ耐性、通信ゼロ）を検証する。

**リスクと緩和**
- *セグメント列の形が実装中に変わる* — フェーズ 1 で形を決め、フィクスチャをコミットしておく。変更が必要になった場合は `segments.js` と `highlight.js` の 2 タスク間の調整で済む
- *性能要件（100ms / 1,000 マッチ）を素朴な DOM 生成で満たせない* — フェーズ 3 で計測し、未達なら `DocumentFragment` への一括構築に切り替える。最初から最適化はしない
- *`tests/unit.js` が 6 タスクの同時編集で衝突する* — ファイルを分割せず、タスクごとに担当セクションを追記のみ行う規約にする。追記位置が異なれば git は自動マージできる

## Task Breakdown Preview

9 タスク。フェーズ 2 の 6 タスクが並列。

| # | タスク | 主な成果物 | 依存 | 並列 | 規模 |
|---|---|---|---|---|---|
| 001 | スキャフォールド、DOM 契約、テストハーネス | `index.html`, `styles.css`, `src/namespace.js`, `tests/{assert.js,unit.html,run.sh}`, マッチレコードのフィクスチャ | — | ❌ | S |
| 002 | 評価コア — `RegExp` 構築と exec 反復 | `src/evaluate.js` | 001 | ✅ | M |
| 003 | セグメント変換とエスケープ（純粋） | `src/segments.js` | 001 | ✅ | M |
| 004 | ハイライト描画（DOM） | `src/highlight.js` | 001 | ✅ | M |
| 005 | グループ表描画 | `src/groups.js` | 001 | ✅ | S |
| 006 | 置換プレビュー | `src/replace.js` | 001 | ✅ | S |
| 007 | 永続化とフォールバック | `src/storage.js` | 001 | ✅ | S |
| 008 | 結線とフラグ制御 | `src/app.js`, `index.html` の script 追加 | 002–007 | ❌ | M |
| 009 | E2E スイートと NFR 検証 | `tests/e2e.spec.js` | 008 | ❌ | L |

**要件のカバレッジ**: 001（AD-6, NFR-4.1）/ 002（FR-1 全項, NFR-1.2）/ 003（FR-2.1, FR-2.2, FR-2.4）/ 004（FR-2.3, FR-2.5, FR-2.6, NFR-2.1）/ 005（FR-3 全項）/ 006（FR-5 全項）/ 007（FR-6 全項）/ 008（FR-4 全項, NFR-4.2）/ 009（SC-2〜SC-9）

## Dependencies

### タスク間の依存

- **001 が全タスクをブロックする。** DOM コンテナ ID、名前空間、マッチレコード形、テストハーネスが揃わないと他が始まらない
- **002–007 は相互に独立。** ただし 004 は 003 が定義するセグメント列の形に依存する。形はフェーズ 1 で確定しフィクスチャで固定するため、実装の同時進行は可能
- **008 は 002–007 の全完了を待つ。** 結線対象が揃っていないと意味がない
- **009 は 008 を待つ。** 結線後のアプリに対する E2E だから

### ファイル所有と衝突

各タスクが排他的に所有するファイルを割り当てることで、`conflicts_with` を空にできる。

| ファイル | 所有タスク |
|---|---|
| `index.html`, `styles.css` | 001（作成）、008（script タグ追加のみ） |
| `src/namespace.js` | 001 |
| `src/evaluate.js` | 002 |
| `src/segments.js` | 003 |
| `src/highlight.js` | 004 |
| `src/groups.js` | 005 |
| `src/replace.js` | 006 |
| `src/storage.js` | 007 |
| `src/app.js` | 008 |
| `tests/unit.js` | 002–007 が各自のセクションを追記 |
| `tests/e2e.spec.js` | 009 |

`index.html` のみ 001 と 008 の両方が触るため、008 の編集を「script タグの追加のみ」に限定する。008 はフェーズ 3 の直列タスクなので、並列衝突は起きない。

### 外部依存

実行時はゼロ。開発時は PRD の D-1〜D-3（Chromium、Playwright、git / gh）のみ。追加インストールは行わない。

## Success Criteria (Technical)

PRD の SC-1〜SC-9 を技術的な検証手段に落とす。

| PRD | 技術的な合格条件 | 検証手段 |
|---|---|---|
| SC-1 | `evaluate`, `buildSegments`, `escape`, 置換展開, storage シリアライズの単体テストが全 green。US-1〜US-5 の受け入れ条件を網羅 | `tests/unit.html` を Playwright で開き、失敗数 0 を確認 |
| SC-2 | 6 ユーザーストーリーに対応する E2E シナリオが全 green | `tests/e2e.spec.js` |
| SC-3 | `a*` / `(?:)` / `^` を 10,000 文字に適用し 5 秒以内に描画完了 | E2E。`page.waitForFunction` にタイムアウト 5000ms |
| SC-4 | `<img src=x onerror=...>` と `<script>` を 3 入力欄すべてに投入し、`dialog` イベント 0 件かつ注入スクリプト由来のグローバル変数が未定義 | E2E。`page.on('dialog')` を監視 |
| SC-5 | 10,000 文字 / 1,000 マッチで入力から描画完了まで 100ms 以内 | E2E。`performance.now()` で計測 |
| SC-6 | 4 項目を入力 → `page.reload()` → 全項目が一致 | E2E |
| SC-7 | localStorage に不正な JSON を書いた状態で起動し、`pageerror` 0 件かつ初期状態が表示される | E2E |
| SC-8 | E2E 実行中の `request` イベントのうち、`file://` 以外のスキームが 0 件 | E2E。`page.on('request')` を監視 |
| SC-9 | `file://` で `index.html` を開いて全機能が動作 | E2E がそもそも `file://` で実行される |

**追加の技術的合格条件**

- TC-1: `src/` 配下の純粋ロジックファイル（`evaluate.js`, `segments.js`）に `document` / `window.localStorage` への参照が存在しない（grep で検証）
- TC-2: 全 `.js` ファイルが IIFE でラップされ、`window.RT` 以外のグローバルを作らない
- TC-3: 外部 URL を含む文字列（`http://`, `https://`, `//cdn`）がソース中に存在しない（NFR-3.2 の静的検証）

## Estimated Effort

| フェーズ | タスク | 規模 |
|---|---|---|
| 1. 契約の確定 | 001 | S ×1 |
| 2. 並列実装 | 002–007 | M ×3, S ×3 |
| 3. 結線と検証 | 008–009 | M ×1, L ×1 |

**合計**: S ×4, M ×4, L ×1 の 9 タスク。

**クリティカルパス**: 001 → (002–007 のうち最も重いもの) → 008 → 009。フェーズ 2 を 6 並列で回せる場合、直列実行に対して壁時計時間はおよそ 4 段分に短縮される。

**最も不確実なのは 009。** 性能（SC-5）と無限ループ耐性（SC-3）は実測するまで達成可否が分からず、未達なら 003/004 への差し戻しが発生する。ここに L を積んでいる。

## Tasks Created
- [ ] 001.md - スキャフォールド、DOM 契約、テストハーネス (parallel: false)
- [ ] 002.md - 評価コア — RegExp 構築と exec 反復 (parallel: true)
- [ ] 003.md - セグメント変換と HTML エスケープ（純粋関数） (parallel: true)
- [ ] 004.md - ハイライト描画（DOM） (parallel: true)
- [ ] 005.md - グループ表描画 (parallel: true)
- [ ] 006.md - 置換プレビュー (parallel: true)
- [ ] 007.md - 永続化とフォールバック (parallel: true)
- [ ] 008.md - 結線とフラグ制御 (parallel: false)
- [ ] 009.md - E2E スイートと NFR 検証 (parallel: false)

Total tasks: 9
Parallel tasks: 6
Sequential tasks: 3
Estimated total effort: 38 hours
