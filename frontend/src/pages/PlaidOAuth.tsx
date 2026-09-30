import { useCallback, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LinkLauncher, type LinkOutcome } from '../components/PlaidLink'
import { savedLinkSession } from '../lib/linkSession'

/** Banks that use OAuth (Chase, Bank of America, …) redirect here to finish connecting. */
export default function PlaidOAuth() {
  const navigate = useNavigate()
  const [session] = useState(savedLinkSession)
  const [error, setError] = useState<string | null>(null)

  const onDone = useCallback(
    (outcome: LinkOutcome) => {
      if (outcome.ok) navigate('/accounts', { replace: true })
      else setError(outcome.message ?? 'The bank connection was not completed.')
    },
    [navigate],
  )

  if (!session || error) {
    return (
      <div className="panel empty">
        <h2>Connection not finished</h2>
        <p>{error ?? 'This page only works right after signing in at your bank. Start the connection again from Accounts.'}</p>
        <Link className="btn btn-primary" to="/accounts">
          Go to Accounts
        </Link>
      </div>
    )
  }

  return (
    <>
      <p className="muted">Finishing your bank connection…</p>
      <LinkLauncher session={session} receivedRedirectUri={window.location.href} onDone={onDone} />
    </>
  )
}
