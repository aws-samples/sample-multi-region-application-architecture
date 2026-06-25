import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { path: '/', label: 'Flights', sub: 'Live' },
  { path: '/airports', label: 'Airports', sub: 'Mock' },
  { path: '/crew', label: 'Crew', sub: 'Mock' },
  { path: '/tech', label: 'Tech' },
];

export const Header = () => {
  const { regionInfo } = useApp();
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="border-b border-slate-700/50 bg-surface-card/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight text-white hover:text-accent transition">
            <img src="/favicon.svg" alt="" className="w-6 h-6" />
            <div className="flex flex-col leading-tight">
              <span>AirportHub</span>
              <span className="text-[10px] font-normal text-slate-400">Global Operations Dashboard</span>
            </div>
          </Link>
          {regionInfo && (
            <span className={`text-xs font-mono px-2 py-0.5 rounded ${
              regionInfo.role === 'primary'
                ? 'bg-status-green/15 text-status-green'
                : 'bg-status-orange/15 text-status-orange'
            }`}>
              {regionInfo.region} · {regionInfo.role}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <nav className="flex gap-1">
            {NAV_ITEMS.map(({ path, label, sub }) => (
              <Link
                key={path}
                to={path}
                className={`px-3 py-1.5 text-sm rounded-md transition text-center ${
                  pathname === path
                    ? 'bg-accent/10 text-accent'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-hover'
                }`}
              >
                {label}
                {sub && <span className="block text-[9px] opacity-60">{sub}</span>}
              </Link>
            ))}
          </nav>
          {user && (
            <div className="flex items-center gap-3 ml-2 pl-3 border-l border-slate-700/50">
              <span className="text-xs text-slate-400">{user.email}</span>
              <button data-testid="header-logout" onClick={handleLogout}
                className="text-xs text-slate-400 hover:text-status-red transition">
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
