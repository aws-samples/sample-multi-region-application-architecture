import type { ReactNode } from 'react';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  color?: 'blue' | 'green' | 'orange' | 'red';
}

const COLOR_MAP = {
  blue: 'border-accent/30 text-accent',
  green: 'border-status-green/30 text-status-green',
  orange: 'border-status-orange/30 text-status-orange',
  red: 'border-status-red/30 text-status-red',
};

export const StatsCard = ({ title, value, icon, color = 'blue' }: StatsCardProps) => (
  <div className={`bg-surface-card border rounded-lg p-4 ${COLOR_MAP[color]}`}>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-xs text-slate-400 uppercase tracking-wider">{title}</p>
        <p className="text-2xl font-semibold mt-1 text-slate-100">{value}</p>
      </div>
      {icon && <span className="text-2xl opacity-60">{icon}</span>}
    </div>
  </div>
);
