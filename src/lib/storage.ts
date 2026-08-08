import { PRIORITIES, STATUSES, type Priority, type Status, type Task } from './tasks'

const STORAGE_KEY = 'dx-board:v1'

function isTask(value: unknown): value is Task {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.title === 'string' &&
    typeof candidate.createdAt === 'number' &&
    STATUSES.includes(candidate.status as Status) &&
    PRIORITIES.includes(candidate.priority as Priority) &&
    Array.isArray(candidate.tags) &&
    candidate.tags.every((tag) => typeof tag === 'string')
  )
}

/** localStorage から読み出す。壊れた値・古い形式は黙って捨てて null を返す。 */
export function loadTasks(): Task[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    return parsed.filter(isTask)
  } catch {
    return null
  }
}

export function saveTasks(tasks: Task[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks))
  } catch {
    // クォータ超過やプライベートモードでは永続化を諦める（UI は動き続ける）
  }
}
