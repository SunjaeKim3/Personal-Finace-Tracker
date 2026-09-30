import { useQueryClient } from '@tanstack/react-query'
import { Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useItems, useMe, useSyncAll } from '../api/hooks'
import { relativeTime } from '../lib/format'

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/transactions', label: 'Transactions' },
  { to: '/budgets', label: 'Budgets' },
  { to: '/recurring', label: 'Recurring' },
  { to: '/net-worth', label: 'Net worth' },
  { to: '/accounts', label: 'Accounts' },
]

export function Logo() {
  return (
    <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="var(--accent)" />
      <path d="M8 22h16M8 16h10M8 10h16" stroke="var(--accent-ink)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

export default function Layout() {
  const me = useMe()
  const items = useItems()
  const syncAll = useSyncAll()
  const qc = useQueryClient()
  const navigate = useNavigate()

  if (me.error instanceof ApiError && me.error.status === 401) return <Navigate to="/login" replace />
  if (!me.data) return null

  const lastSynced = items.data
    ?.map((i) => i.last_synced_at)
    .filter(Boolean)
    .sort()
    .at(0)

  async function logout() {
    await api.post('/auth/logout')
    qc.clear()
    navigate('/login')
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <Logo />
          Finance Tracker
        </NavLink>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          {!!items.data?.length && (
            <button className="btn btn-sm" onClick={() => syncAll.mutate()} disabled={syncAll.isPending}>
              {syncAll.isPending ? 'Refreshing…' : 'Refresh'}
            </button>
          )}
          {lastSynced && <span className="muted who">Updated {relativeTime(lastSynced)}</span>}
          <button className="btn btn-quiet btn-sm" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
