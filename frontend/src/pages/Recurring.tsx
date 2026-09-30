import type { Recurring as Stream } from '../api/client'
import { useRecurring } from '../api/hooks'
import { dayLabel, frequencyLabel, money, moneyWhole } from '../lib/format'

export default function Recurring() {
  const recurring = useRecurring()
  const streams = recurring.data?.streams ?? []
  const outflows = streams.filter((s) => s.direction === 'outflow').sort((a, b) => b.monthly_amount - a.monthly_amount)
  const inflows = streams.filter((s) => s.direction === 'inflow').sort((a, b) => b.monthly_amount - a.monthly_amount)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Recurring</h1>
          <p>Subscriptions, bills, and paychecks Plaid has spotted in your history.</p>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi">
          <div className="kpi-label">Bills and subscriptions</div>
          <div className="kpi-value">{recurring.data ? moneyWhole(recurring.data.monthly_outflow) : '—'}</div>
          <div className="kpi-note">per month</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Recurring income</div>
          <div className="kpi-value">{recurring.data ? moneyWhole(recurring.data.monthly_inflow) : '—'}</div>
          <div className="kpi-note">per month</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Bills and subscriptions</div>
          <div className="kpi-value">{recurring.data ? moneyWhole(recurring.data.monthly_outflow * 12) : '—'}</div>
          <div className="kpi-note">per year</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Active</div>
          <div className="kpi-value">{recurring.data ? streams.length : '—'}</div>
          <div className="kpi-note">streams</div>
        </div>
      </div>

      <div className="stack">
        <StreamTable title="Bills and subscriptions" streams={outflows} verb="charged" />
        <StreamTable title="Income" streams={inflows} verb="received" />
      </div>
    </>
  )
}

function StreamTable({ title, streams, verb }: { title: string; streams: Stream[]; verb: string }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
      </div>
      {streams.length === 0 ? (
        <p className="muted">Nothing detected yet. Plaid needs at least three occurrences to call something recurring.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>How often</th>
                <th className="right">Typical amount</th>
                <th className="right">Per month</th>
                <th className="right">Last {verb}</th>
                <th className="right">Next expected</th>
              </tr>
            </thead>
            <tbody>
              {streams.map((s) => (
                <tr key={s.id}>
                  <td>
                    {s.merchant_name || s.description}
                    {s.status === 'EARLY_DETECTION' && <span className="pending">New</span>}
                  </td>
                  <td className="secondary">{frequencyLabel(s.frequency)}</td>
                  <td className="right">{s.average_amount != null ? money(s.average_amount) : '—'}</td>
                  <td className="right">{money(s.monthly_amount)}</td>
                  <td className="right secondary">{s.last_date ? dayLabel(s.last_date) : '—'}</td>
                  <td className="right">{s.predicted_next_date ? dayLabel(s.predicted_next_date) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
