
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from './components/ui/ErrorBoundary'

import { AppShell } from './components/layout/AppShell'
import { Overview } from './pages/Overview'
import { Analytics } from './pages/Analytics'
import { LiveMonitoring } from './pages/LiveMonitoring'
import { Settings } from './pages/Settings'
import { VideoAnalysis } from './pages/VideoAnalysis'
import { AIControlCenter } from './pages/AIControlCenter'
import { LiveMap } from './pages/LiveMap'
import { Incidents } from './pages/Incidents'
import { RoadIntelligence } from './pages/RoadIntelligence'
import { TrafficIntelligence } from './pages/TrafficIntelligence'
import { Fleet } from './pages/Fleet'
import { Maintenance } from './pages/Maintenance'
import PotholeLab from './pages/PotholeLab'
import { FleetReplay } from './pages/FleetReplay'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppShell />}>
              <Route index element={<Overview />} />
              <Route path="map" element={<LiveMap />} />
              <Route path="fleet-replay" element={<FleetReplay />} />
              <Route path="monitoring" element={<LiveMonitoring />} />
              <Route path="video" element={<VideoAnalysis />} />
              <Route path="road-intelligence" element={<RoadIntelligence />} />
              <Route path="traffic" element={<TrafficIntelligence />} />
              <Route path="incidents" element={<Incidents />} />
              <Route path="fleet" element={<Fleet />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="maintenance" element={<Maintenance />} />
              <Route path="/ai/traffic" element={<TrafficIntelligence />} />
              <Route path="/ai/control" element={<AIControlCenter />} />
              <Route path="/ai/pothole-lab" element={<PotholeLab />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ErrorBoundary>
    </QueryClientProvider>
  )
}

export default App
