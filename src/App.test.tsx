import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

function column(name: string) {
  return screen.getByRole('region', { name })
}

describe('DX Board', () => {
  it('初期表示でシードタスクが各カラムに並ぶ', () => {
    render(<App />)
    expect(within(column('To Do')).getAllByTestId('task-card')).toHaveLength(2)
    expect(within(column('In Progress')).getAllByTestId('task-card')).toHaveLength(2)
    expect(within(column('Done')).getAllByTestId('task-card')).toHaveLength(2)
  })

  it('タスクを追加すると To Do に入り、#タグ が切り出される', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByLabelText('新しいタスク'), 'E2E を足す #test')
    await user.click(screen.getByRole('button', { name: '追加' }))

    const card = within(column('To Do'))
      .getAllByTestId('task-card')
      .find((element) => within(element).queryByText('E2E を足す'))
    expect(card).toBeDefined()
    expect(within(card!).getByRole('button', { name: '#test' })).toBeInTheDocument()
    expect(within(card!).getByText('中')).toBeInTheDocument()
  })

  it('高優先度で追加すると同カラムの先頭に並ぶ', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByLabelText('新しいタスク'), '最優先で直す')
    await user.selectOptions(screen.getByLabelText('優先度'), 'high')
    await user.click(screen.getByRole('button', { name: '追加' }))

    const cards = within(column('To Do')).getAllByTestId('task-card')
    expect(within(cards[0]).getByText('最優先で直す')).toBeInTheDocument()
  })

  it('「In Progress へ →」でカードが隣のカラムに移る', async () => {
    const user = userEvent.setup()
    render(<App />)

    const card = within(column('To Do'))
      .getAllByTestId('task-card')
      .find((element) => within(element).queryByText(/Playwright/))
    expect(card).toBeDefined()

    await user.click(within(card!).getByRole('button', { name: /In Progress へ/ }))

    expect(within(column('In Progress')).getByText(/Playwright/)).toBeInTheDocument()
    expect(within(column('To Do')).queryByText(/Playwright/)).not.toBeInTheDocument()
  })

  it('カードを Done カラムにドロップすると移動する', () => {
    render(<App />)

    const card = within(column('To Do'))
      .getAllByTestId('task-card')
      .find((element) => within(element).queryByText(/Playwright/))!

    fireEvent.dragStart(card)
    fireEvent.dragOver(column('Done'))
    fireEvent.drop(column('Done'))

    expect(within(column('Done')).getByText(/Playwright/)).toBeInTheDocument()
    expect(within(column('To Do')).queryByText(/Playwright/)).not.toBeInTheDocument()
  })

  it('ドラッグ中でないカラムへのドロップは何も起こさない', () => {
    render(<App />)
    const before = within(column('Done')).getAllByTestId('task-card').length

    fireEvent.dragOver(column('Done'))
    fireEvent.drop(column('Done'))

    expect(within(column('Done')).getAllByTestId('task-card')).toHaveLength(before)
  })

  it('dragLeave でドロップ先のハイライトが外れる', () => {
    render(<App />)
    const target = column('Done')

    fireEvent.dragOver(target)
    expect(target).toHaveClass('column--over')

    fireEvent.dragLeave(target)
    expect(target).not.toHaveClass('column--over')
  })

  it('検索で一致しないカードは消える', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByLabelText('タスクを検索'), 'Playwright')

    expect(screen.getAllByTestId('task-card')).toHaveLength(1)
    expect(screen.getByText(/Playwright/)).toBeInTheDocument()
  })

  it('タグチップを押すと絞り込みが効き、もう一度押すと解除される', async () => {
    const user = userEvent.setup()
    render(<App />)

    const chip = screen.getByRole('button', { name: '#claude-code', pressed: false })
    await user.click(chip)
    expect(screen.getAllByTestId('task-card')).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: '#claude-code', pressed: true }))
    expect(screen.getAllByTestId('task-card')).toHaveLength(6)
  })

  it('タイトルをクリックしてインライン編集できる', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByText('ダークモードをシステム設定に追従させる'))
    const input = screen.getByLabelText('タスク名を編集')
    await user.clear(input)
    await user.type(input, '配色トークンを整理する{Enter}')

    expect(screen.getByText('配色トークンを整理する')).toBeInTheDocument()
    expect(screen.queryByLabelText('タスク名を編集')).not.toBeInTheDocument()
  })

  it('Escape で編集を取り消すと元のタイトルに戻る', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByText('ダークモードをシステム設定に追従させる'))
    await user.type(screen.getByLabelText('タスク名を編集'), '書きかけ{Escape}')

    expect(screen.getByText('ダークモードをシステム設定に追従させる')).toBeInTheDocument()
  })

  it('削除ボタンでカードが消え、完了率が更新される', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(screen.getByRole('progressbar', { name: '完了率' })).toHaveAttribute(
      'aria-valuenow',
      '33',
    )

    await user.click(
      screen.getByRole('button', { name: '「キーボードだけでカードを動かせるようにする」を削除' }),
    )

    expect(screen.getAllByTestId('task-card')).toHaveLength(5)
    expect(screen.getByRole('progressbar', { name: '完了率' })).toHaveAttribute(
      'aria-valuenow',
      '40',
    )
  })

  it('「完了を片付ける」で Done が空になり、押せなくなる', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /完了を片付ける/ }))

    expect(within(column('Done')).getByText('まだ何もありません')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '完了を片付ける' })).toBeDisabled()
  })

  it('「/」キーで検索欄にフォーカスが移る', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.keyboard('/')

    expect(screen.getByLabelText('タスクを検索')).toHaveFocus()
  })

  it('テーマトグルで data-theme が切り替わる', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(document.documentElement.dataset.theme).toBe('light')
    await user.click(screen.getByRole('button', { name: 'ダークモードに切り替え' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('追加したタスクが localStorage に永続化される', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByLabelText('新しいタスク'), '保存されるか確認')
    await user.click(screen.getByRole('button', { name: '追加' }))

    const stored = localStorage.getItem('dx-board:v1')
    expect(stored).toContain('保存されるか確認')
  })
})
