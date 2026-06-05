import { Navigate, Route, Routes } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import SearchPage from './pages/SearchPage'
import GraphPage from './pages/GraphPage'
import CommunitiesPage from './pages/CommunitiesPage'
import DiagnosticsPage from './pages/DiagnosticsPage'
import ImportPage from './pages/ImportPage'
import MemoriesPage from './pages/MemoriesPage'
import SettingsPage from './pages/SettingsPage'
import StartupPage from './pages/StartupPage'
import NotFoundPage from './pages/NotFoundPage'

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/inbox" replace />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/graph" element={<GraphPage />} />
      <Route path="/communities" element={<CommunitiesPage />} />
      <Route path="/diagnostics" element={<DiagnosticsPage />} />
      <Route path="/inbox" element={<ImportPage />} />
      <Route path="/import" element={<Navigate to="/inbox" replace />} />
      <Route path="/memories" element={<MemoriesPage />} />
      <Route path="/memories/:memoryId" element={<MemoriesPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/startup" element={<StartupPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
