import { currentMonth, monthLabel, shiftMonth } from '../lib/format'

function Chevron({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d={dir === 'left' ? 'M10 3.5 5.5 8l4.5 4.5' : 'M6 3.5 10.5 8 6 12.5'}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function MonthSwitch({ month, onChange }: { month: string; onChange: (m: string) => void }) {
  const isCurrent = month >= currentMonth()
  return (
    <div className="month-switch" role="group" aria-label="Month">
      <button onClick={() => onChange(shiftMonth(month, -1))} aria-label="Previous month">
        <Chevron dir="left" />
      </button>
      <span aria-live="polite">{monthLabel(month)}</span>
      <button onClick={() => onChange(shiftMonth(month, 1))} disabled={isCurrent} aria-label="Next month">
        <Chevron dir="right" />
      </button>
    </div>
  )
}
