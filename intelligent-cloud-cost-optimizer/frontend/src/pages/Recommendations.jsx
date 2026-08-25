import React, { useEffect, useState } from 'react';
import { recommendations as recsAPI } from '../services/api';

const fmt = n => `₹${Number(n||0).toLocaleString('en-IN')}`;

const STATUS_COLORS = {
  pending:   'bg-yellow-900/50 text-yellow-300 border-yellow-700',
  approved:  'bg-blue-900/50 text-blue-300 border-blue-700',
  completed: 'bg-green-900/50 text-green-300 border-green-700',
  rejected:  'bg-red-900/50 text-red-300 border-red-700',
  rolled_back:'bg-gray-700 text-gray-300 border-gray-600',
};

const RISK_COLORS = {
  low:'text-green-400', medium:'text-yellow-400', high:'text-red-400', critical:'text-red-600'
};

function ExplanationPanel({ rec, onClose }) {
  const xai = rec.explanation || {};
  const cost = xai.cost_analysis || {};
  const risk = xai.risk || {};
  const conf = xai.confidence || {};
  const sec  = xai.security || {};

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-lg font-bold text-white">🧠 AI Explanation</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">×</button>
        </div>

        {/* Summary */}
        <div className="bg-indigo-900/20 border border-indigo-700/40 rounded-xl p-4 mb-4">
          <p className="text-sm text-gray-300">{xai.why?.summary || rec.reason}</p>
        </div>

        {/* Cost analysis */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          {[
            { label:'Current Provider', value: (cost.current_provider||'N/A') },
            { label:'Recommended Provider', value: (cost.recommended_provider||'N/A') },
            { label:'Current Cost', value: fmt(cost.current_cost_inr) },
            { label:'Optimized Cost', value: fmt(cost.optimized_cost_inr) },
            { label:'Monthly Saving', value: fmt(cost.monthly_saving_inr), green:true },
            { label:'Annual Saving', value: fmt(cost.annual_saving_inr), green:true },
          ].map((c,i) => (
            <div key={i} className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-400">{c.label}</p>
              <p className={`font-bold mt-0.5 ${c.green?'text-green-400':'text-white'}`}>{c.value}</p>
            </div>
          ))}
        </div>

        {/* Risk */}
        <div className="bg-gray-800 rounded-xl p-4 mb-4">
          <h3 className="text-sm font-semibold text-white mb-2">Risk Assessment</h3>
          <div className="grid grid-cols-2 gap-2 mb-2">
            {[
              {l:'Overall', v:risk.overall_score},
              {l:'Performance', v:risk.performance_risk},
              {l:'Availability', v:risk.availability_risk},
              {l:'Migration', v:risk.migration_risk},
            ].map((r,i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="text-gray-400">{r.l}</span>
                <span className={RISK_COLORS[risk.level] || 'text-white'}>{(r.v||0).toFixed(0)}/100</span>
              </div>
            ))}
          </div>
          {risk.factors?.map((f,i) => <p key={i} className="text-xs text-yellow-400 mt-1">⚠ {f}</p>)}
        </div>

        {/* Confidence */}
        <div className="bg-gray-800 rounded-xl p-4 mb-4">
          <h3 className="text-sm font-semibold text-white mb-2">Confidence: {conf.score?.toFixed(0)}% — {conf.label}</h3>
          <p className="text-xs text-gray-400">{conf.explanation}</p>
        </div>

        {/* Security */}
        <div className="bg-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-1">Security Score: {(sec.score||0).toFixed(0)}/100 — {sec.rating}</h3>
          <p className={`text-xs font-medium ${sec.approved?'text-green-400':'text-red-400'}`}>
            {sec.approved ? '✓ Security check passed' : '✗ Security check failed'}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function RecommendationsPage() {
  const [recs, setRecs]         = useState([]);
  const [savings, setSavings]   = useState({});
  const [selected, setSelected] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [generating, setGenerating] = useState(false);
  const [actionLoading, setActionLoading] = useState({});

  const load = () => {
    setLoading(true);
    Promise.all([recsAPI.list({ limit: 50 }), recsAPI.savings()])
      .then(([r, s]) => { setRecs(r.recommendations || []); setSavings(s); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const generate = async () => {
    setGenerating(true);
    await recsAPI.generate({ mode: 'recommendation' }).finally(() => setGenerating(false));
    load();
  };

  const approve = async (id, approve) => {
    setActionLoading(p => ({ ...p, [id]: true }));
    await recsAPI.approve(id, { approve, comment: approve ? 'Approved via dashboard' : 'Rejected by user' });
    setActionLoading(p => ({ ...p, [id]: false }));
    load();
  };

  const execute = async (id) => {
    setActionLoading(p => ({ ...p, [id]: true }));
    await recsAPI.execute(id).catch(e => alert(e.response?.data?.detail || 'Execution failed'));
    setActionLoading(p => ({ ...p, [id]: false }));
    load();
  };

  const viewXAI = async (rec) => {
    if (!rec.explanation) {
      const full = await recsAPI.get(rec.recommendation_id || rec.id);
      setSelected(full);
    } else {
      setSelected(rec);
    }
  };

  return (
    <div className="space-y-6">
      {selected && <ExplanationPanel rec={selected} onClose={() => setSelected(null)} />}

      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold text-white">AI Recommendations</h1>
        <button onClick={generate} disabled={generating}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium">
          {generating ? '⏳ Generating...' : '🤖 Generate Recommendations'}
        </button>
      </div>

      {/* Savings summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label:'Available Monthly', value: fmt(savings.available_monthly) },
          { label:'Available Annual',  value: fmt(savings.available_annual) },
          { label:'Executed Monthly',  value: fmt(savings.executed_monthly) },
          { label:'Total Recommendations', value: savings.recommendation_count || 0 },
        ].map((c,i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-400 mb-1">{c.label}</p>
            <p className="text-xl font-bold text-white">{c.value}</p>
          </div>
        ))}
      </div>

      {/* Recommendations list */}
      {loading ? <p className="text-gray-400 text-sm">Loading...</p> : (
        <div className="space-y-3">
          {recs.length === 0
            ? <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
                <p className="text-gray-400">No recommendations yet.</p>
                <button onClick={generate} className="mt-3 text-indigo-400 text-sm hover:underline">Generate now</button>
              </div>
            : recs.map(r => {
                const id = r.recommendation_id || r.id;
                const expl = r.explanation || {};
                const risk = expl.risk || {};
                return (
                  <div key={id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLORS[r.status] || 'bg-gray-800 text-gray-400 border-gray-600'}`}>
                            {r.status}
                          </span>
                          <span className="text-xs text-gray-500">{r.rec_type || r.recommendation_type}</span>
                          {risk.level && (
                            <span className={`text-xs font-medium ${RISK_COLORS[risk.level]}`}>
                              {risk.level?.toUpperCase()} RISK
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-200 leading-relaxed">{r.reason?.slice(0,140)}</p>
                        <div className="flex gap-4 mt-2 text-xs text-gray-500">
                          <span>{(r.current_provider||'').toUpperCase()} → {(r.recommended_provider||'').toUpperCase()}</span>
                          <span>Security: {(r.security_score||0).toFixed(0)}/100</span>
                          <span>Confidence: {((r.confidence||r.confidence_score||0)*100).toFixed(0)}%</span>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <p className="text-green-400 font-bold text-lg">{fmt(r.estimated_saving)}/mo</p>
                        <p className="text-xs text-gray-500">Save {(r.saving_percentage||0).toFixed(0)}%</p>

                        <div className="flex gap-2 mt-3 justify-end flex-wrap">
                          <button onClick={() => viewXAI(r)}
                            className="text-xs px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg">
                            🧠 Explain
                          </button>
                          {r.status === 'pending' && (
                            <>
                              <button onClick={() => approve(id, true)} disabled={actionLoading[id]}
                                className="text-xs px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white rounded-lg disabled:opacity-50">
                                ✓ Approve
                              </button>
                              <button onClick={() => approve(id, false)} disabled={actionLoading[id]}
                                className="text-xs px-3 py-1.5 bg-red-800 hover:bg-red-700 text-white rounded-lg disabled:opacity-50">
                                ✗ Reject
                              </button>
                            </>
                          )}
                          {r.status === 'approved' && (
                            <button onClick={() => execute(id)} disabled={actionLoading[id]}
                              className="text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-50">
                              {actionLoading[id] ? '⏳' : '▶ Execute'}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
          }
        </div>
      )}
    </div>
  );
}
