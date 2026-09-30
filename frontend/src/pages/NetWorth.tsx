import { useState } from 'react'
import { useNetWorthCurrent, useNetWorthHistory } from '../api/hooks'
import { ChartPanel, NetWorthChart } from '../components/charts'
import { dayLabel, money, moneyWhole } from '../lib/format'

const RANGES = [
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '1 year', days: 365 },
  { label: 'All', days: undefined },
]

export default function NetWorth() {
  const [days, setDays] = useState<number | undefined>(365)
  const history = useNetWorthHistory(days)
  const current = useNetWorthCurrent()
  const c = current.data
  const points = history.data ?? []

  return (
    <>
      <div className="filters">
        <select
          className="field"
          value={days ?? ''}
          onChange={(e) => setDays(e.target.value ? Number(e.target.value) : undefined)}
          aria-label="Time range"
        >
          {RANGES.map((r) => (
            <option key={r.label} value={r.days ?? ''}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <section className="hero" aria-label="Net worth">
        <div className={`hero-figure${c && c.net_worth < 0 ? ' negative' : ''}`}>{c ? moneyWhole(c.net_worth) : '—'}</div>
        <p className="hero-line">
          {c ? `net worth today: ${money(c.assets)} in assets minus ${money(c.liabilities)} owed on cards and loans.` : ' '}
        </p>
      </section>

      <div className="stack">
        <ChartPanel
          title="Net worth over time"
          subtitle="One point per day the app synced"
          refetching={history.isPlaceholderData}
          table={
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th className="right">Assets</th>
                  <th className="right">Owed</th>
                  <th className="right">Net worth</th>
                </tr>
              </thead>
              <tbody>
                {[...points].reverse().map((p) => (
                  <tr key={p.date}>
                    <td>{dayLabel(p.date, true)}</td>
                    <td className="right">{money(p.assets)}</td>
                    <td className="right">{money(p.liabilities)}</td>
                    <td className="right">{money(p.net_worth)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          {points.length >= 2 ? (
            <NetWorthChart data={points} />
          ) : (
            <p className="muted" style={{ padding: '24px 0' }}>
              Plaid doesn't provide past balances, so history starts the day you connect and grows by one point each
              day the app syncs. Check back tomorrow for the first line.
            </p>
          )}
        </ChartPanel>

        <section className="panel">
          <div className="panel-head">
            <h2>By account</h2>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Institution</th>
                  <th className="right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {c?.accounts.map((a) => (
                  <tr key={a.account_id}>
                    <td>
                      {a.name}
                      {a.mask && <span className="muted"> ••{a.mask}</span>}
                    </td>
                    <td className="secondary">{a.institution}</td>
                    <td className="right">{money(a.signed_balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </>
  )
}
