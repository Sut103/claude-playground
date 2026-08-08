import { useEffect, useRef, useState } from 'react'
import { PRIORITY_LABELS, STATUSES, STATUS_LABELS, type Task } from '../lib/tasks'

type Props = {
  task: Task
  onAdvance: () => void
  onRemove: () => void
  onRename: (title: string) => void
  onDragStart: () => void
  onTagClick: (tag: string) => void
}

export function TaskCard({ task, onAdvance, onRemove, onRename, onDragStart, onTagClick }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(task.title)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.select()
  }, [editing])

  const commit = () => {
    onRename(draft)
    setEditing(false)
  }

  const isLast = task.status === STATUSES[STATUSES.length - 1]

  return (
    <li
      className={`card card--${task.priority}`}
      draggable={!editing}
      onDragStart={onDragStart}
      data-testid="task-card"
    >
      <div className="card__head">
        <span className={`badge badge--${task.priority}`}>{PRIORITY_LABELS[task.priority]}</span>
        <button
          type="button"
          className="icon-button"
          onClick={onRemove}
          aria-label={`「${task.title}」を削除`}
        >
          ×
        </button>
      </div>

      {editing ? (
        <input
          ref={inputRef}
          className="card__input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') commit()
            if (event.key === 'Escape') {
              setDraft(task.title)
              setEditing(false)
            }
          }}
          aria-label="タスク名を編集"
        />
      ) : (
        <button
          type="button"
          className="card__title"
          onClick={() => {
            setDraft(task.title)
            setEditing(true)
          }}
        >
          {task.title}
        </button>
      )}

      {task.tags.length > 0 && (
        <ul className="card__tags">
          {task.tags.map((tag) => (
            <li key={tag}>
              <button type="button" className="tag" onClick={() => onTagClick(tag)}>
                #{tag}
              </button>
            </li>
          ))}
        </ul>
      )}

      {!isLast && (
        <button type="button" className="card__advance" onClick={onAdvance}>
          {STATUS_LABELS[task.status === 'todo' ? 'doing' : 'done']} へ →
        </button>
      )}
    </li>
  )
}
