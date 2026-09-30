const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const usdWhole = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const usdCompact = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
})

export const money = (n: number) => usd.format(n)
export const moneyWhole = (n: number) => usdWhole.format(n)
export const moneyCompact = (n: number) => (Math.abs(n) < 1000 ? usdWhole.format(n) : usdCompact.format(n))

/** Plaid amounts are positive for money out. Show them the way a person reads a statement. */
export function flow(amount: number) {
  const inflow = amount < 0
  return { inflow, text: `${inflow ? '+' : '−'}${usd.format(Math.abs(amount))}` }
}

const CATEGORY_LABELS: Record<string, string> = {
  INCOME: 'Income',
  TRANSFER_IN: 'Transfer in',
  TRANSFER_OUT: 'Transfer out',
  LOAN_PAYMENTS: 'Loan payments',
  BANK_FEES: 'Bank fees',
  ENTERTAINMENT: 'Entertainment',
  FOOD_AND_DRINK: 'Food & drink',
  GENERAL_MERCHANDISE: 'Shopping',
  HOME_IMPROVEMENT: 'Home improvement',
  MEDICAL: 'Medical',
  PERSONAL_CARE: 'Personal care',
  GENERAL_SERVICES: 'Services',
  GOVERNMENT_AND_NON_PROFIT: 'Government & nonprofit',
  TRANSPORTATION: 'Transportation',
  TRAVEL: 'Travel',
  RENT_AND_UTILITIES: 'Rent & utilities',
  OTHER: 'Other',
}

export function categoryLabel(c: string | null | undefined) {
  if (!c) return 'Other'
  if (CATEGORY_LABELS[c]) return CATEGORY_LABELS[c]
  const s = c.toLowerCase().replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const FREQUENCY_LABELS: Record<string, string> = {
  WEEKLY: 'Weekly',
  BIWEEKLY: 'Every 2 weeks',
  SEMI_MONTHLY: 'Twice a month',
  MONTHLY: 'Monthly',
  ANNUALLY: 'Yearly',
  UNKNOWN: 'Irregular',
}
export const frequencyLabel = (f: string | null | undefined) => FREQUENCY_LABELS[f ?? 'UNKNOWN'] ?? f ?? 'Irregular'

// Months are "YYYY-MM" strings throughout, matching the API.
export function currentMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function shiftMonth(month: string, delta: number) {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function monthLabel(month: string, style: 'long' | 'short' = 'long') {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(y, m - 1, 1)
  const sameYear = y === new Date().getFullYear()
  return d.toLocaleDateString('en-US', {
    month: style,
    year: style === 'short' ? '2-digit' : sameYear ? undefined : 'numeric',
  })
}

export function monthRange(month: string) {
  const [y, m] = month.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  return { start: `${month}-01`, end: `${month}-${String(last).padStart(2, '0')}` }
}

/** Parse "YYYY-MM-DD" as a local date (new Date("2026-09-01") would be UTC midnight). */
export function parseDay(s: string) {
  const [y, m, d] = s.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function dayLabel(s: string, withYear = false) {
  return parseDay(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: withYear ? 'numeric' : undefined })
}

export function relativeTime(iso: string | null | undefined) {
  if (!iso) return 'never'
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.round(hours / 24)
  return days === 1 ? 'yesterday' : `${days} days ago`
}
