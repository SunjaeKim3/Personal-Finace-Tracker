import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ApiError } from './api/client'
import Layout from './components/Layout'
import Accounts from './pages/Accounts'
import Budgets from './pages/Budgets'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import NetWorth from './pages/NetWorth'
import PlaidOAuth from './pages/PlaidOAuth'
import Recurring from './pages/Recurring'
import Transactions from './pages/Transactions'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="accounts" element={<Accounts />} />
            <Route path="budgets" element={<Budgets />} />
            <Route path="recurring" element={<Recurring />} />
            <Route path="net-worth" element={<NetWorth />} />
            <Route path="plaid-oauth" element={<PlaidOAuth />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
