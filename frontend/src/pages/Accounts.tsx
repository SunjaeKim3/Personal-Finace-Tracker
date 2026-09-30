import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type Item } from '../api/client'
import { useItems, useRemoveItem, useSetAccountHidden, useSyncItem } from '../api/hooks'
import { ConnectButton, type LinkOutcome } from '../components/PlaidLink'
import { money, relativeTime } from '../lib/format'

interface AuthConfig {
  plaid_env: string
}

const TYPE_LABELS: Record<string, string> = {
  depository: 'Cash',
  credit: 'Credit',
  loan: 'Loan',
  investment: 'Investment',
  brokerage: 'Investment',
  other: 'Other',
}

export default function Accounts() {
  const items = useItems()
  const config = useQuery({ queryKey: ['auth-config'], queryFn: () => api.get<AuthConfig>('/auth/providers') })
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null)

  function onConnected(outcome: LinkOutcome) {
    if (outcome.ok && outcome.item) {
      setMessage({
        text: `Connected ${outcome.item.institution_name ?? 'your bank'}. Plaid can take a few minutes to pull full history; use Refresh if transactions look incomplete.`,
      })
    } else if (outcome.ok) {
      setMessage({ text: 'Reconnected. Your accounts are syncing again.' })
    } else if (outcome.message) {
      setMessage({ text: outcome.message, error: true })
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Accounts</h1>
          <p>Hide an account to leave it out of spending, budgets, and net worth.</p>
        </div>
        <ConnectButton label="Connect an account" onDone={onConnected} />
      </div>

      {message && (
        <div className={`notice${message.error ? ' error' : ''}`} role="status">
          {message.text}
        </div>
      )}

      {config.data?.plaid_env === 'sandbox' && (
        <div className="notice" role="note">
          Sandbox mode: these are Plaid's test banks. Pick any institution and sign in with username{' '}
          <strong>user_transactions_dynamic</strong> and any password for realistic transactions.
        </div>
      )}

      {items.data?.length === 0 && (
        <div className="panel empty">
          <h2>No accounts connected</h2>
          <p>Connect a bank, card, or brokerage login. One login can include several accounts.</p>
        </div>
      )}

      <div className="stack">
        {items.data?.map((item) => (
          <Institution key={item.id} item={item} onReconnected={onConnected} />
        ))}
      </div>
    </>
  )
}

function Institution({ item, onReconnected }: { item: Item; onReconnected: (o: LinkOutcome) => void }) {
  const sync = useSyncItem()
  const remove = useRemoveItem()
  const setHidden = useSetAccountHidden()
  const needsLogin = item.status === 'login_required'

  return (
    <section className="panel institution">
      <div className="institution-head">
        <div>
          <h2>{item.institution_name ?? 'Institution'}</h2>
          {needsLogin ? (
            <span className="status bad">
              <span aria-hidden="true">▲</span> Sign in again to keep syncing
            </span>
          ) : item.status === 'error' ? (
            <span className="status bad">
              <span aria-hidden="true">▲</span> Last sync failed ({item.error_code})
            </span>
          ) : (
            <span className="status">
              {item.last_synced_at ? `Synced ${relativeTime(item.last_synced_at)}` : 'Not synced yet'}
            </span>
          )}
        </div>
        <div className="actions">
          {needsLogin ? (
            <ConnectButton itemId={item.id} label="Reconnect" onDone={onReconnected} />
          ) : (
            <button className="btn btn-sm" onClick={() => sync.mutate(item.id)} disabled={sync.isPending}>
              {sync.isPending ? 'Syncing…' : 'Sync now'}
            </button>
          )}
          <button
            className="btn btn-sm btn-quiet btn-danger"
            disabled={remove.isPending}
            onClick={() => {
              if (confirm(`Disconnect ${item.institution_name ?? 'this institution'}? Its accounts and transactions will be deleted from this app.`))
                remove.mutate(item.id)
            }}
          >
            Disconnect
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Account</th>
              <th>Type</th>
              <th className="right">Balance</th>
              <th className="right">In totals</th>
            </tr>
          </thead>
          <tbody>
            {item.accounts.map((a) => (
              <tr key={a.id} style={a.hidden ? { opacity: 0.55 } : undefined}>
                <td>
                  {a.name}
                  {a.mask && <span className="muted"> ••{a.mask}</span>}
                </td>
                <td className="secondary">
                  {TYPE_LABELS[a.type] ?? a.type}
                  {a.subtype && a.subtype !== a.type ? `, ${a.subtype}` : ''}
                </td>
                <td className="right">
                  {a.current_balance == null ? '—' : money(a.current_balance)}
                  {(a.type === 'credit' || a.type === 'loan') && a.current_balance != null && (
                    <small className="muted" style={{ display: 'block' }}>
                      owed
                    </small>
                  )}
                </td>
                <td className="right">
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!a.hidden}
                      onChange={(e) => setHidden.mutate({ id: a.id, hidden: !e.target.checked })}
                    />
                    <span className="visually-hidden">Include {a.name} in totals</span>
                  </label>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
