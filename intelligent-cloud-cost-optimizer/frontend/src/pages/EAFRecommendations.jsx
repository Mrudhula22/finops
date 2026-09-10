import React, { useEffect, useState } from 'react';
import { recommendations as recsAPI } from '../services/api';
import API from '../services/api';

const fmt = n => `₹${Number(n || 0).toLocaleString('en-IN')}`;

/* ── Reversibility Badge ──────────────────────────────────────────────────── */
function ReversibilityBadge({ cls }) {
  const map = {
    FULLY_REVERSIBLE:     { bg: 'bg-green-900/50 border-green-600',  text: 'text-green-300',  icon: '✅', label: 'FULLY REVERSIBLE' },
    PARTIALLY_REVERSIBLE: { bg: 'bg-yellow-900/50 border-yellow-600', text: 'text-yellow-300', icon: '⚠️', label: 'PARTLY REVERSIBLE' },
    IRREVERSIBLE:         { bg: 'bg-red-900/50 border-red-600',       text: 'text-red-300',    icon: '🚫', label: 'IRREVERSIBLE' },
  };
  const s = map[cls] || map['FULLY_REVERSIBLE'];
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-bold ${s.bg} ${s.text}`}>
      {s.icon} {s.label}
    </span>
  );
}

/* ── Policy Status Badge ──────────────────────────────────────────────────── */
function PolicyBadge({ passed, signature }) {
  if (passed) return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border bg-green-900/40 border-green-600 text-green-300 font-bold">
      🔒 POLICY PASS <span className="font-mono text-green-500 opacity-70">{signature?.slice(0, 8)}</span>
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border bg-red-900/40 border-red-600 text-red-300 font-bold">
      🚫 POLICY BLOCKED
    </span>
  );
}

/* ── Route Badge ──────────────────────────────────────────────────────────── */
function RouteBadge({ route }) {
  const map = {
    AUTO_EXECUTE:   { bg: 'bg-indigo-900/50 border-indigo-500', text: 'text-indigo-300', label: '⚡ AUTO-EXECUTE' },
    MANUAL_REVIEW:  { bg: 'bg-blue-900/50 border-blue-600',     text: 'text-blue-300',   label: '👤 MANUAL REVIEW' },
    SUPPRESSED:     { bg: 'bg-gray-800 border-gray-600',         text: 'text-gray-400',   label: '🚫 SUPPRESSED' },
  };
  const s = map[route] || map['MANUAL_REVIEW'];
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-bold ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

/* ── Terraform Panel ──────────────────────────────────────────────────────── */
function TerraformPanel({ forward, rollback, safetyNote, costReversal, revertTime, whatIsLost, onExecute, autoEligible, policySignature }) {
  const [tab, setTab] = useState('forward');
  const [copied, setCopied] = useState(false);
  const code = tab === 'forward' ? forward : rollback;

  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mt-4 bg-gray-950 border border-gray-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex gap-1">
          {['forward', 'rollback'].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-1 rounded text-xs font-medium ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>
              {t === 'forward' ? '▶ Forward Plan' : '↩ Rollback Plan'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 font-mono">terraform</span>
          <button onClick={copy} className="text-xs text-gray-400 hover:text-white px-2 py-0.5 bg-gray-700 rounded">
            {copied ? '✓ Copied' : 'Copy'}
          </button>
        </div>
      </div>

      {/* Safety info bar */}
      <div className="px-4 py-2 bg-gray-900 border-b border-gray-800 flex flex-wrap gap-4 text-xs">
        <span className="text-gray-300">{safetyNote}</span>
        <span className="text-gray-500">Revert: {Math.round(revertTime / 60)} min</span>
        {costReversal > 0 && <span className="text-yellow-400">Cost to revert: {fmt(costReversal)}</span>}
      </div>

      {/* What's lost */}
      {whatIsLost?.length > 0 && (
        <div className="px-4 py-2 bg-yellow-950/30 border-b border-yellow-800/30">
          <p className="text-xs text-yellow-400 font-medium mb-1">⚠️ What is lost on rollback:</p>
          {whatIsLost.map((w, i) => <p key={i} className="text-xs text-yellow-300/70">• {w}</p>)}
        </div>
      )}

      {/* HCL Code */}
      <pre className="text-xs text-green-300 font-mono p-4 overflow-x-auto max-h-72 bg-gray-950 leading-relaxed">
        {code}
      </pre>

      {/* Execute button */}
      {tab === 'forward' && autoEligible && (
        <div className="px-4 py-3 bg-gray-900 border-t border-gray-800 flex items-center justify-between">
          <p className="text-xs text-gray-400">⚡ Policy-cleared for one-click apply</p>
          <button
            onClick={onExecute}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors">
            ▶ Apply Terraform Plan
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Game Theory Panel ────────────────────────────────────────────────────── */
function GameTheoryPanel({ data }) {
  if (!data) return null;
  return (
    <div className="mt-3 bg-purple-950/20 border border-purple-800/40 rounded-xl p-4">
      <h4 className="text-xs font-bold text-purple-300 mb-2">🎮 Game-Theory Pricing Analysis</h4>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-gray-800 rounded-lg p-2">
          <p className="text-xs text-gray-400">Naive Saving</p>
          <p className="text-white font-bold">{data.naive_saving_pct?.toFixed(1)}%</p>
          <p className="text-xs text-gray-500">{fmt(data.naive_monthly)} /mo</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-2">
          <p className="text-xs text-gray-400">Game-Adjusted Saving</p>
          <p className={`font-bold ${data.game_adjusted_saving_pct < data.naive_saving_pct ? 'text-yellow-400' : 'text-green-400'}`}>
            {data.game_adjusted_saving_pct?.toFixed(1)}%
          </p>
          <p className="text-xs text-gray-500">{fmt(data.game_adjusted_monthly)} /mo</p>
        </div>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-gray-400">Repricing Risk:</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${data.repricing_risk === 'high' ? 'bg-red-900/50 text-red-300' : data.repricing_risk === 'medium' ? 'bg-yellow-900/50 text-yellow-300' : 'bg-green-900/50 text-green-300'}`}>
          {data.repricing_risk?.toUpperCase()}
        </span>
      </div>
      <p className="text-xs text-gray-400 leading-relaxed">{data.explanation?.slice(0, 200)}...</p>
    </div>
  );
}

/* ── Main EAF Recommendations Page ───────────────────────────────────────── */
export default function EAFRecommendationsPage() {
  const [recs, setRecs]             = useState([]);
  const [eafDecisions, setDecisions]= useState([]);
  const [expanded, setExpanded]     = useState({});
  const [generating, setGenerating] = useState(false);
  const [executing, setExecuting]   = useState({});
  const [loading, setLoading]       = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await recsAPI.list({ limit: 50 });
      setRecs(r.recommendations || []);
      if ((r.recommendations || []).length > 0) {
        await runEAF(r.recommendations);
      }
    } finally {
      setLoading(false);
    }
  };

  const runEAF = async (recommendations) => {
    try {
      const res = await API.post('/api/eaf/analyze', { recommendations });
      const byId = {};
      (res.data.decisions || []).forEach(d => { byId[d.recommendation_id] = d; });
      setDecisions(byId);
    } catch (e) {
      console.error('EAF analysis failed', e);
    }
  };

  useEffect(() => { load(); }, []);

  const generate = async () => {
    setGenerating(true);
    await recsAPI.generate({ mode: 'recommendation' }).finally(() => setGenerating(false));
    load();
  };

  const executeAction = async (d) => {
    setExecuting(p => ({ ...p, [d.recommendation_id]: true }));
    try {
      const res = await API.post('/api/eaf/execute', {
        recommendation_id: d.recommendation_id,
        forward_terraform: d.terraform?.forward || '',
        policy_signature:  d.policy_signature || '',
        confirmed: true,
      });
      alert(`✅ ${res.data.note}`);
      load();
    } catch (e) {
      alert(`❌ ${e.response?.data?.detail || 'Execution failed'}`);
    } finally {
      setExecuting(p => ({ ...p, [d.recommendation_id]: false }));
    }
  };

  const toggle = (id) => setExpanded(p => ({ ...p, [id]: !p[id] }));

  const ROUTE_ORDER = { AUTO_EXECUTE: 0, MANUAL_REVIEW: 1, SUPPRESSED: 2 };

  // Merge recs with EAF decisions, sort by route
  const merged = recs
    .map(r => ({ ...r, eaf: eafDecisions[r.recommendation_id || r.id] }))
    .sort((a, b) => (ROUTE_ORDER[a.eaf?.route] ?? 1) - (ROUTE_ORDER[b.eaf?.route] ?? 1));

  const stats = {
    total:   Object.keys(eafDecisions).length,
    auto:    Object.values(eafDecisions).filter(d => d.route === 'AUTO_EXECUTE').length,
    manual:  Object.values(eafDecisions).filter(d => d.route === 'MANUAL_REVIEW').length,
    blocked: Object.values(eafDecisions).filter(d => d.route === 'SUPPRESSED').length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-xl font-bold text-white">EAF Recommendations</h1>
          <p className="text-gray-500 text-xs mt-0.5">
            Explainable Agentic FinOps — Twin-Plan Gating · Policy-Locked · Game-Theory Pricing
          </p>
        </div>
        <button onClick={generate} disabled={generating}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium">
          {generating ? '⏳ Generating...' : '🤖 Generate + Analyze'}
        </button>
      </div>

      {/* EAF stats */}
      {stats.total > 0 && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Total Analyzed', value: stats.total, color: 'border-gray-700 bg-gray-900' },
            { label: '⚡ Auto-Execute', value: stats.auto, color: 'border-indigo-600/40 bg-indigo-900/20' },
            { label: '👤 Manual Review', value: stats.manual, color: 'border-blue-600/40 bg-blue-900/20' },
            { label: '🚫 Policy Blocked', value: stats.blocked, color: 'border-red-600/40 bg-red-900/20' },
          ].map((c, i) => (
            <div key={i} className={`border rounded-xl p-4 ${c.color}`}>
              <p className="text-xs text-gray-400 mb-1">{c.label}</p>
              <p className="text-2xl font-bold text-white">{c.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Recommendation cards */}
      {loading ? <p className="text-gray-400 text-sm">Loading...</p> : (
        merged.length === 0
          ? <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
              <p className="text-gray-400">No recommendations yet.</p>
              <button onClick={generate} className="mt-3 text-indigo-400 text-sm hover:underline">Generate now</button>
            </div>
          : merged.map(r => {
              const id  = r.recommendation_id || r.id;
              const d   = r.eaf;
              const exp = expanded[id];

              if (d?.route === 'SUPPRESSED') return null; // never shown

              return (
                <div key={id} className={`bg-gray-900 border rounded-xl overflow-hidden transition-all ${d?.route === 'AUTO_EXECUTE' ? 'border-indigo-600/50' : 'border-gray-800'}`}>
                  {/* Card header */}
                  <div className="p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        {/* Badges row */}
                        <div className="flex flex-wrap gap-2 mb-2">
                          {d && <RouteBadge route={d.route} />}
                          {d && <ReversibilityBadge cls={d.reversibility} />}
                          {d && <PolicyBadge passed={d.policy_passed} signature={d.policy_signature} />}
                        </div>
                        <p className="text-sm text-gray-200 leading-relaxed">{r.reason?.slice(0, 130)}</p>
                        <div className="flex gap-4 mt-2 text-xs text-gray-500 flex-wrap">
                          <span>{(r.current_provider || '').toUpperCase()} → {(r.recommended_provider || '').toUpperCase()}</span>
                          {d && <span>Confidence: {(d.confidence_score * 100).toFixed(0)}%</span>}
                          {d && <span>Risk: {d.risk_score?.toFixed(0)}/100</span>}
                          {d && d.cost_of_reversal_inr > 0 && (
                            <span className="text-yellow-400">Cost to revert: {fmt(d.cost_of_reversal_inr)}</span>
                          )}
                        </div>
                        {d?.explanation && (
                          <p className="text-xs text-indigo-300/70 mt-1">{d.explanation}</p>
                        )}
                      </div>

                      <div className="text-right shrink-0">
                        <p className="text-green-400 font-bold text-lg">{fmt(r.estimated_saving)}/mo</p>
                        {d?.game_theory && (
                          <p className="text-xs text-purple-400">
                            Game-adj: {fmt(d.game_theory.game_adjusted_monthly)}/mo
                          </p>
                        )}
                        <p className="text-xs text-gray-500 mt-0.5">Save {(r.saving_percentage || 0).toFixed(0)}%</p>

                        <div className="flex gap-2 mt-3 justify-end flex-wrap">
                          <button onClick={() => toggle(id)}
                            className="text-xs px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg">
                            {exp ? '▲ Hide' : '▼ Terraform'}
                          </button>
                          {d?.route === 'AUTO_EXECUTE' && (
                            <button
                              onClick={() => executeAction(d)}
                              disabled={executing[id]}
                              className="text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-bold">
                              {executing[id] ? '⏳' : '⚡ One-Click Apply'}
                            </button>
                          )}
                          {d?.route === 'MANUAL_REVIEW' && (
                            <button
                              onClick={() => toggle(id)}
                              className="text-xs px-3 py-1.5 bg-blue-700 hover:bg-blue-600 text-white rounded-lg">
                              👤 Review Plan
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Safety summary */}
                    {d?.safety_summary && (
                      <div className="mt-3 text-xs text-gray-400 bg-gray-800 rounded-lg px-3 py-2">
                        {d.safety_summary}
                        {d.revert_time_seconds > 0 && (
                          <span className="text-gray-500 ml-3">
                            · Revert in {Math.round(d.revert_time_seconds / 60)} min
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Expanded Terraform + Game Theory */}
                  {exp && d && (
                    <div className="px-5 pb-5">
                      <TerraformPanel
                        forward={d.terraform?.forward || '# No forward plan'}
                        rollback={d.terraform?.rollback || '# No rollback plan'}
                        safetyNote={d.safety_summary}
                        costReversal={d.cost_of_reversal_inr}
                        revertTime={d.revert_time_seconds}
                        whatIsLost={d.what_is_lost}
                        autoEligible={d.route === 'AUTO_EXECUTE'}
                        policySignature={d.policy_signature}
                        onExecute={() => executeAction(d)}
                      />
                      <GameTheoryPanel data={d.game_theory} />
                    </div>
                  )}
                </div>
              );
            })
      )}
    </div>
  );
}
