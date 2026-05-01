import { Home, LayoutGrid, PlusCircle, BarChart2 } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/',          icon: Home,        label: 'Home' },
  { to: '/dashboard', icon: LayoutGrid,  label: 'Dashboard' },
  { to: '/create',    icon: PlusCircle,  label: 'Create Job' },
  { to: '/metrics',   icon: BarChart2,   label: 'Metrics' },
]

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 bg-bg-surface border-r border-border flex flex-col h-screen sticky top-0">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-border">
        <div className="text-accent text-xs tracking-[0.3em] font-mono font-semibold">JOBQUEUE</div>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="w-1.5 h-1.5 rounded-full bg-status-completed inline-block" />
          <span className="text-[10px] text-text-muted tracking-wider">SYSTEM ONLINE</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-0.5">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors duration-100 border-l-2 ${
                isActive
                  ? 'text-accent border-accent bg-bg-elevated'
                  : 'text-text-secondary border-transparent hover:text-text-primary hover:bg-bg-elevated'
              }`
            }
          >
            <Icon size={16} strokeWidth={1.5} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border">
        <div className="text-[10px] text-text-muted font-mono">v0.1.0 · FastAPI + Redis</div>
      </div>
    </aside>
  )
}
