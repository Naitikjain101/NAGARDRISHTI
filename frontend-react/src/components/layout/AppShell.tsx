import { Outlet } from 'react-router-dom'
import { TopHeader } from './TopHeader'
import { Sidebar } from './Sidebar'

export function AppShell() {
  return (
    <div className="h-screen flex flex-col overflow-hidden bg-background">
      <TopHeader />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main
          id="main-content"
          className="flex-1 min-h-0 flex flex-col relative overflow-y-auto"
          tabIndex={-1}
        >
          <div className="flex-1 p-6 flex flex-col min-h-0">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
