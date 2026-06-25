import { useState, useEffect, useRef } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../utils/api';
import { StatsCard } from '../components/StatsCard';

const REGION_NAMES: Record<string, string> = { 'us-east-1': 'N. Virginia', 'us-east-2': 'Ohio' };

export const Stats = () => {
  const { regionInfo } = useApp();
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [appHealth, setAppHealth] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(60);

  const loadStats = async () => {
    try {
      setLoading(true); setError(null);
      const [statsData, healthData] = await Promise.all([
        api.getStats(),
        api.healthCheck().then(r => r.status).catch(() => 'unhealthy'),
      ]);
      setStats(statsData);
      setAppHealth(healthData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stats');
    } finally { setLoading(false); }
  };

  useEffect(() => { loadStats(); }, []);
  const loadRef = useRef(loadStats);
  useEffect(() => { loadRef.current = loadStats; });
  useEffect(() => {
    setCountdown(60);
    const tick = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { loadRef.current(); return 60; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">Loading statistics...</div>;

  if (error) {
    return (
      <div className="bg-status-red/10 border border-status-red/30 rounded-lg p-6 text-sm">
        <p className="text-status-red">{error}</p>
        <button onClick={loadStats} className="mt-3 px-4 py-2 bg-status-red text-white text-xs rounded hover:bg-red-500 transition">Retry</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="bg-surface-card rounded-lg border border-slate-700/50 p-5">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-slate-100">System Statistics</h2>
          <button onClick={loadStats} className="px-3 py-1.5 text-xs bg-accent/10 text-accent rounded-md hover:bg-accent/20 transition">Refresh</button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <StatsCard title="Active Region" value={REGION_NAMES[regionInfo?.region || 'us-east-1'] || regionInfo?.region || 'us-east-1'} icon="🌍" color="blue" />
          <StatsCard title="Application Health" value={appHealth === 'healthy' ? 'Healthy' : 'Unhealthy'} icon={appHealth === 'healthy' ? '💚' : '❤️'} color={appHealth === 'healthy' ? 'green' : 'red'} />
          {regionInfo && (
            <>
              <StatsCard title="Role" value={regionInfo.role.toUpperCase()} icon={regionInfo.role === 'primary' ? '✅' : '⏸️'} color={regionInfo.role === 'primary' ? 'green' : 'orange'} />
              <StatsCard title="Tasks" value={regionInfo.taskCount} icon="📦" color="blue" />
              <StatsCard title="Health" value={regionInfo.status.toUpperCase()} icon={regionInfo.status === 'healthy' ? '💚' : '❤️'} color={regionInfo.status === 'healthy' ? 'green' : 'red'} />
            </>
          )}
          {stats && <StatsCard title="Database" value={stats.connected ? 'Healthy' : 'Unhealthy'} icon={stats.connected ? '💚' : '⚠️'} color={stats.connected ? 'green' : 'red'} />}
        </div>
      </section>

      {regionInfo && (
        <section className="bg-surface-card rounded-lg border border-slate-700/50 p-5">
          <h3 className="text-sm font-semibold text-slate-100 mb-3">Database Details</h3>
          <div className="space-y-2 text-sm">
            {[
              { label: 'Region', value: regionInfo.region },
              { label: 'Updated', value: stats?.lastUpdated || new Date().toLocaleString() },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between py-2 border-b border-slate-700/50">
                <span className="text-slate-400">{label}</span>
                <span className="text-slate-200 font-mono text-xs">{value}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="text-center text-xs text-slate-500">
        Auto-refresh in <span className="font-mono text-slate-400">{countdown}s</span>
      </div>
    </div>
  );
};
