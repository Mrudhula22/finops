import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend } from 'recharts';
import { forecast as forecastAPI } from '../services/api';

const fmt = n => `₹${Number(n||0).toLocaleString('en-IN')}`;

export default function ForecastPage() {
  const [data, setData]     = useState(null);
  const [model, setModel]   = useState('ensemble');
  const [provider, setProv] = useState('aws');
  const [loading, setLoading] = useState(false);

  const run = () => {
    setLoading(true);
    forecastAPI.predict({ provider, model, periods: 30 })
      .then(setData).finally(() => setLoading(false));
  };

  useEffect(() => { run(); }, []);

  const prov = data?.forecasts?.[provider] || {};
  const points = prov.forecast_points || [];
  const budget = data?.monthly_budget || 50000;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">Cost Forecast</h1>

      {/* Controls */}
      <div className="flex flex-wrap gap-3">
        {['aws','azure','gcp'].map(p => (
          <button key={p} onClick={() => setProv(p)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium ${provider===p?'bg-indigo-600 text-white':'bg-gray-800 text-gray-400 hover:text-white'}`}>
            {p.toUpperCase()}
          </button>
        ))}
        <select value={model} onChange={e => setModel(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-1.5">
          {['ensemble','arima','prophet','xgboost'].map(m => <option key={m} value={m}>{m.toUpperCase()}</option>)}
        </select>
        <button onClick={run} disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-1.5 rounded-lg text-sm font-medium">
          {loading ? 'Running...' : '▶ Run Forecast'}
        </button>
      </div>

      {/* KPI cards */}
      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Current Monthly', value: fmt(prov.current_monthly_cost) },
            { label: 'Predicted Next Month', value: fmt(prov.predicted_next_month), highlight: true },
            { label: 'Budget', value: fmt(budget) },
            { label: 'Budget Overrun', value: fmt(prov.budget_overrun), risk: prov.overrun_risk },
          ].map((c,i) => (
            <div key={i} className={`rounded-xl border p-4 ${c.risk==='high'?'border-red-600/40 bg-red-900/20':c.highlight?'border-indigo-500/40 bg-indigo-900/20':'border-gray-800 bg-gray-900'}`}>
              <p className="text-xs text-gray-400 mb-1">{c.label}</p>
              <p className={`text-xl font-bold ${c.risk==='high'?'text-red-400':c.highlight?'text-indigo-300':'text-white'}`}>{c.value}</p>
              {c.risk && <span className={`text-xs px-2 py-0.5 rounded-full mt-1 inline-block font-medium ${c.risk==='high'?'bg-red-900 text-red-300':c.risk==='medium'?'bg-yellow-900 text-yellow-300':'bg-green-900 text-green-300'}`}>{c.risk.toUpperCase()} RISK</span>}
            </div>
          ))}
        </div>
      )}

      {/* Forecast chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-4">30-Day Forecast — {provider.toUpperCase()} ({model.toUpperCase()})</h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="date" tick={{ fill:'#6b7280', fontSize:10 }} tickFormatter={d => d?.slice(5)} />
            <YAxis tick={{ fill:'#6b7280', fontSize:10 }} tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
            <Tooltip contentStyle={{ background:'#111827', border:'1px solid #374151', borderRadius:8 }}
              formatter={v => fmt(v)} labelFormatter={l => `Date: ${l}`} />
            <Legend />
            <ReferenceLine y={budget/30} stroke="#f59e0b" strokeDasharray="4 4" label={{ value:'Daily Budget', fill:'#f59e0b', fontSize:10 }} />
            <Line type="monotone" dataKey="predicted" stroke="#6366f1" strokeWidth={2} dot={false} name="Predicted" />
            <Line type="monotone" dataKey="upper"     stroke="#6366f180" strokeWidth={1} strokeDasharray="3 3" dot={false} name="Upper Bound" />
            <Line type="monotone" dataKey="lower"     stroke="#6366f180" strokeWidth={1} strokeDasharray="3 3" dot={false} name="Lower Bound" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Model metrics */}
      {prov.metrics && typeof prov.metrics === 'object' && !prov.metrics.sub_models && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-3">Model Accuracy Metrics</h2>
          <div className="grid grid-cols-4 gap-4">
            {Object.entries(prov.metrics).map(([k,v]) => (
              <div key={k} className="bg-gray-800 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 uppercase">{k}</p>
                <p className="text-white font-bold mt-1">{typeof v === 'number' ? v.toFixed(2) : v}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
