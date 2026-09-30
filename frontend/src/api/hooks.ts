import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  type Account,
  type Budget,
  type CashflowPoint,
  type Item,
  type NetWorthCurrent,
  type NetWorthPoint,
  type RecurringSummary,
  type Summary,
  type SyncResult,
  type Transaction,
  type TransactionPage,
  type User,
} from './client'

const V1 = '/api/v1'

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: () => api.get<User>(`${V1}/me`) })

export const useItems = () => useQuery({ queryKey: ['items'], queryFn: () => api.get<Item[]>(`${V1}/items`) })

export const useSummary = (month: string) =>
  useQuery({
    queryKey: ['summary', month],
    queryFn: () => api.get<Summary>(`${V1}/insights/summary`, { month }),
    placeholderData: keepPreviousData,
  })

export const useCashflow = (endMonth: string, months = 12) =>
  useQuery({
    queryKey: ['cashflow', endMonth, months],
    queryFn: () => api.get<CashflowPoint[]>(`${V1}/insights/cashflow`, { end_month: endMonth, months }),
    placeholderData: keepPreviousData,
  })

export interface TransactionFilters {
  search?: string
  account_id?: number
  category?: string
  start?: string
  end?: string
  limit?: number
}

export const useTransactions = (filters: TransactionFilters) =>
  useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => api.get<TransactionPage>(`${V1}/transactions`, { ...filters }),
    placeholderData: keepPreviousData,
  })

export const useCategories = () =>
  useQuery({ queryKey: ['categories'], queryFn: () => api.get<string[]>(`${V1}/categories`), staleTime: 5 * 60_000 })

export const useBudgets = (month: string) =>
  useQuery({
    queryKey: ['budgets', month],
    queryFn: () => api.get<Budget[]>(`${V1}/budgets`, { month }),
    placeholderData: keepPreviousData,
  })

export const useRecurring = () =>
  useQuery({ queryKey: ['recurring'], queryFn: () => api.get<RecurringSummary>(`${V1}/recurring`) })

export const useNetWorthHistory = (days?: number) =>
  useQuery({
    queryKey: ['networth', 'history', days],
    queryFn: () => api.get<NetWorthPoint[]>(`${V1}/networth/history`, { days }),
    placeholderData: keepPreviousData,
  })

export const useNetWorthCurrent = () =>
  useQuery({ queryKey: ['networth', 'current'], queryFn: () => api.get<NetWorthCurrent>(`${V1}/networth/current`) })

// Mutations invalidate everything derived from transactions/balances; the data set is small.
function useInvalidateAll() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
}

export function useSyncAll() {
  const invalidate = useInvalidateAll()
  return useMutation({ mutationFn: () => api.post<SyncResult[]>(`${V1}/sync`), onSettled: invalidate })
}

export function useSyncItem() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (itemId: number) => api.post<SyncResult>(`${V1}/items/${itemId}/sync`),
    onSettled: invalidate,
  })
}

export function useRemoveItem() {
  const invalidate = useInvalidateAll()
  return useMutation({ mutationFn: (itemId: number) => api.delete(`${V1}/items/${itemId}`), onSettled: invalidate })
}

export function useSetAccountHidden() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ id, hidden }: { id: number; hidden: boolean }) =>
      api.patch<Account>(`${V1}/accounts/${id}`, { hidden }),
    onSettled: invalidate,
  })
}

export function useRecategorize() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ id, category }: { id: number; category: string | null }) =>
      api.patch<Transaction>(`${V1}/transactions/${id}`, { category_override: category }),
    onSettled: invalidate,
  })
}

export function useSaveBudget() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ category, limit }: { category: string; limit: number }) =>
      api.put<Budget>(`${V1}/budgets/${encodeURIComponent(category)}`, { monthly_limit: limit }),
    onSettled: invalidate,
  })
}

export function useDeleteBudget() {
  const invalidate = useInvalidateAll()
  return useMutation({ mutationFn: (id: number) => api.delete(`${V1}/budgets/${id}`), onSettled: invalidate })
}
