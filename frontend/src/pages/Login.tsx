import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { Logo } from '../components/Layout'

interface Providers {
  providers: string[]
  dev_login: boolean
}

const ERRORS: Record<string, string> = {
  not_allowed: "That account isn't on the allowed list. Sign in with the email set in ALLOWED_EMAILS.",
  unverified_email: 'Your email with that provider is not verified. Verify it there, then try again.',
  oauth_failed: 'Sign-in was cancelled or expired. Try again.',
}

const NAMES: Record<string, string> = { google: 'Google', github: 'GitHub' }

export default function Login() {
  const [params] = useSearchParams()
  const error = params.get('error')
  const providers = useQuery({ queryKey: ['providers'], queryFn: () => api.get<Providers>('/auth/providers') })
  const none = providers.data && providers.data.providers.length === 0 && !providers.data.dev_login

  return (
    <div className="login">
      <div className="login-card">
        <div className="brand" style={{ padding: 0 }}>
          <Logo />
          Finance Tracker
        </div>
        <div>
          <h1>Sign in</h1>
          <p style={{ marginTop: 6 }}>Your accounts, spending, and net worth in one private place.</p>
        </div>
        {error && (
          <div className="notice error" role="alert">
            {ERRORS[error] ?? 'Sign-in failed. Try again.'}
          </div>
        )}
        <div className="stack" style={{ gap: 10 }}>
          {providers.data?.providers.map((p) => (
            <a key={p} className="btn btn-primary" href={`/auth/login/${p}`}>
              Continue with {NAMES[p] ?? p}
            </a>
          ))}
          {providers.data?.dev_login && (
            <a className="btn" href="/auth/dev-login">
              Continue with dev login
            </a>
          )}
        </div>
        {none && (
          <p className="muted">
            No sign-in method is configured. Set GOOGLE_CLIENT_ID or GITHUB_CLIENT_ID, or DEV_LOGIN_EMAIL for local
            development.
          </p>
        )}
      </div>
    </div>
  )
}
