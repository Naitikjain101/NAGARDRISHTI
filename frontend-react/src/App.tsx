import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { ToastProvider } from './components/ui/Toast'

import { AuthProvider } from './contexts/AuthContext'
import { AuthGuard } from './components/layout/AuthGuard'
import { Login } from './pages/Login'
import { AppShell } from './components/layout/AppShell'
import { CommandCenter } from './pages/CommandCenter'
import { LiveMonitoring } from './pages/LiveMonitoring'
import { Settings } from './pages/Settings'
import { VideoAnalysis } from './pages/VideoAnalysis'
import { Incidents } from './pages/Incidents'
import { RoadIntelligence } from './pages/RoadIntelligence'
import { TrafficIntelligence } from './pages/TrafficIntelligence'
import { Fleet } from './pages/Fleet'
import { Maintenance } from './pages/Maintenance'
import { FleetReplay } from './pages/FleetReplay'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 10_000,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ErrorBoundary>
          <AuthProvider>
            <BrowserRouter>
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<Login />} />
              
              {/* Main application shell - protected by default */}
              <Route path="/" element={<AuthGuard><AppShell /></AuthGuard>}>
                <Route index element={<CommandCenter />} />
                <Route path="fleet-replay" element={<FleetReplay />} />
                <Route path="monitoring" element={<LiveMonitoring />} />
                <Route path="video" element={<VideoAnalysis />} />
                <Route path="road-intelligence" element={<RoadIntelligence />} />
                <Route path="traffic" element={<TrafficIntelligence />} />
                <Route path="incidents" element={<Incidents />} />
                <Route path="fleet" element={<Fleet />} />
                <Route path="maintenance" element={
                  <AuthGuard allowedRoles={['ADMIN', 'CONTROL_ROOM_OPERATOR', 'MAINTENANCE_OFFICER']}>
                    <Maintenance />
                  </AuthGuard>
                } />
                <Route path="settings" element={
                  <AuthGuard allowedRoles={['ADMIN']}>
                    <Settings />
                  </AuthGuard>
                } />

                {/* Redirects for old AI routes → Settings tabs */}
                <Route path="ai/control"     element={<Navigate to="/settings?tab=ai"     replace />} />
                <Route path="ai/pothole-lab" element={<Navigate to="/settings?tab=models" replace />} />
                <Route path="ai/traffic"     element={<Navigate to="/traffic"              replace />} />

                {/* Catch-all */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
            </BrowserRouter>
          </AuthProvider>
        </ErrorBoundary>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
