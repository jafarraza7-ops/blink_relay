import { NavLink } from 'react-router-dom'
import { Inbox, LayoutDashboard, PlusCircle, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'

const navItems = [
  { to: '/submit', label: 'New Request', icon: PlusCircle, exact: true },
  { to: '/my-requests', label: 'My Requests', icon: Inbox },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, reviewerOnly: true },
]

export function Sidebar() {
  const { isReviewer } = useAuth()

  return (
    <aside className="flex w-60 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex h-16 items-center gap-2 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
          <Zap className="h-5 w-5 text-primary-foreground" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold text-foreground">Blink Relay</p>
          <p className="text-xs text-muted-foreground">Tech Request Portal</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map(({ to, label, icon: Icon, reviewerOnly }) => {
          if (reviewerOnly && !isReviewer) return null
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-3">
        <p className="px-3 text-xs text-muted-foreground">© {new Date().getFullYear()} Blink Network</p>
      </div>
    </aside>
  )
}
