import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'dx-board:theme'

function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function initialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'light' || stored === 'dark' ? stored : systemTheme()
}

/**
 * テーマを保持し、`<html data-theme>` に反映する。
 * ユーザーが明示的に選ぶまではシステム設定の変更に追従する。
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const [pinned, setPinned] = useState(() => localStorage.getItem(STORAGE_KEY) !== null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    if (pinned) return
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!media) return
    const onChange = (event: MediaQueryListEvent) => setTheme(event.matches ? 'dark' : 'light')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [pinned])

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark'
      localStorage.setItem(STORAGE_KEY, next)
      return next
    })
    setPinned(true)
  }, [])

  return { theme, toggle }
}
