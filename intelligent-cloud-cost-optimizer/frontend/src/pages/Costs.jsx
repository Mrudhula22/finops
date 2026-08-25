import React, { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { costs as costsAPI } from '../services/api';

const fmt = n => `₹${Number(n||0).toLocaleString('en-IN')}`;
const PROV_COLORS = { aws: '#FF9900', azure: '#0078D4', gcp: '#4285F4' };

export default function CostPage() {
  const [summary, setSummary] = useState(null);
  const [breakdown, setBreakdown] = useState({});
  const [anomalies, setAnomalies] = useState([]);
  const [tab, setTab] = useState('aws');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([costsAPI.summary(), costsAPI.breakdown(), costsAPI.anomalies()])
      .then(([s, b, a]) => { setSummary(s); setBreakdown(b); setAnomalies(a.anomalies || []); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 text-sm">Loading costs...</div>;

  const provData = ['aws','azure','gcp'].map(p => ({
    name: p.toUpperCase(), value: summary?.[`${p}_cost`] || 0, color: PROV_COLORS[p]
  }));

  const tabBreakdown = (breakdown[tab]?.breakdown || []).slice(0, 8).map(b => ({
    name: b.service?.replace('Amazon ', '').replace('Azure ', '').replace('Google ', '') || b.service,
    amount: b.amount, pct: b.percentage
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">Cloud Costs</h1>

      {/* Provider summary cards */}
      <div className="grid grid-cols-3 gap-4">
        {['aws','azure','gcp'].map(p => (
          <div key={p} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ background: PROV_COLORS[p] }} />
              <span className="text-sm font-medium text-gray-300">{p.toUpperCase()}</span>
            </div>
            <p className="text-2xl font-bold text-white">{fmt(summary?.[`${p}_cost`])}</p>
            <p className="text-xs text-gray-500 mt-1">{summary?.period}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Pie chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Cost Distribution</h2>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={provData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={e => `${e.name} ${e.payload.pct||''}%`}>
                {provData.map((e,i) => <Cell key={i} fill={e.color} />)}
              </Pie>
              <Tooltip formatter={v => fmt(v)} contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Per-service breakdown */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white">Service Breakdown</h2>
            <div className="flex gap-1">
              {['aws','azure','gcp'].map(p => (
                <button key={p} onClick={() => setTab(p)}
                  className={`px-2 py-0.5 rounded text-xs font-medium ${tab===p ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={tabBreakdown} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis type="number" tick={{ fill:'#6b7280', fontSize:10 }} tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
              <YAxis type="category" dataKey="name" tick={{ fill:'#9ca3af', fontSize:10 }} width={90} />
              <Tooltip contentStyle={{ background:'#111827', border:'1px solid #374151', borderRadius:8 }}
                formatter={v => fmt(v)} />
              <Bar dataKey="amount" fill={PROV_COLORS[tab]} radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">⚠️ Cost Anomalies ({anomalies.length})</h2>
          <div className="space-y-2">
            {anomalies.slice(0,6).map((a,i) => (
              <div key={i} className="flex items-start gap-3 bg-yellow-900/20 border border-yellow-800/40 rounded-lg px-4 py-3">
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${a.severity==='critical'?'bg-red-700 text-red-100':'bg-yellow-700 text-yellow-100'}`}>
                  {(a.severity||'').toUpperCase()}
                </span>
                <p className="text-sm text-gray-300">{a.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
