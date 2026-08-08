import { describe, expect, it } from 'vitest'
import {
  allTags,
  boardReducer,
  completionRate,
  groupByStatus,
  nextStatus,
  parseTitle,
  selectVisible,
  type BoardState,
  type Task,
} from './tasks'

function task(overrides: Partial<Task> = {}): Task {
  return {
    id: 'a',
    title: 'タスク',
    status: 'todo',
    priority: 'medium',
    tags: [],
    createdAt: 0,
    ...overrides,
  }
}

function state(tasks: Task[]): BoardState {
  return { tasks }
}

describe('parseTitle', () => {
  it('#タグ を抜き出してタイトルから取り除く', () => {
    expect(parseTitle('レビュー対応 #ui #urgent')).toEqual({
      title: 'レビュー対応',
      tags: ['ui', 'urgent'],
    })
  })

  it('同じタグは 1 度しか拾わない', () => {
    expect(parseTitle('#ui 直す #ui').tags).toEqual(['ui'])
  })

  it('タグを抜いたあとの空白を潰す', () => {
    expect(parseTitle('  a  #x  b  ').title).toBe('a b')
  })

  it('タグが無ければそのまま返す', () => {
    expect(parseTitle('普通のタスク')).toEqual({ title: '普通のタスク', tags: [] })
  })
})

describe('nextStatus', () => {
  it('todo → doing → done と進む', () => {
    expect(nextStatus('todo')).toBe('doing')
    expect(nextStatus('doing')).toBe('done')
  })

  it('done で止まる', () => {
    expect(nextStatus('done')).toBe('done')
  })
})

describe('boardReducer', () => {
  it('add は先頭に todo として積む', () => {
    const next = boardReducer(state([]), {
      type: 'add',
      id: 'new',
      now: 100,
      title: '新しい',
      priority: 'high',
      tags: ['x'],
    })
    expect(next.tasks).toHaveLength(1)
    expect(next.tasks[0]).toMatchObject({ id: 'new', status: 'todo', priority: 'high', tags: ['x'] })
  })

  it('空文字の add は無視する', () => {
    const before = state([])
    const after = boardReducer(before, {
      type: 'add',
      id: 'new',
      now: 0,
      title: '   ',
      priority: 'low',
      tags: [],
    })
    expect(after).toBe(before)
  })

  it('advance は次のステータスへ進める', () => {
    const next = boardReducer(state([task({ status: 'doing' })]), { type: 'advance', id: 'a' })
    expect(next.tasks[0].status).toBe('done')
  })

  it('advance は done では何も変えない', () => {
    const next = boardReducer(state([task({ status: 'done' })]), { type: 'advance', id: 'a' })
    expect(next.tasks[0].status).toBe('done')
  })

  it('move は任意のステータスへ飛ばせる', () => {
    const next = boardReducer(state([task()]), { type: 'move', id: 'a', status: 'done' })
    expect(next.tasks[0].status).toBe('done')
  })

  it('rename は前後の空白を落とす', () => {
    const next = boardReducer(state([task()]), { type: 'rename', id: 'a', title: '  改名  ' })
    expect(next.tasks[0].title).toBe('改名')
  })

  it('空文字への rename は拒否する', () => {
    const before = state([task()])
    expect(boardReducer(before, { type: 'rename', id: 'a', title: '  ' })).toBe(before)
  })

  it('remove は該当 id だけ消す', () => {
    const next = boardReducer(state([task({ id: 'a' }), task({ id: 'b' })]), {
      type: 'remove',
      id: 'a',
    })
    expect(next.tasks.map((item) => item.id)).toEqual(['b'])
  })

  it('clearDone は done だけ一掃する', () => {
    const next = boardReducer(
      state([task({ id: 'a', status: 'done' }), task({ id: 'b', status: 'doing' })]),
      { type: 'clearDone' },
    )
    expect(next.tasks.map((item) => item.id)).toEqual(['b'])
  })

  it('元の state を破壊しない', () => {
    const before = state([task()])
    const snapshot = structuredClone(before)
    boardReducer(before, { type: 'advance', id: 'a' })
    expect(before).toEqual(snapshot)
  })
})

describe('selectVisible', () => {
  const tasks = [
    task({ id: 'a', title: 'アルファ', priority: 'low', createdAt: 3, tags: ['ui'] }),
    task({ id: 'b', title: 'ブラボー', priority: 'high', createdAt: 1 }),
    task({ id: 'c', title: 'チャーリー', priority: 'high', createdAt: 2, tags: ['ui'] }),
  ]

  it('優先度の高い順、同率なら新しい順に並べる', () => {
    expect(selectVisible(tasks, { query: '', tag: null }).map((item) => item.id)).toEqual([
      'c',
      'b',
      'a',
    ])
  })

  it('タイトルの部分一致で絞る', () => {
    expect(selectVisible(tasks, { query: 'ブラ', tag: null }).map((item) => item.id)).toEqual(['b'])
  })

  it('タグ名でも検索できる', () => {
    expect(selectVisible(tasks, { query: 'ui', tag: null }).map((item) => item.id)).toEqual([
      'c',
      'a',
    ])
  })

  it('タグ絞り込みと検索は AND で効く', () => {
    expect(selectVisible(tasks, { query: 'アルファ', tag: 'ui' }).map((item) => item.id)).toEqual([
      'a',
    ])
  })

  it('入力を破壊的にソートしない', () => {
    const order = tasks.map((item) => item.id)
    selectVisible(tasks, { query: '', tag: null })
    expect(tasks.map((item) => item.id)).toEqual(order)
  })
})

describe('groupByStatus', () => {
  it('全ステータスのキーを必ず返す', () => {
    expect(groupByStatus([])).toEqual({ todo: [], doing: [], done: [] })
  })

  it('ステータスごとに振り分ける', () => {
    const grouped = groupByStatus([task({ id: 'a', status: 'done' }), task({ id: 'b' })])
    expect(grouped.done.map((item) => item.id)).toEqual(['a'])
    expect(grouped.todo.map((item) => item.id)).toEqual(['b'])
  })
})

describe('allTags', () => {
  it('重複を除いて辞書順に返す', () => {
    expect(allTags([task({ tags: ['ui', 'a11y'] }), task({ tags: ['ui'] })])).toEqual(['a11y', 'ui'])
  })
})

describe('completionRate', () => {
  it('タスクが無ければ 0', () => {
    expect(completionRate([])).toBe(0)
  })

  it('完了割合を四捨五入して返す', () => {
    expect(completionRate([task({ status: 'done' }), task(), task()])).toBe(33)
  })

  it('全部完了なら 100', () => {
    expect(completionRate([task({ status: 'done' })])).toBe(100)
  })
})
