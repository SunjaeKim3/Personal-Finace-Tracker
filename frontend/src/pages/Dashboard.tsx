import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useBudgets, useCashflow, useItems, useNetWorthCurrent, useRecurring, useSummary } from '../api/hooks'
import { BudgetMeter, CashflowChart, CategoryBars } from '../components/charts'
import MonthSwitch from '../components/MonthSwitch'
import { ConnectButton } from '../components/PlaidLink'
import { currentMonth, dayLabel, money, moneyWhole, monthLabel, parseDay } from '../lib/format'

export default function Dashboard() {
  const [month, setMonth] = useState(currentMonth)
  const items = useItems()
  const summary = useSummary(month)
  const cashflow = useCashflow(month)
  const budgets = useBudgets(month)
  const recurring = useRecurring()
  const networth = useNetWorthCurrent()
  const [today] = useState(() => new Date())

  if (items.data && items.data.length === 0) {
    return (
      <div className="panel empty" style={{ marginTop: 48 }}>
        <h2>Connect your first account</h2>
        <p>
          Link your bank, credit card, and investment accounts through Plaid. Your spending, income, and net worth show
          up here once the first sync finishes.
        </p>
        <ConnectButton label="Connect an account" />
      </div>
    )
  }

  const s = summary.data
  const isCurrent = month === currentMonth()
  const upcoming = (recurring.data?.streams ?? [])
    .filter((r) => r.direction === 'outflow' && r.predicted_next_date && parseDay(r.predicted_next_date) >= today)
    .slice(0, 5)

  return (
    <>
      <div className="filters">
        <MonthSwitch month={month} onChange={setMonth} />
      </div>

      <section className="hero" aria-label="This month">
        {s ? (
          <>
            <div className={`hero-figure${s.net < 0 ? ' negative' : ''}`}>
              {s.net >= 0 ? '+' : '−'}
              {moneyWhole(Math.abs(s.net))}
            </div>
            <p className="hero-line">
              {s.net >= 0
                ? `kept in ${monthLabel(month)}${isCurrent ? ' so far' : ''}, from ${money(s.income)} earned and ${money(s.spending)} spent.`
                : `more spent than earned in ${monthLabel(month)}${isCurrent ? ' so far' : ''}: ${money(s.spending)} out, ${money(s.income)} in.`}
            </p>
          </>
        ) : (
          <div className="hero-figure muted">—</div>
        )}
      </section>

      <div className="kpis">
        <div className="kpi">
          <div className="kpi-label">
            <i className="key-dot" style={{ background: 'var(--income)' }} />
            Income
          </div>
          <div className="kpi-value">{s ? moneyWhole(s.income) : '—'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">
            <i className="key-dot" style={{ background: 'var(--spending)' }} />
            Spending
          </div>
          <div className="kpi-value">{s ? moneyWhole(s.spending) : '—'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Savings rate</div>
          <div className="kpi-value">
            {s?.savings_rate != null ? `${Math.round(s.savings_rate * 100)}%` : '—'}
          </div>
          <div className="kpi-note">share of income kept</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Net worth</div>
          <div className="kpi-value">{networth.data ? moneyWhole(networth.data.net_worth) : '—'}</div>
          <div className="kpi-note">
            <Link to="/net-worth">See history</Link>
          </div>
        </div>
      </div>

      <div className="stack">
        <div className="grid-2">
          {cashflow.data ? (
            <CashflowChart data={cashflow.data} refetching={cashflow.isPlaceholderData} />
          ) : (
            <section className="panel" style={{ minHeight: 340 }} />
          )}
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Where it went</h2>
                <p>Spending by category in {monthLabel(month)}</p>
              </div>
            </div>
            <div className={`chart-frame${summary.isPlaceholderData ? ' refetching' : ''}`}>
              {s && <CategoryBars categories={s.categories} month={month} />}
            </div>
          </section>
        </div>

        <div className="grid-2">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Budgets</h2>
                <p>{monthLabel(month)}</p>
              </div>
              <Link to="/budgets" className="btn btn-quiet btn-sm">
                Manage
              </Link>
            </div>
            {budgets.data?.length ? (
              <div className="stack">
                {[...budgets.data]
                  .sort((a, b) => b.spent / b.monthly_limit - a.spent / a.monthly_limit)
                  .slice(0, 5)
                  .map((b) => (
                    <BudgetMeter key={b.id} budget={b} />
                  ))}
              </div>
            ) : (
              <p className="muted">
                No budgets yet. <Link to="/budgets">Set a monthly limit</Link> for the categories you want to watch.
              </p>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Coming up</h2>
                <p>
                  {recurring.data ? `${money(recurring.data.monthly_outflow)} a month in recurring charges` : ' '}
                </p>
              </div>
              <Link to="/recurring" className="btn btn-quiet btn-sm">
                All
              </Link>
            </div>
            {upcoming.length ? (
              <ul className="list-plain upcoming">
                {upcoming.map((r) => (
                  <li key={r.id}>
                    <span>
                      {r.merchant_name || r.description}
                      <small className="muted" style={{ display: 'block' }}>
                        Expected {dayLabel(r.predicted_next_date!)}
                      </small>
                    </span>
                    <span className="num">{money(r.average_amount ?? 0)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No upcoming charges detected yet. Plaid needs a few months of history to spot them.</p>
            )}
          </section>
        </div>
      </div>
    </>
  )
}
