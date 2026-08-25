import React, { useEffect, useState } from 'react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { costs as costsAPI, forecast as forecastAPI, recommendations as recsAPI } from '../services/api';

const fmt = n => `₹${Number(n || 0).toLocaleString('en-IN')}`;

function StatCard({ label, value, sub, color = 'indigo' }) {
  const colors = { indigo:'border-indigo-500/30 bg-indigo-500/10', green:'border-green-500/30 bg-green-500/10',
                   yellow:'border-yellow-500/30 bg-yellow-500/10', red:'border-red-500/30 bg-red-500/10',
                   aws:'border-orange-500/30 bg-orange-500/10', azure:'border-blue-500/30 bg-blue-500/10',
                   gcp:'border-blue-400/30 bg-blue-400/10' };
  return (
    <div className={`border rounded-xl p-4 ${colors[color] || colors.indigo}`}>
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

const RISK_COLOR = { high:'text-red-400 bg-red-900/40', medium:'text-yellow-400 bg-yellow-900/40', low:'text-green-400 bg-green-900/40' };

export default function Dashboard() {
  const [summary, setSummary]   = useState(null);
  const [history, setHistory]   = useState([]);
  const [recs, setRecs]         = useState([]);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    Promise.all([
      costsAPI.summary(),
      costsAPI.history(6),
      recsAPI.list({ limit: 5 }),
    ]).then(([s, h, r]) => {
      setSummary(s);
      setHistory(h.history || []);
      setRecs(r.recommendations || []);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 text-sm">Loading dashboard...</div>;

  const risk = summary?.budget_utilization_pct > 100 ? 'high' : summary?.budget_utilization_pct > 85 ? 'medium' : 'low';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-500 text-sm">Real-time multi-cloud cost intelligence</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Cost (MTD)" value={fmt(summary?.total_cost)} sub={summary?.period} color="indigo" />
        <StatCard label="AWS Cost" value={fmt(summary?.aws_cost)} color="aws" />
        <StatCard label="Azure Cost" value={fmt(summary?.azure_cost)} color="azure" />
        <StatCard label="GCP Cost" value={fmt(summary?.gcp_cost)} color="gcp" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard label="Monthly Budget" value={fmt(summary?.monthly_budget)} color="indigo" />
        <StatCard label="Budget Used" value={`${summary?.budget_utilization_pct ?? 0}%`}
          sub={`₹${(summary?.monthly_budget - summary?.total_cost || 0).toLocaleString('en-IN')} remaining`}
          color={risk} />
        <StatCard label="Budget Risk" value={risk.toUpperCase()}
          sub="Based on current spend rate" color={risk} />
      </div>

      {/* Cost trend chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-4">6-Month Cost Trend</h2>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={history}>
            <defs>
              <linearGradient id="aws" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#FF9900" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#FF9900" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="azure" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0078D4" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#0078D4" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="gcp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4285F4" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#4285F4" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
            <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
              formatter={(v, n) => [fmt(v), n.toUpperCase()]} />
            <Legend />
            <Area type="monotone" dataKey="aws"   stroke="#FF9900" fill="url(#aws)"   name="AWS" />
            <Area type="monotone" dataKey="azure" stroke="#0078D4" fill="url(#azure)" name="Azure" />
            <Area type="monotone" dataKey="gcp"   stroke="#4285F4" fill="url(#gcp)"   name="GCP" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Top recommendations */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-4">Top AI Recommendations</h2>
        {recs.length === 0
          ? <p className="text-gray-500 text-sm">No recommendations yet. <a href="/recommendations" className="text-indigo-400">Generate</a></p>
          : <div className="space-y-3">
              {recs.map(r => (
                <div key={r.recommendation_id || r.id} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
                  <div>
                    <p className="text-sm text-white font-medium">{r.reason?.slice(0, 80) || r.recommendation_type}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {(r.current_provider || '').toUpperCase()} → {(r.recommended_provider || '').toUpperCase()}
                    </p>
                  </div>
                  <div className="text-right ml-4 shrink-0">
                    <p className="text-green-400 font-bold text-sm">{fmt(r.estimated_saving)}/mo</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${RISK_COLOR[r.status] || 'text-gray-400 bg-gray-700'}`}>
                      {r.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
        }
      </div>
    </div>
  );
}
