import { useEffect, useReducer } from 'react'
import { boardReducer, type BoardState } from '../lib/tasks'
import { loadTasks, saveTasks } from '../lib/storage'
import { seedTasks } from '../lib/seed'

function init(): BoardState {
  const stored = loadTasks()
  return { tasks: stored && stored.length > 0 ? stored : seedTasks }
}

/** リデューサと localStorage 永続化を束ねる、UI 側の唯一の入口。 */
export function useBoard() {
  const [state, dispatch] = useReducer(boardReducer, undefined, init)

  useEffect(() => {
    saveTasks(state.tasks)
  }, [state.tasks])

  return [state, dispatch] as const
}
