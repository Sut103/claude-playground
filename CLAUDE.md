# claude-playground

Claude Code on the Web でのフロントエンド開発 DX を体験するための Vite + React + TypeScript アプリ。

## コマンド

| コマンド | 用途 |
| --- | --- |
| `npm run dev` | 開発サーバー（HMR）を 5173 で起動 |
| `npm run verify` | typecheck → lint → test を一括実行。**変更後は必ずこれを通す** |
| `npm test` / `npm run test:watch` | Vitest（jsdom + Testing Library） |
| `npm run typecheck` | `tsc -b --noEmit`（strict 有効） |
| `npm run lint` | oxlint |
| `npm run screenshot` | 起動中の dev サーバーを実ブラウザで撮影 → `screenshots/` |
| `npm run build` | 型チェック込みの本番ビルド |

## 構成の約束

- `src/lib/` — React に依存しない純粋関数だけを置く。状態遷移は `boardReducer` に集約し、
  ユニットテストはここに厚く書く。UI を経由せずに仕様を固定できる。
- `src/hooks/` — `lib` と React を繋ぐ層。副作用（localStorage、matchMedia）はここに閉じ込める。
- `src/components/` — 表示に専念。ロジックを持たせない。
- `src/test/setup.ts` — jsdom に足りない API（`matchMedia`）の補完と後片付け。

## テストの方針

- ドメインロジックは `src/lib/*.test.ts` で直接叩く。
- UI は `src/App.test.tsx` で **ロール・ラベル経由**で操作する（`getByRole` / `getByLabelText`）。
  クラス名や DOM 構造に依存したセレクタは使わない。アクセシビリティの回帰も同時に拾える。
- 見た目の確認は `npm run screenshot`。コンソールエラーが出た場合は exit 1 で落ちる。

## スクリーンショットを撮る手順

```bash
npm run dev &            # バックグラウンドで起動
npm run screenshot       # light / dark / mobile の 3 枚
```

コンテナには Chromium が同梱されている。`npx playwright install` は不要で、
`scripts/screenshot.mjs` が `PLAYWRIGHT_BROWSERS_PATH` 配下から実行ファイルを探して使う。

## セッション起動フック

`.claude/hooks/session-start.sh` が Claude Code on the Web のセッション開始時に走り、
`npm install` を済ませる。ローカル CLI では何もしない（`CLAUDE_CODE_REMOTE` で分岐）。
