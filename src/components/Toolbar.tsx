import type { Theme } from '../hooks/useTheme'

type Props = {
  query: string
  onQueryChange: (query: string) => void
  tags: string[]
  activeTag: string | null
  onTagChange: (tag: string | null) => void
  theme: Theme
  onThemeToggle: () => void
  onClearDone: () => void
  doneCount: number
}

export function Toolbar({
  query,
  onQueryChange,
  tags,
  activeTag,
  onTagChange,
  theme,
  onThemeToggle,
  onClearDone,
  doneCount,
}: Props) {
  return (
    <div className="toolbar">
      <input
        className="toolbar__search"
        type="search"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="検索…"
        aria-label="タスクを検索"
      />

      <div className="toolbar__tags" role="group" aria-label="タグで絞り込み">
        {tags.map((tag) => {
          const active = activeTag === tag
          return (
            <button
              key={tag}
              type="button"
              className={`chip${active ? ' chip--active' : ''}`}
              aria-pressed={active}
              onClick={() => onTagChange(active ? null : tag)}
            >
              #{tag}
            </button>
          )
        })}
      </div>

      <div className="toolbar__actions">
        <button
          type="button"
          className="ghost-button"
          onClick={onClearDone}
          disabled={doneCount === 0}
        >
          完了を片付ける{doneCount > 0 ? ` (${doneCount})` : ''}
        </button>
        <button
          type="button"
          className="ghost-button"
          onClick={onThemeToggle}
          aria-label={theme === 'dark' ? 'ライトモードに切り替え' : 'ダークモードに切り替え'}
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
    </div>
  )
}
