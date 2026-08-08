import { beforeEach, describe, expect, it, vi } from 'vitest'
import { loadTasks, saveTasks } from './storage'
import type { Task } from './tasks'

const valid: Task = {
  id: 'a',
  title: 'タスク',
  status: 'todo',
  priority: 'high',
  tags: ['ui'],
  createdAt: 1,
}

describe('storage', () => {
  beforeEach(() => localStorage.clear())

  it('保存したものをそのまま読み戻せる', () => {
    saveTasks([valid])
    expect(loadTasks()).toEqual([valid])
  })

  it('未保存なら null', () => {
    expect(loadTasks()).toBeNull()
  })

  it('壊れた JSON は null', () => {
    localStorage.setItem('dx-board:v1', '{壊れている')
    expect(loadTasks()).toBeNull()
  })

  it('配列でなければ null', () => {
    localStorage.setItem('dx-board:v1', '{"tasks":[]}')
    expect(loadTasks()).toBeNull()
  })

  it('形の合わない要素だけを捨てる', () => {
    localStorage.setItem(
      'dx-board:v1',
      JSON.stringify([valid, { id: 'b' }, { ...valid, id: 'c', status: 'archived' }]),
    )
    expect(loadTasks()).toEqual([valid])
  })

  it('保存に失敗しても例外を投げない', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    expect(() => saveTasks([valid])).not.toThrow()
    spy.mockRestore()
  })
})
