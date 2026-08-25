import React, { createContext, useContext, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { auth as authAPI } from './services/api';

// Pages
import Dashboard    from './pages/Dashboard';
import CostPage     from './pages/Costs';
import ForecastPage from './pages/Forecast';
import RecommendationsPage from './pages/Recommendations';
import MultiCloudPage from './pages/MultiCloud';
import AuditLogsPage  from './pages/AuditLogs';
import LoginPage      from './pages/Login';

// ── Auth Context ──────────────────────────────────────────────────────────────
export const AuthContext = createContext(null);

export function useAuth() { return useContext(AuthContext); }

function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      authAPI.me().then(setUser).catch(() => localStorage.removeItem('token')).finally(() => setLoading(false));
    } else { setLoading(false); }
  }, []);

  const login = async (creds) => {
    const data = await authAPI.login(creds);
    localStorage.setItem('token', data.access_token);
    setUser(data.user);
  };
  const logout = () => { localStorage.removeItem('token'); setUser(null); };

  if (loading) return <div className="flex items-center justify-center h-screen text-white">Loading...</div>;
  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

// ── Layout ────────────────────────────────────────────────────────────────────
const NAV = [
  { path: '/',               label: '📊 Dashboard' },
  { path: '/costs',          label: '💰 Costs' },
  { path: '/forecast',       label: '🔮 Forecast' },
  { path: '/recommendations',label: '🤖 AI Recommendations' },
  { path: '/multicloud',     label: '☁️ Multi-Cloud' },
  { path: '/audit',          label: '📋 Audit Logs' },
];

function Layout({ children }) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-sm font-bold text-indigo-400 leading-tight">☁️ AI Cloud Cost<br/>Optimizer</h1>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(n => (
            <Link key={n.path} to={n.path}
              className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                loc.pathname === n.path
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-800">
          <p className="text-xs text-gray-500 mb-2">{user?.email}</p>
          <button onClick={logout}
            className="w-full text-xs text-red-400 hover:text-red-300 py-1">
            Logout
          </button>
        </div>
      </aside>
      {/* Main */}
      <main className="flex-1 overflow-y-auto bg-gray-950 p-6">{children}</main>
    </div>
  );
}

function PrivateRoute({ children }) {
  const { user } = useAuth();
  return user ? <Layout>{children}</Layout> : <Navigate to="/login" replace />;
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/"               element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/costs"          element={<PrivateRoute><CostPage /></PrivateRoute>} />
          <Route path="/forecast"       element={<PrivateRoute><ForecastPage /></PrivateRoute>} />
          <Route path="/recommendations"element={<PrivateRoute><RecommendationsPage /></PrivateRoute>} />
          <Route path="/multicloud"     element={<PrivateRoute><MultiCloudPage /></PrivateRoute>} />
          <Route path="/audit"          element={<PrivateRoute><AuditLogsPage /></PrivateRoute>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
