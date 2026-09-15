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
          className="flex-1 overflow-y-auto"
          tabIndex={-1}
        >
          <div className="p-6 min-h-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
