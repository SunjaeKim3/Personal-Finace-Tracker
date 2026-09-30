import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Transaction } from '../api/client'
import { useCategories, useItems, useRecategorize, useTransactions } from '../api/hooks'
import { categoryLabel, currentMonth, dayLabel, flow, monthLabel, monthRange, shiftMonth } from '../lib/format'

const PAGE = 100

function isoDay(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function rangeFor(range: string): { start?: string; end?: string } {
  const now = new Date()
  if (range === 'this-month') return monthRange(currentMonth())
  if (range === 'last-month') return monthRange(shiftMonth(currentMonth(), -1))
  if (range === '90d') return { start: isoDay(new Date(now.getTime() - 90 * 86_400_000)) }
  if (range === 'ytd') return { start: `${now.getFullYear()}-01-01` }
  if (range.startsWith('month:')) return monthRange(range.slice(6))
  return {}
}

export default function Transactions() {
  const [params, setParams] = useSearchParams()
  const range = params.get('month') ? `month:${params.get('month')}` : (params.get('range') ?? '90d')
  const category = params.get('category') ?? ''
  const accountId = params.get('account') ?? ''
  const [search, setSearch] = useState(params.get('q') ?? '')
  const [debounced, setDebounced] = useState(search)
  const [limit, setLimit] = useState(PAGE)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 250)
    return () => clearTimeout(t)
  }, [search])

  const filters = useMemo(
    () => ({
      ...rangeFor(range),
      search: debounced || undefined,
      category: category || undefined,
      account_id: accountId ? Number(accountId) : undefined,
      limit,
    }),
    [range, debounced, category, accountId, limit],
  )
  const txns = useTransactions(filters)
  const items = useItems()
  const categories = useCategories()

  const accounts = useMemo(
    () => (items.data ?? []).flatMap((i) => i.accounts.map((a) => ({ ...a, institution: i.institution_name }))),
    [items.data],
  )
  const accountName = (id: number) => {
    const a = accounts.find((x) => x.id === id)
    return a ? `${a.name}${a.mask ? ` ••${a.mask}` : ''}` : ''
  }

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key === 'range') next.delete('month')
    setParams(next, { replace: true })
    setLimit(PAGE)
  }

  const total = txns.data?.total ?? 0

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Transactions</h1>
          <p>{txns.data ? `${total.toLocaleString()} transactions` : ' '}</p>
        </div>
      </div>

      <div className="filters">
        <select className="field" value={range} onChange={(e) => setParam('range', e.target.value)} aria-label="Date range">
          {range.startsWith('month:') && <option value={range}>{monthLabel(range.slice(6))}</option>}
          <option value="this-month">This month</option>
          <option value="last-month">Last month</option>
          <option value="90d">Last 90 days</option>
          <option value="ytd">This year</option>
          <option value="all">All time</option>
        </select>
        <select className="field" value={category} onChange={(e) => setParam('category', e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {categories.data?.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
        <select className="field" value={accountId} onChange={(e) => setParam('account', e.target.value)} aria-label="Account">
          <option value="">All accounts</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.institution ? `${a.institution}: ` : ''}
              {a.name}
            </option>
          ))}
        </select>
        <input
          className="field grow"
          type="search"
          placeholder="Search merchant or description"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setLimit(PAGE)
          }}
          aria-label="Search"
        />
      </div>

      <section className={`panel chart-frame${txns.isPlaceholderData ? ' refetching' : ''}`}>
        {txns.data && txns.data.items.length === 0 ? (
          <div className="empty">
            <h2>No transactions match</h2>
            <p>Try a wider date range or clear the category and account filters.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th className="right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {txns.data?.items.map((t) => (
                  <Row key={t.id} t={t} account={accountName(t.account_id)} categories={categories.data ?? []} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {txns.data && txns.data.items.length < total && (
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <button className="btn" onClick={() => setLimit((l) => l + PAGE)}>
              Show more
            </button>
          </div>
        )}
      </section>
    </>
  )
}

function Row({ t, account, categories }: { t: Transaction; account: string; categories: string[] }) {
  const recategorize = useRecategorize()
  const name = t.merchant_name || t.name
  const { inflow, text } = flow(t.amount)
  const options = categories.includes(t.category) ? categories : [...categories, t.category]

  return (
    <tr>
      <td className="num secondary" style={{ whiteSpace: 'nowrap' }}>
        {dayLabel(t.date)}
      </td>
      <td>
        <div className="merchant">
          {t.logo_url ? (
            <img src={t.logo_url} alt="" loading="lazy" />
          ) : (
            <span className="logo-fallback" aria-hidden="true">
              {name.slice(0, 1).toUpperCase()}
            </span>
          )}
          <div>
            {name}
            {t.pending && <span className="pending">Pending</span>}
            <small>{account}</small>
          </div>
        </div>
      </td>
      <td>
        <select
          className={`category-select${t.category_override ? ' overridden' : ''}`}
          value={t.category}
          disabled={recategorize.isPending}
          aria-label={`Category for ${name}`}
          title={t.category_override ? `Changed by you. Plaid said ${categoryLabel(t.pfc_primary)}.` : undefined}
          onChange={(e) => {
            const value = e.target.value
            recategorize.mutate({ id: t.id, category: value === t.pfc_primary ? null : value })
          }}
        >
          {options.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
      </td>
      <td
        className={`right${!t.counted ? ' not-counted' : inflow ? ' positive' : ''}`}
        title={t.counted ? undefined : 'Transfer or card payment: not counted as spending or income'}
      >
        {text}
      </td>
    </tr>
  )
}
