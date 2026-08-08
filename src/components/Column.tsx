import { useState, type ReactNode } from 'react'
import { STATUS_LABELS, type Status } from '../lib/tasks'

type Props = {
  status: Status
  count: number
  onDrop: () => void
  children: ReactNode
}

export function Column({ status, count, onDrop, children }: Props) {
  const [over, setOver] = useState(false)

  return (
    <section
      className={`column${over ? ' column--over' : ''}`}
      aria-labelledby={`column-${status}`}
      onDragOver={(event) => {
        event.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setOver(false)
        onDrop()
      }}
    >
      <header className="column__head">
        <h2 id={`column-${status}`}>{STATUS_LABELS[status]}</h2>
        <span className="column__count" aria-label={`${count} 件`}>
          {count}
        </span>
      </header>
      <ul className="column__list">{children}</ul>
    </section>
  )
}
