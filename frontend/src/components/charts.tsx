import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Budget, CashflowPoint, CategoryTotal, NetWorthPoint } from '../api/client'
import { categoryLabel, dayLabel, money, moneyCompact, monthLabel, moneyWhole } from '../lib/format'

const AXIS_TICK = { fill: 'var(--ink-3)', fontSize: 12 }

/** Panel wrapper with a chart/table toggle, so every value is reachable without hovering. */
export function ChartPanel({
  title,
  subtitle,
  legend,
  table,
  refetching,
  children,
}: {
  title: string
  subtitle?: ReactNode
  legend?: ReactNode
  table: ReactNode
  refetching?: boolean
  children: ReactNode
}) {
  const [showTable, setShowTable] = useState(false)
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <button className="btn btn-quiet btn-sm" onClick={() => setShowTable((v) => !v)} aria-pressed={showTable}>
          {showTable ? 'Show chart' : 'Show table'}
        </button>
      </div>
      <div className={`chart-frame${refetching ? ' refetching' : ''}`}>
        {showTable ? (
          <div className="table-wrap">{table}</div>
        ) : (
          <>
            {legend}
            {children}
          </>
        )}
      </div>
    </section>
  )
}

function LegendKey({ color, label }: { color: string; label: string }) {
  return (
    <span>
      <i className="key-dot" style={{ background: color }} />
      {label}
    </span>
  )
}

interface TipProps {
  active?: boolean
  label?: string | number
  payload?: { dataKey?: string | number; value?: number; payload?: unknown }[]
}

// ----------------------------------------------------------------------------- Cash flow

function CashflowTip({ active, payload, label }: TipProps) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload as CashflowPoint
  return (
    <div className="tooltip">
      <div className="tooltip-title">{monthLabel(String(label))}</div>
      <div className="tooltip-row">
        <i className="line-key" style={{ background: 'var(--income)' }} />
        <strong>{money(p.income)}</strong>
        <span>income</span>
      </div>
      <div className="tooltip-row">
        <i className="line-key" style={{ background: 'var(--spending)' }} />
        <strong>{money(p.spending)}</strong>
        <span>spending</span>
      </div>
      <div className="tooltip-row" style={{ marginTop: 4 }}>
        <strong className={p.net >= 0 ? 'positive' : undefined}>{money(p.net)}</strong>
        <span>{p.net >= 0 ? 'kept' : 'overspent'}</span>
      </div>
    </div>
  )
}

export function CashflowChart({ data, refetching }: { data: CashflowPoint[]; refetching?: boolean }) {
  return (
    <ChartPanel
      title="Income and spending"
      subtitle="Last 12 months, transfers and card payments excluded"
      refetching={refetching}
      legend={
        <div className="legend">
          <LegendKey color="var(--income)" label="Income" />
          <LegendKey color="var(--spending)" label="Spending" />
        </div>
      }
      table={
        <table className="table">
          <thead>
            <tr>
              <th>Month</th>
              <th className="right">Income</th>
              <th className="right">Spending</th>
              <th className="right">Net</th>
            </tr>
          </thead>
          <tbody>
            {[...data].reverse().map((p) => (
              <tr key={p.month}>
                <td>{monthLabel(p.month)}</td>
                <td className="right">{money(p.income)}</td>
                <td className="right">{money(p.spending)}</td>
                <td className={`right${p.net >= 0 ? ' positive' : ''}`}>{money(p.net)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={2} barCategoryGap="28%" margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--hairline)" />
            <XAxis
              dataKey="month"
              tickFormatter={(m: string) => monthLabel(m, 'short').split(' ')[0]}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: 'var(--rule)' }}
              interval="preserveStartEnd"
            />
            <YAxis tickFormatter={moneyCompact} tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} />
            <Tooltip content={<CashflowTip />} cursor={{ fill: 'var(--hover-wash)' }} />
            <Bar dataKey="income" name="Income" fill="var(--income)" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
            <Bar dataKey="spending" name="Spending" fill="var(--spending)" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  )
}

// ----------------------------------------------------------------------------- Categories

export function CategoryBars({
  categories,
  month,
  limit = 8,
}: {
  categories: CategoryTotal[]
  month: string
  limit?: number
}) {
  const positive = categories.filter((c) => c.amount > 0)
  const shown = positive.slice(0, limit)
  const rest = positive.slice(limit).reduce((s, c) => s + c.amount, 0)
  const rows = rest > 0 ? [...shown, { category: '__rest', amount: rest, count: 0 }] : shown
  const max = Math.max(...rows.map((c) => c.amount), 1)

  if (!rows.length) return <p className="muted">No spending this month yet.</p>

  return (
    <ul className="bars">
      {rows.map((c) => {
        const label = c.category === '__rest' ? 'Everything else' : categoryLabel(c.category)
        const bar = (
          <div className="bar-row">
            <span className="label" title={label}>
              {label}
            </span>
            <span className="bar-track">
              <span className="bar" style={{ width: `${(c.amount / max) * 78}%` }} />
              <span className="bar-value">{moneyWhole(c.amount)}</span>
            </span>
          </div>
        )
        return (
          <li key={c.category}>
            {c.category === '__rest' ? (
              bar
            ) : (
              <Link
                className="bar-link"
                to={`/transactions?category=${encodeURIComponent(c.category)}&month=${month}`}
                aria-label={`${label}: ${money(c.amount)} across ${c.count} transactions`}
              >
                {bar}
              </Link>
            )}
          </li>
        )
      })}
    </ul>
  )
}

// ----------------------------------------------------------------------------- Budgets

export function BudgetMeter({ budget, onEdit }: { budget: Budget; onEdit?: ReactNode }) {
  const ratio = budget.spent / budget.monthly_limit
  const state = ratio > 1 ? 'over' : ratio >= 0.85 ? 'warning' : 'ok'
  const status =
    state === 'over'
      ? `Over by ${money(-budget.remaining)}`
      : state === 'warning'
        ? `Close to the limit, ${money(budget.remaining)} left`
        : `${money(budget.remaining)} left`
  return (
    <div className={`meter ${state}`}>
      <div className="meter-top">
        <strong style={{ fontWeight: 600 }}>{categoryLabel(budget.category)}</strong>
        <span className="num secondary">
          {moneyWhole(budget.spent)} of {moneyWhole(budget.monthly_limit)}
        </span>
      </div>
      <div
        className="meter-track"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={budget.monthly_limit}
        aria-valuenow={budget.spent}
        aria-label={`${categoryLabel(budget.category)} budget`}
      >
        <div className="meter-fill" style={{ width: `${Math.min(ratio, 1) * 100}%` }} />
      </div>
      <div className="meter-status">
        {state !== 'ok' && <span aria-hidden="true">{state === 'over' ? '▲' : '●'}</span>}
        <span>{status}</span>
        {onEdit}
      </div>
    </div>
  )
}

// ----------------------------------------------------------------------------- Net worth

function NetWorthTip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload as NetWorthPoint
  return (
    <div className="tooltip">
      <div className="tooltip-title">{dayLabel(p.date, true)}</div>
      <div className="tooltip-row">
        <i className="line-key" style={{ background: 'var(--series-1)' }} />
        <strong>{money(p.net_worth)}</strong>
        <span>net worth</span>
      </div>
      <div className="tooltip-row">
        <span>
          {moneyWhole(p.assets)} assets, {moneyWhole(p.liabilities)} owed
        </span>
      </div>
    </div>
  )
}

export function NetWorthChart({ data, height = 280 }: { data: NetWorthPoint[]; height?: number }) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--hairline)" />
          <XAxis
            dataKey="date"
            tickFormatter={(d: string) => dayLabel(d)}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: 'var(--rule)' }}
            minTickGap={32}
          />
          <YAxis
            tickFormatter={moneyCompact}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={60}
            domain={['auto', 'auto']}
          />
          <Tooltip content={<NetWorthTip />} cursor={{ stroke: 'var(--rule)', strokeWidth: 1 }} />
          <Area
            type="linear"
            dataKey="net_worth"
            stroke="var(--series-1)"
            strokeWidth={2}
            fill="var(--series-1)"
            fillOpacity={0.1}
            dot={false}
            activeDot={{ r: 5, fill: 'var(--series-1)', stroke: 'var(--surface)', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
