/**
 * ボードのドメインロジック。
 * React に一切依存しない純粋関数だけを置き、ユニットテストの対象にする。
 */

export const STATUSES = ['todo', 'doing', 'done'] as const
export type Status = (typeof STATUSES)[number]

export const PRIORITIES = ['low', 'medium', 'high'] as const
export type Priority = (typeof PRIORITIES)[number]

export type Task = {
  id: string
  title: string
  status: Status
  priority: Priority
  tags: string[]
  createdAt: number
}

export type BoardState = {
  tasks: Task[]
}

export type Action =
  | { type: 'add'; title: string; priority: Priority; tags: string[]; id: string; now: number }
  | { type: 'remove'; id: string }
  | { type: 'move'; id: string; status: Status }
  | { type: 'advance'; id: string }
  | { type: 'rename'; id: string; title: string }
  | { type: 'setPriority'; id: string; priority: Priority }
  | { type: 'clearDone' }
  | { type: 'replaceAll'; tasks: Task[] }

export const STATUS_LABELS: Record<Status, string> = {
  todo: 'To Do',
  doing: 'In Progress',
  done: 'Done',
}

export const PRIORITY_LABELS: Record<Priority, string> = {
  low: '低',
  medium: '中',
  high: '高',
}

const PRIORITY_WEIGHT: Record<Priority, number> = { high: 0, medium: 1, low: 2 }

/** 入力文字列から `#タグ` を抜き出し、タイトルとタグに分解する。 */
export function parseTitle(input: string): { title: string; tags: string[] } {
  const tags: string[] = []
  const title = input
    .replace(/#([^\s#]+)/g, (_match, tag: string) => {
      if (!tags.includes(tag)) tags.push(tag)
      return ''
    })
    .replace(/\s+/g, ' ')
    .trim()
  return { title, tags }
}

/** 次のステータス。done の次は無い（末端で止まる）。 */
export function nextStatus(status: Status): Status {
  const index = STATUSES.indexOf(status)
  return STATUSES[Math.min(index + 1, STATUSES.length - 1)]
}

export function boardReducer(state: BoardState, action: Action): BoardState {
  switch (action.type) {
    case 'add': {
      const title = action.title.trim()
      if (!title) return state
      const task: Task = {
        id: action.id,
        title,
        status: 'todo',
        priority: action.priority,
        tags: action.tags,
        createdAt: action.now,
      }
      return { tasks: [task, ...state.tasks] }
    }
    case 'remove':
      return { tasks: state.tasks.filter((task) => task.id !== action.id) }
    case 'move':
      return {
        tasks: state.tasks.map((task) =>
          task.id === action.id ? { ...task, status: action.status } : task,
        ),
      }
    case 'advance':
      return {
        tasks: state.tasks.map((task) =>
          task.id === action.id ? { ...task, status: nextStatus(task.status) } : task,
        ),
      }
    case 'rename': {
      const title = action.title.trim()
      if (!title) return state
      return {
        tasks: state.tasks.map((task) => (task.id === action.id ? { ...task, title } : task)),
      }
    }
    case 'setPriority':
      return {
        tasks: state.tasks.map((task) =>
          task.id === action.id ? { ...task, priority: action.priority } : task,
        ),
      }
    case 'clearDone':
      return { tasks: state.tasks.filter((task) => task.status !== 'done') }
    case 'replaceAll':
      return { tasks: action.tasks }
  }
}

export type Filter = {
  query: string
  tag: string | null
}

/** 検索クエリとタグでの絞り込み。優先度の高い順 → 新しい順に整列する。 */
export function selectVisible(tasks: Task[], filter: Filter): Task[] {
  const query = filter.query.trim().toLowerCase()
  return tasks
    .filter((task) => {
      if (filter.tag && !task.tags.includes(filter.tag)) return false
      if (!query) return true
      return (
        task.title.toLowerCase().includes(query) ||
        task.tags.some((tag) => tag.toLowerCase().includes(query))
      )
    })
    .sort(
      (a, b) => PRIORITY_WEIGHT[a.priority] - PRIORITY_WEIGHT[b.priority] || b.createdAt - a.createdAt,
    )
}

export function groupByStatus(tasks: Task[]): Record<Status, Task[]> {
  const grouped: Record<Status, Task[]> = { todo: [], doing: [], done: [] }
  for (const task of tasks) grouped[task.status].push(task)
  return grouped
}

export function allTags(tasks: Task[]): string[] {
  return [...new Set(tasks.flatMap((task) => task.tags))].sort((a, b) => a.localeCompare(b))
}

/** 完了率（0〜100 の整数）。タスクが無いときは 0。 */
export function completionRate(tasks: Task[]): number {
  if (tasks.length === 0) return 0
  const done = tasks.filter((task) => task.status === 'done').length
  return Math.round((done / tasks.length) * 100)
}
