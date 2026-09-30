import { useState } from 'react'
import type { Budget } from '../api/client'
import { useBudgets, useCategories, useDeleteBudget, useSaveBudget, useSummary } from '../api/hooks'
import { BudgetMeter } from '../components/charts'
import MonthSwitch from '../components/MonthSwitch'
import { categoryLabel, currentMonth, moneyWhole, monthLabel } from '../lib/format'

const NOT_BUDGETABLE = new Set(['INCOME', 'TRANSFER_IN', 'TRANSFER_OUT'])

export default function Budgets() {
  const [month, setMonth] = useState(currentMonth)
  const budgets = useBudgets(month)
  const summary = useSummary(month)
  const categories = useCategories()
  const save = useSaveBudget()

  const spent = new Map(summary.data?.categories.map((c) => [c.category, c.amount]))
  const budgeted = new Set(budgets.data?.map((b) => b.category))
  const available = (categories.data ?? [])
    .filter((c) => !NOT_BUDGETABLE.has(c) && !budgeted.has(c))
    .sort((a, b) => (spent.get(b) ?? 0) - (spent.get(a) ?? 0))

  const [category, setCategory] = useState('')
  const [limit, setLimit] = useState('')
  const chosen = category || available[0] || ''

  const totalLimit = budgets.data?.reduce((s, b) => s + b.monthly_limit, 0) ?? 0
  const totalSpent = budgets.data?.reduce((s, b) => s + b.spent, 0) ?? 0

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Budgets</h1>
          <p>
            {budgets.data?.length
              ? `${moneyWhole(totalSpent)} spent of ${moneyWhole(totalLimit)} budgeted in ${monthLabel(month)}`
              : 'Set a monthly limit for the categories you want to keep an eye on.'}
          </p>
        </div>
      </div>

      <div className="filters">
        <MonthSwitch month={month} onChange={setMonth} />
      </div>

      <div className="grid-2">
        <section className={`panel chart-frame${budgets.isPlaceholderData ? ' refetching' : ''}`}>
          {budgets.data?.length ? (
            <div className="stack" style={{ gap: 24 }}>
              {budgets.data.map((b) => (
                <BudgetRow key={b.id} budget={b} />
              ))}
            </div>
          ) : (
            <div className="empty">
              <h2>No budgets yet</h2>
              <p>Add one on the right. Budgets reset each month and count refunds against what you spent.</p>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Add a budget</h2>
          </div>
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault()
              const n = Number(limit)
              if (!chosen || !(n > 0)) return
              save.mutate({ category: chosen, limit: n }, { onSuccess: () => { setLimit(''); setCategory('') } })
            }}
          >
            <select className="field" value={chosen} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
              {available.map((c) => (
                <option key={c} value={c}>
                  {categoryLabel(c)}
                  {spent.get(c) ? ` (${moneyWhole(spent.get(c)!)} in ${monthLabel(month)})` : ''}
                </option>
              ))}
            </select>
            <div className="form-row">
              <input
                className="field money-input"
                inputMode="decimal"
                placeholder="Monthly limit"
                value={limit}
                onChange={(e) => setLimit(e.target.value.replace(/[^0-9.]/g, ''))}
                aria-label="Monthly limit in dollars"
              />
              <button className="btn btn-primary" disabled={!chosen || !(Number(limit) > 0) || save.isPending}>
                Add budget
              </button>
            </div>
          </form>
        </section>
      </div>
    </>
  )
}

function BudgetRow({ budget }: { budget: Budget }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(budget.monthly_limit))
  const save = useSaveBudget()
  const remove = useDeleteBudget()

  if (editing) {
    return (
      <form
        className="form-row"
        onSubmit={(e) => {
          e.preventDefault()
          const n = Number(value)
          if (n > 0) save.mutate({ category: budget.category, limit: n }, { onSuccess: () => setEditing(false) })
        }}
      >
        <strong style={{ fontWeight: 600, flex: '1 1 140px' }}>{categoryLabel(budget.category)}</strong>
        <input
          className="field money-input"
          inputMode="decimal"
          value={value}
          autoFocus
          onChange={(e) => setValue(e.target.value.replace(/[^0-9.]/g, ''))}
          aria-label={`Monthly limit for ${categoryLabel(budget.category)}`}
        />
        <button className="btn btn-primary btn-sm" disabled={save.isPending}>
          Save
        </button>
        <button type="button" className="btn btn-sm btn-quiet" onClick={() => setEditing(false)}>
          Cancel
        </button>
        <button type="button" className="btn btn-sm btn-quiet btn-danger" onClick={() => remove.mutate(budget.id)}>
          Delete
        </button>
      </form>
    )
  }
  return (
    <BudgetMeter
      budget={budget}
      onEdit={
        <button className="btn btn-quiet btn-sm" style={{ marginLeft: 'auto', minHeight: 24 }} onClick={() => setEditing(true)}>
          Edit
        </button>
      }
    />
  )
}
