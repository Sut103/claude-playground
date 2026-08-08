import type { Task } from './tasks'

const BASE = Date.UTC(2026, 7, 8, 9, 0, 0)

/** 初回起動時のサンプルデータ。空の画面を見せないための足場。 */
export const seedTasks: Task[] = [
  {
    id: 'seed-1',
    title: 'SessionStart フックで依存を自動インストール',
    status: 'done',
    priority: 'high',
    tags: ['claude-code', 'dx'],
    createdAt: BASE,
  },
  {
    id: 'seed-2',
    title: 'ボードのドメインロジックを純粋関数に切り出す',
    status: 'done',
    priority: 'medium',
    tags: ['refactor'],
    createdAt: BASE + 1000,
  },
  {
    id: 'seed-3',
    title: 'Vitest でリデューサのユニットテストを書く',
    status: 'doing',
    priority: 'high',
    tags: ['test'],
    createdAt: BASE + 2000,
  },
  {
    id: 'seed-4',
    title: 'ダークモードをシステム設定に追従させる',
    status: 'doing',
    priority: 'low',
    tags: ['ui'],
    createdAt: BASE + 3000,
  },
  {
    id: 'seed-5',
    title: 'Playwright でスクリーンショットを撮って見た目を確認',
    status: 'todo',
    priority: 'high',
    tags: ['claude-code', 'test'],
    createdAt: BASE + 4000,
  },
  {
    id: 'seed-6',
    title: 'キーボードだけでカードを動かせるようにする',
    status: 'todo',
    priority: 'medium',
    tags: ['a11y', 'ui'],
    createdAt: BASE + 5000,
  },
]
