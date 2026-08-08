type Props = {
  total: number
  done: number
  rate: number
}

export function Progress({ total, done, rate }: Props) {
  return (
    <div className="progress">
      <div className="progress__meta">
        <span className="progress__rate">{rate}%</span>
        <span className="progress__count">
          {done} / {total} 完了
        </span>
      </div>
      <div
        className="progress__track"
        role="progressbar"
        aria-valuenow={rate}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="完了率"
      >
        <div className="progress__bar" style={{ width: `${rate}%` }} />
      </div>
    </div>
  )
}
