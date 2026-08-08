import { useState, type FormEvent } from 'react'
import { PRIORITIES, PRIORITY_LABELS, parseTitle, type Priority } from '../lib/tasks'

type Props = {
  onAdd: (title: string, priority: Priority, tags: string[]) => void
}

export function Composer({ onAdd }: Props) {
  const [value, setValue] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const { title, tags } = parseTitle(value)
    if (!title) return
    onAdd(title, priority, tags)
    setValue('')
  }

  return (
    <form className="composer" onSubmit={submit}>
      <input
        className="composer__input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="やることを入力（#タグ が使えます）"
        aria-label="新しいタスク"
      />
      <select
        className="composer__select"
        value={priority}
        onChange={(event) => setPriority(event.target.value as Priority)}
        aria-label="優先度"
      >
        {PRIORITIES.map((item) => (
          <option key={item} value={item}>
            優先度: {PRIORITY_LABELS[item]}
          </option>
        ))}
      </select>
      <button type="submit" className="composer__submit">
        追加
      </button>
    </form>
  )
}
