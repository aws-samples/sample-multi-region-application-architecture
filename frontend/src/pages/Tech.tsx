import { useState, useEffect, useRef } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../utils/api';
import { StatsCard } from '../components/StatsCard';

const REGION_NAMES: Record<string, string> = { 'us-east-1': 'N. Virginia', 'us-east-2': 'Ohio' };

/* Reusable section wrapper */
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="bg-surface-card rounded-lg border border-slate-700/50 p-5">
    <h2 className="text-lg font-semibold text-slate-100 mb-4">{title}</h2>
    {children}
  </section>
);

/* ── Architecture Diagram Components ── */

const Chip = ({ label, sub, color = 'blue', pulse, dim }: { label: string; sub?: string; color?: string; pulse?: boolean; dim?: boolean }) => {
  const palettes: Record<string, string> = {
    blue:   'border-blue-500/40 bg-blue-500/8 text-blue-300',
    green:  'border-emerald-500/40 bg-emerald-500/8 text-emerald-300',
    orange: 'border-orange-500/40 bg-orange-500/8 text-orange-300',
    purple: 'border-purple-500/40 bg-purple-500/8 text-purple-300',
    slate:  'border-slate-600/40 bg-slate-600/8 text-slate-300',
    cyan:   'border-cyan-500/40 bg-cyan-500/8 text-cyan-300',
    amber:  'border-amber-500/40 bg-amber-500/8 text-amber-300',
  };
  return (
    <div className={`relative border rounded-lg px-3 py-2 text-center transition-all ${palettes[color] || palettes.blue} ${dim ? 'opacity-30' : ''}`}>
      {pulse && <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" /><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" /></span>}
      <div className="text-[11px] font-semibold">{label}</div>
      {sub && <div className="text-[9px] opacity-60 mt-0.5">{sub}</div>}
    </div>
  );
};


export const Tech = () => {
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
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally { setLoading(false); }
  };

  useEffect(() => { loadStats(); }, []);
  const loadRef = useRef(loadStats);
  useEffect(() => { loadRef.current = loadStats; });
  useEffect(() => {
    setCountdown(60);
    const tick = setInterval(() => {
      setCountdown(prev => { if (prev <= 1) { loadRef.current(); return 60; } return prev - 1; });
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">Loading...</div>;
  if (error) return (
    <div className="bg-status-red/10 border border-status-red/30 rounded-lg p-6 text-sm">
      <p className="text-status-red">{error}</p>
      <button onClick={loadStats} className="mt-3 px-4 py-2 bg-status-red text-white text-xs rounded hover:bg-red-500 transition">Retry</button>
    </div>
  );

  const activeRegion = regionInfo?.region || 'us-east-1';
  const passiveRegion = activeRegion === 'us-east-1' ? 'us-east-2' : 'us-east-1';
  const isPrimaryEast1 = activeRegion === 'us-east-1';

  return (
    <div className="space-y-6">

      {/* ── System Health ── */}
      <Section title="System Health">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <StatsCard title="Active Region" value={REGION_NAMES[activeRegion] || activeRegion} icon="🌍" color="blue" />
          <StatsCard title="Application Health" value={appHealth === 'healthy' ? 'Healthy' : 'Unhealthy'} icon={appHealth === 'healthy' ? '💚' : '❤️'} color={appHealth === 'healthy' ? 'green' : 'red'} />
          {stats && <StatsCard title="Database" value={stats.connected ? 'Healthy' : 'Unhealthy'} icon={stats.connected ? '💚' : '⚠️'} color={stats.connected ? 'green' : 'red'} />}
        </div>
        <div className="text-center text-xs text-slate-500 mt-3">Auto-refresh in <span className="font-mono text-slate-400">{countdown}s</span></div>
      </Section>

      {/* ── Architecture Overview ── */}
      <Section title="Architecture Overview">
        <div className="space-y-6 py-4">

          {/* Layer 1: Edge */}
          <div className="flex items-center justify-center gap-6">
            <div className="flex flex-col items-center gap-1">
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">Edge</div>
              <div className="flex items-center gap-3">
                <Chip label="CloudFront" sub={window.location.hostname} color="purple" />
                <span className="text-slate-600 text-xs">→</span>
                <Chip label="VPC Origin" sub="Private path" color="purple" />
              </div>
            </div>
            <div className="h-12 border-l border-dashed border-slate-700" />
            <div className="flex flex-col items-center gap-1">
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">Auth</div>
              <Chip label="Cognito" sub="JWT tokens" color="cyan" />
            </div>
          </div>

          {/* Layer 2: Compute — side by side regions */}
          <div className="grid grid-cols-2 gap-4 max-w-3xl mx-auto">
            {/* Region 1 */}
            <div className={`rounded-xl border p-4 transition-all ${isPrimaryEast1 ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-slate-700/40 bg-slate-800/20 opacity-50'}`}>
              <div className="flex items-center gap-2 mb-3">
                <span className={`w-2.5 h-2.5 rounded-full ${isPrimaryEast1 ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`} />
                <span className={`text-sm font-bold ${isPrimaryEast1 ? 'text-emerald-400' : 'text-slate-500'}`}>us-east-1</span>
                <span className={`text-[9px] px-2 py-0.5 rounded-full ${isPrimaryEast1 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700/50 text-slate-500'}`}>
                  {isPrimaryEast1 ? 'Active' : 'Pilot Light'}
                </span>
              </div>
              <div className="space-y-2">
                <div className={`text-[10px] text-center py-1.5 rounded border ${isPrimaryEast1 ? 'border-emerald-500/30 text-emerald-300' : 'border-slate-700 text-slate-500'}`}>
                  ALB (internal) → ECS Flask ({isPrimaryEast1 ? 2 : 0} tasks)
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {['Airport', 'Flights', 'Crew'].map(svc => (
                    <div key={svc} className={`text-[9px] text-center py-1 rounded border ${isPrimaryEast1 ? 'border-emerald-500/20 text-emerald-300/80' : 'border-slate-700/50 text-slate-600'}`}>
                      {svc} λ
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Region 2 */}
            <div className={`rounded-xl border p-4 transition-all ${!isPrimaryEast1 ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-slate-700/40 bg-slate-800/20 opacity-50'}`}>
              <div className="flex items-center gap-2 mb-3">
                <span className={`w-2.5 h-2.5 rounded-full ${!isPrimaryEast1 ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`} />
                <span className={`text-sm font-bold ${!isPrimaryEast1 ? 'text-emerald-400' : 'text-slate-500'}`}>us-east-2</span>
                <span className={`text-[9px] px-2 py-0.5 rounded-full ${!isPrimaryEast1 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700/50 text-slate-500'}`}>
                  {!isPrimaryEast1 ? 'Active' : 'Pilot Light'}
                </span>
              </div>
              <div className="space-y-2">
                <div className={`text-[10px] text-center py-1.5 rounded border ${!isPrimaryEast1 ? 'border-emerald-500/30 text-emerald-300' : 'border-slate-700 text-slate-500'}`}>
                  ALB (internal) → ECS Flask ({!isPrimaryEast1 ? 2 : 0} tasks)
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {['Airport', 'Flights', 'Crew'].map(svc => (
                    <div key={svc} className={`text-[9px] text-center py-1 rounded border ${!isPrimaryEast1 ? 'border-emerald-500/20 text-emerald-300/80' : 'border-slate-700/50 text-slate-600'}`}>
                      {svc} λ
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Layer 3: Data */}
          <div className="flex items-center justify-center gap-4">
            <Chip label="DocumentDB Global Cluster" sub={`${activeRegion} → ${passiveRegion}`} color="blue" />
            <Chip label="Secrets Manager" sub="Replicated" color="slate" />
          </div>

          {/* Layer 4: External */}
          <div className="flex items-center justify-center">
            <div className="flex items-center gap-3 px-4 py-2 rounded-lg border border-amber-500/20 bg-amber-500/5">
              <span className="text-[9px] text-amber-400">FlightAware AeroAPI</span>
              <span className="text-slate-600 text-[9px]">→</span>
              <span className="text-[9px] text-slate-400">EventBridge → Refresh λ → DocumentDB</span>
            </div>
          </div>

        </div>
      </Section>

      {/* ── Pilot Light Setup ── */}
      <Section title="Pilot Light Setup">
        <p className="text-sm text-slate-300 mb-4">
          The application uses a <a href="https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html#pilot-light" target="_blank" rel="noopener noreferrer" className="text-accent font-medium underline hover:text-accent/80">Pilot Light</a> disaster recovery pattern.
          Data is continuously replicated to {REGION_NAMES[passiveRegion]}, and compute infrastructure is deployed but idle (0 tasks).
          On failover, compute scales up and traffic switches — no infrastructure needs to be created from scratch.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="text-sm font-semibold text-emerald-400 mb-2">Always On</h3>
            <ul className="text-sm text-slate-300 space-y-1">
              <li>• DocumentDB Global Cluster (continuous replication)</li>
              <li>• Secrets Manager replica (auto-synced)</li>
              <li>• ECR image replication (cross-region)</li>
              <li>• CloudFront + Route 53 (global)</li>
              <li>• Cognito User Pool (cross-region auth)</li>
              <li>• FlightAware AeroAPI (external, region-agnostic)</li>
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-orange-400 mb-2">Switched Off (Pilot Light)</h3>
            <ul className="text-sm text-slate-300 space-y-1">
              <li>• ECS Service — 0 tasks (deployed, idle)</li>
              <li>• Airport Lambda — deployed, no traffic</li>
              <li>• Flights Lambda — deployed, no traffic</li>
              <li>• Crew Lambda — deployed, no traffic</li>
              <li>• EventBridge schedule — disabled in standby region</li>
            </ul>
          </div>
        </div>
      </Section>

      {/* ── ARC Region Switch ── */}
      <Section title="ARC Region Switch">
        <p className="text-sm text-slate-300 mb-4">
          Failover is orchestrated by <a href="https://docs.aws.amazon.com/r53recovery/latest/dg/region-switch.html" target="_blank" rel="noopener noreferrer" className="text-accent font-medium underline hover:text-accent/80">AWS Application Recovery Controller — Region Switch</a>.
          The plan executes manually with a 6-step workflow using <span className="font-mono text-xs text-slate-400">switchoverOnly</span> mode (zero data loss).
        </p>
        <div className="space-y-2">
          {[
            { step: '1', label: 'DocumentDB Switchover', desc: 'Promotes recovery region secondary to primary writer (zero data loss)', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4zm0 2c3.87 0 6 1.5 6 2s-2.13 2-6 2-6-1.5-6-2 2.13-2 6-2zM6 17v-2.42c1.23.8 3.38 1.42 6 1.42s4.77-.62 6-1.42V17c0 .5-2.13 2-6 2s-6-1.5-6-2z"/></svg> },
            { step: '2', label: 'Seed Flight Data', desc: 'Seeds live flight data into the activating region from FlightAware', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg> },
            { step: '3', label: 'Human Approval', desc: 'Operator verifies database and data health before switching traffic', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M12 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 12c-5.33 0-8 2.67-8 4v2h16v-2c0-1.33-2.67-4-8-4z"/></svg> },
            { step: '4', label: 'Scale Compute + Switch CloudFront', desc: 'ECS scales from 0 → production, CloudFront origin swaps to recovery ALB (parallel)', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/></svg> },
            { step: '5', label: 'Final Approval', desc: 'Operator confirms application is fully healthy in the new region', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> },
            { step: '6', label: 'Cleanup', desc: 'Toggles FlightAware schedule to new region and scales down source ECS (parallel)', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M19.14 12.94a7.014 7.014 0 0 0 .02-.94c0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.63-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z"/></svg> },
          ].map(({ step, label, desc, icon }) => (
            <div key={step} className="flex gap-3 items-start p-3 rounded-lg bg-surface/50 border border-slate-700/30 hover:border-accent/30 transition-colors">
              <span className="flex-shrink-0 w-7 h-7 rounded-full bg-accent/15 text-accent text-xs font-bold flex items-center justify-center">{icon}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-slate-500">Step {step}</span>
                  <span className="text-sm font-medium text-slate-200">{label}</span>
                </div>
                <div className="text-xs text-slate-400 mt-0.5">{desc}</div>
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-3">Both failover (→ us-east-2) and failback (→ us-east-1) workflows are configured. The FlightAware scheduled refresh has its own ARC child plan nested under the parent.</p>
      </Section>
    </div>
  );
};
