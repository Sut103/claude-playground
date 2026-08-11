---
name: regex-tester
status: backlog
created: 2026-08-11T14:27:30Z
updated: 2026-08-11T14:37:39Z
progress: 0%
prd: .claude/prds/regex-tester.md
github: https://github.com/Sut103/claude-playground/issues/27
---

# Epic: regex-tester

## Overview

依存ゼロ・ビルドレスの単一ページアプリを、DOM に触れない純粋なロジック層と、その上に乗る薄い UI 層に分けて実装する。ロジック層は ES モジュールとして切り出し `node --test` で覆う。マッチの実行だけは Web Worker に隔離し、メインスレッドがユーザのパターンに巻き込まれないようにする。

作るものは 4 つの純粋モジュール（マッチ・ハイライト範囲・置換・履歴）、1 つの隔離レイヤ（Worker とそのクライアント）、1 つの結線層（UI）である。

## Architecture Decisions

**AD-1: 起動は静的ファイルサーバ経由とする**

`file://` では ES モジュールが読み込めない。Chromium で実測し、`origin 'null'` からのスクリプト取得が CORS で拒否されることを確認済み（同構成を `http://127.0.0.1` で開くとモジュール・Worker とも動作）。

選択肢は「モジュールを諦めて全部を 1 ファイルの classic script に押し込む」か「静的サーバを前提にする」の二択だった。前者を採ると `export` が書けず、ロジック層を `node --test` から import できなくなり NFR-5 と衝突する。後者を採る。`python3 -m http.server` で足り、ビルド工程は増えない。

**AD-2: ロジック層は DOM と Worker の両方から独立させる**

`src/logic/` 配下のモジュールは `document`・`window`・`self` のいずれにも触れない。入力は素の値、出力は素のデータ構造。これにより同じコードを Node のテストからも Worker の中からも import できる。localStorage のような環境依存は、呼び出し側が注入する形にする（履歴モジュールは storage オブジェクトを引数で受け取る）。

**AD-3: データ契約をタスク着手前に固定する**

マッチ結果の形（`MatchResult`, `CaptureGroup`, `Segment` 等）を最初のタスクで JSDoc typedef として確定させる。これが決まっていれば、マッチ・ハイライト・置換・履歴の 4 モジュールは互いのコードを読まずに並行して書ける。この契約が並列化の要である。

**AD-4: Worker は使い捨て可能な資源として扱う**

タイムアウトは `terminate()` でしか止められない（暴走中の Worker は `postMessage` に応答しない）。よってクライアントは Worker を「壊れたら捨てて作り直すもの」として扱い、terminate 後は次のリクエスト時に新しい Worker を遅延生成する。リクエストには連番 ID を振り、terminate 前の古い Worker からの遅延応答は ID 不一致で破棄する。

**AD-5: 描画はテキストノードのみ**

テスト文字列はユーザ入力である。`innerHTML` を使わず、`document.createTextNode` と `textContent` だけで描画する。ハイライトは `<span>` 要素を生成してテキストノードを子に持たせる。これにより XSS の入り込む隙をコード上なくす。

## Technical Approach

### Frontend Components

```
index.html              エントリ。type="module" で ui/app.js を読む
styles.css              レイアウト、ハイライト配色、ダーク前提の配色
src/
  logic/
    types.js            JSDoc typedef 群（データ契約）
    matcher.js          パターン compile → マッチ実行 → 構造化結果
    highlight.js        マッチ配列 → 描画用セグメント列
    replace.js          置換プレビュー生成
    history.js          履歴の追加・重複排除・上限・消去（storage 注入）
  worker/
    regex-worker.js     Worker 本体。logic/matcher, logic/replace を import
    worker-client.js    メインスレッド側。タイムアウト・terminate・再生成
  ui/
    app.js              入力購読、デバウンス、状態、worker 呼び出し
    render.js           DOM 生成（テキストノードのみ）
test/
  *.test.js             node --test 対象
```

**入力とフラグ** — パターン・テスト文字列・置換文字列の 3 テキスト欄と、`g i m s u y` の 6 チェックボックス。変更を購読しデバウンスを挟んで評価をキックする。

**マッチ結果の描画** — `highlight.js` が返すセグメント列（`{kind: "text"|"match"|"zero-width", value, matchIndex}`）を順に DOM 要素へ変換する。`match` は交互に 2 色を割り当てて隣接マッチを区別する。

**キャプチャ表** — マッチごとに行を持つ表。列は「#」「マッチ全体」「開始 index」＋グループ列。名前付きグループは見出しに名前を出す。捕捉されなかったオプショナルグループは空文字と区別して `undefined` と表示する。

**履歴 UI** — パターンとフラグの組の一覧。クリックで入力欄に再適用。全消去ボタン。

### Backend Services

なし。サーバ側の処理は存在しない。静的ファイルの配信のみ。

### Infrastructure

- 配信: 任意の静的ファイルサーバ。README には `python3 -m http.server 8000` を記載する
- テスト: `node --test test/`。`package.json` は置かないか、置く場合も依存を空に保つ
- CI: 本エピックのスコープ外

## Implementation Strategy

**フェーズ 1 — 契約の確定**（直列）

最初のタスクでディレクトリ構造・`index.html` の骨格・`styles.css`・README・そして `logic/types.js` のデータ契約を置く。ここが全ての前提になるため、単独で先に完了させる。

**フェーズ 2 — 純粋ロジックの並行実装**（4 並列）

マッチ・ハイライト・置換・履歴の 4 モジュールを同時に書く。互いにファイルが重ならず、契約が固定されているため衝突しない。各タスクは自身のテストを同時に持つ。

**フェーズ 3 — 隔離レイヤ**（直列）

Worker とクライアントを実装する。マッチと置換のモジュールを import するため、フェーズ 2 の該当タスク完了後に着手する。

**フェーズ 4 — 結線**（直列）

UI を組み、全モジュールを繋ぐ。ここで初めてブラウザ上で動く形になる。

**フェーズ 5 — 受け入れ確認**（直列）

PRD の Success Criteria を 1 つずつ実測で潰す。ReDoS 耐性と XSS 無害化は実ブラウザで確認する。

## Task Breakdown Preview

| # | タスク | 依存 | 並列 |
|---|---|---|---|
| 28 | プロジェクト基盤とデータ契約 | なし | — |
| 29 | マッチエンジン | 28 | ✅ |
| 30 | ハイライト範囲の算出 | 28 | ✅ |
| 31 | 置換プレビュー | 28 | ✅ |
| 32 | 履歴の永続化モデル | 28 | ✅ |
| 33 | Worker 隔離とタイムアウト | 29, 31 | — |
| 34 | UI 結線と描画 | 30, 32, 33 | — |
| 35 | 受け入れ確認 | 34 | — |

8 タスク。フェーズ 2 で 4 並列が効く。

## Dependencies

**外部依存** — なし。

**プラットフォーム前提**
- ブラウザ組み込みの `RegExp`、`Worker`、`localStorage`
- Node.js 18 以上（`node --test` の安定版が要る。実行環境は v22）
- Python 3（動作確認用の静的サーバ。他のサーバでも代替可）

**タスク間依存** — 上表のとおり。28 が全体のクリティカルパス先頭、33 と 34 が合流点。

## Success Criteria (Technical)

1. 静的サーバ配信下で `index.html` を開くと、追加手順なしに全機能が動く
2. `node --test test/` が追加インストールなしで通る
3. `src/logic/` の各モジュールが単体テストで覆われている（マッチ・ハイライト・置換・履歴）
4. `src/logic/` のいずれのファイルにも `document` / `window` / `localStorage` への直接参照がない
5. `(a+)+$` に 30 文字以上の非マッチ文字列を当てたとき、UI がタイムアウトを表示し、その後パターンを直せば通常の結果が返る
6. `<script>alert(1)</script>` をテスト文字列に入れてもスクリプトが実行されず、文字列としてハイライト対象になる
7. 実行時・テスト時ともに外部パッケージへの依存がない
8. PRD の US-1 〜 US-6 の受け入れ基準がすべて満たされている

## Estimated Effort

| タスク | サイズ |
|---|---|
| 28 プロジェクト基盤とデータ契約 | S |
| 29 マッチエンジン | M |
| 30 ハイライト範囲の算出 | S |
| 31 置換プレビュー | S |
| 32 履歴の永続化モデル | S |
| 33 Worker 隔離とタイムアウト | M |
| 34 UI 結線と描画 | M |
| 35 受け入れ確認 | S |

直列に積むと 8 タスク分。フェーズ 2 の 4 並列が効くため、実時間では 5 フェーズ分に圧縮される。

## Tasks Created
- [ ] #28 - プロジェクト基盤とデータ契約 (parallel: false)
- [ ] #29 - マッチエンジン (parallel: true)
- [ ] #30 - ハイライト範囲の算出 (parallel: true)
- [ ] #31 - 置換プレビュー (parallel: true)
- [ ] #32 - 履歴の永続化モデル (parallel: true)
- [ ] #33 - Worker 隔離とタイムアウト (parallel: false)
- [ ] #34 - UI 結線と描画 (parallel: false)
- [ ] #35 - 受け入れ確認 (parallel: false)

Total tasks: 8
Parallel tasks: 4
Sequential tasks: 4
Estimated total effort: 25 hours
