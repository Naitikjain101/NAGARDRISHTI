
import { Search, User } from 'lucide-react'
import { useState } from 'react'
import { GlobalSearch } from './GlobalSearch'
import { Notifications } from './Notifications'

export function TopHeader() {
  const [searchOpen, setSearchOpen] = useState(false)

  return (
    <>
      <header className="h-14 border-b border-border bg-background flex items-center justify-between px-4 sticky top-0 z-30">
        <div className="flex items-center gap-2">
          {/* Mobile menu button could go here */}
          <span className="font-semibold text-lg hidden md:block tracking-wide">Urban Intelligence Command Center</span>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="relative hidden md:block">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Search (⌘K)" 
              onClick={() => setSearchOpen(true)}
              readOnly
              className="h-8 w-64 rounded-md border border-input bg-secondary/30 pl-8 pr-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring cursor-pointer hover:bg-secondary/50 transition-colors"
            />
          </div>
          
          <Notifications />
          
          <button className="p-2 text-muted-foreground hover:bg-secondary hover:text-foreground rounded-md transition-colors">
            <User className="h-5 w-5" />
          </button>
        </div>
      </header>
      
      <GlobalSearch isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
    </>
  )
}
