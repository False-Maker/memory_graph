import { NavLink } from 'react-router-dom'
import AppRouter from './router'
import './api/client'
import GlobalErrorToastContainer from './components/GlobalErrorToastContainer'

const primaryNavigation = [
  { label: 'Inbox', path: '/inbox', className: 'nav-import' },
  { label: 'Search', path: '/search', className: 'nav-search' },
  { label: 'Memory', path: '/memories', className: 'nav-memory' },
  { label: 'Settings', path: '/settings', className: 'nav-settings' }
]

const secondaryNavigation = [
  { label: 'Dashboard', path: '/dashboard', className: 'nav-dashboard' },
  { label: 'Diagnostics', path: '/diagnostics', className: 'nav-diagnostics' },
  { label: 'Graph', path: '/graph', className: 'nav-graph' },
  { label: 'Communities', path: '/communities', className: 'nav-communities' },
  { label: 'Startup', path: '/startup', className: 'nav-startup' }
]

function renderNavClassName({ isActive }) {
  return isActive ? 'nav-link active' : 'nav-link'
}

function NavigationGroup({ title, items }) {
  return (
    <div className="nav-group">
      <p className="nav-group-title">{title}</p>
      <div className="nav-group-links">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => `${renderNavClassName({ isActive })} ${item.className}`}
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="logo">Memory Graph</div>
        <nav className="nav" aria-label="Main navigation">
          <NavigationGroup title="Core" items={primaryNavigation} />
          <NavigationGroup title="Secondary" items={secondaryNavigation} />
        </nav>
      </aside>

      <main className="content">
        <AppRouter />
      </main>

      <GlobalErrorToastContainer />
    </div>
  )
}
