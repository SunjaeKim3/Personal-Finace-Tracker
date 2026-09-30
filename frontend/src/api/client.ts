import type { components } from './schema'

export type Schemas = components['schemas']
export type Item = Schemas['ItemOut']
export type Account = Schemas['AccountOut']
export type Transaction = Schemas['TransactionOut']
export type TransactionPage = Schemas['TransactionPage']
export type Summary = Schemas['SummaryOut']
export type CashflowPoint = Schemas['CashflowPoint']
export type CategoryTotal = Schemas['CategoryTotal']
export type Budget = Schemas['BudgetOut']
export type Recurring = Schemas['RecurringOut']
export type RecurringSummary = Schemas['RecurringSummary']
export type NetWorthPoint = Schemas['NetWorthPoint']
export type NetWorthCurrent = Schemas['NetWorthCurrent']
export type SyncResult = Schemas['SyncResultOut']
export type User = Schemas['UserOut']

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Query = Record<string, string | number | boolean | null | undefined>

function withQuery(path: string, query?: Query) {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const res = await fetch(withQuery(path, query), {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let message = res.statusText
    try {
      const data = await res.json()
      message = typeof data.detail === 'string' ? data.detail : message
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, undefined, query),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
