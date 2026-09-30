// OAuth banks send the user back to /plaid-oauth, which must re-open Link with the same token.
const STORAGE_KEY = 'plaid-link-session'

export interface LinkSession {
  token: string
  itemId?: number
}

export function savedLinkSession(): LinkSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as LinkSession) : null
  } catch {
    return null
  }
}

export function saveLinkSession(s: LinkSession | null) {
  try {
    if (s) localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // storage unavailable: OAuth banks will need a retry, everything else still works
  }
}
