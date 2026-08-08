import { useEffect, useMemo, useRef, useState } from 'react'
import { Column } from './components/Column'
import { Composer } from './components/Composer'
import { Progress } from './components/Progress'
import { TaskCard } from './components/TaskCard'
import { Toolbar } from './components/Toolbar'
import { useBoard } from './hooks/useBoard'
import { useTheme } from './hooks/useTheme'
import {
  STATUSES,
  allTags,
  completionRate,
  groupByStatus,
  selectVisible,
  type Priority,
} from './lib/tasks'
import './App.css'

export default function App() {
  const [state, dispatch] = useBoard()
  const { theme, toggle } = useTheme()
  const [query, setQuery] = useState('')
  const [tag, setTag] = useState<string | null>(null)
  const dragging = useRef<string | null>(null)
  const searchRef = useRef<HTMLDivElement>(null)

  const visible = useMemo(() => selectVisible(state.tasks, { query, tag }), [state.tasks, query, tag])
  const columns = useMemo(() => groupByStatus(visible), [visible])
  const tags = useMemo(() => allTags(state.tasks), [state.tasks])
  const rate = completionRate(state.tasks)
  const doneCount = state.tasks.filter((task) => task.status === 'done').length

  // 「/」で検索へフォーカス。入力中は横取りしない。
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.metaKey || event.ctrlKey) return
      const target = event.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      event.preventDefault()
      searchRef.current?.querySelector('input')?.focus()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const addTask = (title: string, priority: Priority, taskTags: string[]) => {
    dispatch({ type: 'add', id: crypto.randomUUID(), now: Date.now(), title, priority, tags: taskTags })
  }

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1 className="app__title">DX Board</h1>
          <p className="app__subtitle">Claude Code on the Web で作ったフロントエンド体験用ボード</p>
        </div>
        <Progress total={state.tasks.length} done={doneCount} rate={rate} />
      </header>

      <Composer onAdd={addTask} />

      <div ref={searchRef}>
        <Toolbar
          query={query}
          onQueryChange={setQuery}
          tags={tags}
          activeTag={tag}
          onTagChange={setTag}
          theme={theme}
          onThemeToggle={toggle}
          onClearDone={() => dispatch({ type: 'clearDone' })}
          doneCount={doneCount}
        />
      </div>

      <main className="board">
        {STATUSES.map((status) => (
          <Column
            key={status}
            status={status}
            count={columns[status].length}
            onDrop={() => {
              const id = dragging.current
              if (id) dispatch({ type: 'move', id, status })
              dragging.current = null
            }}
          >
            {columns[status].map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onAdvance={() => dispatch({ type: 'advance', id: task.id })}
                onRemove={() => dispatch({ type: 'remove', id: task.id })}
                onRename={(title) => dispatch({ type: 'rename', id: task.id, title })}
                onDragStart={() => {
                  dragging.current = task.id
                }}
                onTagClick={(clicked) => setTag((current) => (current === clicked ? null : clicked))}
              />
            ))}
            {columns[status].length === 0 && <li className="column__empty">まだ何もありません</li>}
          </Column>
        ))}
      </main>

      <footer className="app__footer">
        <kbd>/</kbd> で検索・カードをドラッグして移動・タイトルをクリックで編集
      </footer>
    </div>
  )
}
