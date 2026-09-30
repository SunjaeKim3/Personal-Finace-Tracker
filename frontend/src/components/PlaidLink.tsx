import { useCallback, useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { usePlaidLink, type PlaidLinkOnSuccess } from 'react-plaid-link'
import { api, type Item } from '../api/client'
import { saveLinkSession, type LinkSession } from '../lib/linkSession'

export type LinkOutcome = { ok: true; item?: Item } | { ok: false; message?: string }

/** Opens Plaid Link as soon as it's ready and reports the result. */
export function LinkLauncher({
  session,
  receivedRedirectUri,
  onDone,
}: {
  session: LinkSession
  receivedRedirectUri?: string
  onDone: (outcome: LinkOutcome) => void
}) {
  const qc = useQueryClient()

  const onSuccess = useCallback<PlaidLinkOnSuccess>(
    async (publicToken, metadata) => {
      saveLinkSession(null)
      try {
        if (session.itemId) {
          // Update mode: the Item keeps its access token; just re-sync.
          await api.post(`/api/v1/items/${session.itemId}/sync`)
          onDone({ ok: true })
        } else {
          const item = await api.post<Item>('/api/v1/plaid/exchange', {
            public_token: publicToken,
            institution_id: metadata.institution?.institution_id ?? null,
            institution_name: metadata.institution?.name ?? null,
          })
          onDone({ ok: true, item })
        }
      } catch (e) {
        onDone({ ok: false, message: e instanceof Error ? e.message : 'Could not save the connection.' })
      } finally {
        qc.invalidateQueries()
      }
    },
    [session.itemId, onDone, qc],
  )

  const { open, ready } = usePlaidLink({
    token: session.token,
    receivedRedirectUri,
    onSuccess,
    onExit: (err) => {
      saveLinkSession(null)
      onDone({ ok: false, message: err?.display_message ?? err?.error_message ?? undefined })
    },
  })

  useEffect(() => {
    if (ready) open()
  }, [ready, open])

  return null
}

/** "Connect account" (new Item) or "Reconnect" (update mode for an existing Item). */
export function ConnectButton({
  itemId,
  label,
  className = 'btn btn-primary',
  onDone,
}: {
  itemId?: number
  label: string
  className?: string
  onDone?: (outcome: LinkOutcome) => void
}) {
  const [session, setSession] = useState<LinkSession | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function start() {
    setBusy(true)
    setError(null)
    try {
      const { link_token } = await api.post<{ link_token: string }>('/api/v1/plaid/link-token', {
        item_id: itemId ?? null,
      })
      const s = { token: link_token, itemId }
      saveLinkSession(s)
      setSession(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start Plaid.')
      setBusy(false)
    }
  }

  const finish = useCallback(
    (outcome: LinkOutcome) => {
      setSession(null)
      setBusy(false)
      if (!outcome.ok && outcome.message) setError(outcome.message)
      onDone?.(outcome)
    },
    [onDone],
  )

  return (
    <>
      <button className={className} onClick={start} disabled={busy}>
        {busy ? 'Connecting…' : label}
      </button>
      {error && (
        <span role="alert" className="status bad">
          {error}
        </span>
      )}
      {session && <LinkLauncher session={session} onDone={finish} />}
    </>
  )
}
