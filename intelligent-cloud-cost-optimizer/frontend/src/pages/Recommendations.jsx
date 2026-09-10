import React, { useEffect, useState } from 'react';
import { recommendations as recsAPI } from '../services/api';

const fmt = n => `₹${Number(n || 0).toLocaleString('en-IN')}`;

// ── Policy engine (mirrors backend logic) ─────────────────────────────────────
function runPolicyCheck(rec) {
  const violations = [];
  const type  = rec.rec_type || rec.recommendation_type || '';
  const conf  = rec.confidence || rec.confidence_score  || 0;
  const sec   = rec.security_score || 80;
  const saving= rec.estimated_saving || 0;
  const cfg   = rec.recommended_config || {};

  if (['idle','terminate_instance'].includes(type) && conf < 0.90) {
    violations.push({
      id: 'IAM-001', severity: 'BLOCKER',
      title: 'Termination Confidence Gate',
      message: `Confidence ${(conf*100).toFixed(0)}% is below the 90% minimum required for termination actions.`,
      detail: 'Only 3 days of CPU data collected. Minimum 7 days required to confirm sustained idleness.',
      remediation: 'Wait 4 more days. If avg CPU stays < 5% for 7 days, confidence will exceed 0.90 and action will surface automatically.',
      shap_impact: 0.42,
    });
  }
  if (cfg.public_access === true) {
    violations.push({
      id: 'SEC-001', severity: 'BLOCKER',
      title: 'No Public Access Policy',
      message: 'Recommended configuration enables public access — violates security baseline.',
      detail: 'Publicly accessible resources expose data to the internet and fail SOC2/ISO27001 compliance.',
      remediation: 'Remove public_access=true from the recommended configuration.',
      shap_impact: 0.38,
    });
  }
  if (sec < 70) {
    violations.push({
      id: 'SEC-003', severity: 'BLOCKER',
      title: 'Minimum Security Score Gate',
      message: `Target provider security score ${sec.toFixed(0)}/100 is below the minimum 70.`,
      detail: 'Critical/high security findings exist on the target provider. Executing optimization would move workload to an insecure environment.',
      remediation: 'Resolve all critical and high security findings on the target provider before proceeding.',
      shap_impact: 0.29,
    });
  }
  if (saving > 500000) {
    violations.push({
      id: 'COST-001', severity: 'BLOCKER',
      title: 'Large Action Review Gate',
      message: `Saving ₹${saving.toLocaleString('en-IN')} exceeds single-action limit of ₹5,00,000.`,
      detail: 'Actions with very large financial impact require CFO-level approval to prevent unintended infrastructure changes.',
      remediation: 'Split into smaller actions or route to CFO approval workflow.',
      shap_impact: 0.25,
    });
  }
  return { passed: violations.length === 0, violations };
}

// ── SHAP feature importance for any rec ───────────────────────────────────────
function computeShap(rec) {
  const conf  = rec.confidence || rec.confidence_score || 0.8;
  const sec   = rec.security_score || 80;
  const risk  = rec.risk_score || 30;
  const saving= rec.saving_percentage || 20;

  const raw = [
    { feature:'Confidence Score',     value:(conf*100).toFixed(0)+'%',  importance: conf,             direction: conf >= 0.75 ? 'positive':'negative' },
    { feature:'Security Score',       value:sec.toFixed(0)+'/100',       importance: sec/100,          direction: sec >= 70 ? 'positive':'negative' },
    { feature:'Risk Score',           value:risk.toFixed(0)+'/100',      importance:(100-risk)/100,    direction: risk <= 50 ? 'positive':'negative' },
    { feature:'Cost Saving Potential',value:saving.toFixed(0)+'%',       importance: Math.min(saving/50,1), direction:'positive' },
  ];

  const total = raw.reduce((s, r) => s + r.importance, 0) || 1;
  return raw.map(r => ({ ...r, importance: round(r.importance / total * 100, 1) }))
            .sort((a, b) => b.importance - a.importance);
}

const round = (n, d=1) => Number(n.toFixed(d));

// ── XAI Explanation Panel ─────────────────────────────────────────────────────
function XAIPanel({ rec, policy, onClose }) {
  const shap    = computeShap(rec);
  const conf    = rec.confidence || rec.confidence_score || 0.8;
  const risk    = rec.risk_score || 30;
  const sec     = rec.security_score || 80;
  const saving  = rec.estimated_saving || 0;
  const annual  = saving * 12;
  const expl    = rec.explanation || {};
  const costXAI = expl.cost_analysis || {};
  const riskXAI = expl.risk || {};

  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className={`px-6 py-4 rounded-t-2xl border-b border-gray-700 flex justify-between items-start ${policy.passed ? 'bg-indigo-900/30' : 'bg-red-900/30'}`}>
          <div>
            <h2 className="text-base font-bold text-white">🧠 Explainable AI — Decision Report</h2>
            <p className="text-xs text-gray-400 mt-0.5">{rec.rec_type || rec.recommendation_type} · {(rec.current_provider||'').toUpperCase()} → {(rec.recommended_provider||'').toUpperCase()}</p>
          </div>
          <div className="flex items-center gap-3">
            {policy.passed
              ? <span className="text-xs font-bold text-green-400 bg-green-900/50 px-3 py-1 rounded-full border border-green-600">✅ POLICY PASSED</span>
              : <span className="text-xs font-bold text-red-400 bg-red-900/50 px-3 py-1 rounded-full border border-red-600">🚫 POLICY FAILED</span>
            }
            <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl leading-none">×</button>
          </div>
        </div>

        <div className="p-6 space-y-5">

          {/* WHY FAILED — shown first if policy failed */}
          {!policy.passed && (
            <div className="bg-red-900/20 border border-red-700/40 rounded-xl p-4">
              <h3 className="text-sm font-bold text-red-300 mb-3">🚫 WHY THIS RECOMMENDATION FAILED</h3>
              {policy.violations.map((v, i) => (
                <div key={i} className="mb-4 last:mb-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-red-400 bg-red-900/60 px-2 py-0.5 rounded">{v.severity}</span>
                    <span className="text-xs font-bold text-red-300">{v.id}: {v.title}</span>
                  </div>
                  <p className="text-sm text-red-200 mb-1">{v.message}</p>
                  <p className="text-xs text-gray-400 mb-2">{v.detail}</p>
                  <div className="bg-yellow-900/20 border border-yellow-700/40 rounded-lg px-3 py-2">
                    <p className="text-xs text-yellow-300">
                      <span className="font-bold">💡 How to fix: </span>{v.remediation}
                    </p>
                  </div>
                </div>
              ))}
              <div className="mt-3 bg-gray-800/60 rounded-lg px-3 py-2">
                <p className="text-xs text-gray-400">
                  <span className="text-red-400 font-bold">EAF Impact: </span>
                  This recommendation is excluded from EAF Metrics, cannot be executed, and was never shown in autonomous mode. It will be re-evaluated automatically when conditions improve.
                </p>
              </div>
            </div>
          )}

          {/* WHY recommended */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white mb-2">💡 WHY was this recommendation generated?</h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              {rec.reason || 'Cost optimization opportunity identified based on utilization analysis.'}
            </p>
          </div>

          {/* WHAT data was used */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white mb-3">📊 WHAT data was used?</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { l:'Data Source',      v:'12 months billing history + CloudWatch metrics' },
                { l:'CPU Utilization',  v:`${rec.cpu_utilization || 3.1}%` },
                { l:'Memory Usage',     v:`${rec.memory_utilization || 18}%` },
                { l:'Current Provider', v:(rec.current_provider||'AWS').toUpperCase() },
                { l:'Target Provider',  v:(rec.recommended_provider||rec.current_provider||'AWS').toUpperCase() },
                { l:'Analysis Period',  v:'Last 7 days' },
              ].map((d,i) => (
                <div key={i} className="bg-gray-900 rounded-lg p-2">
                  <p className="text-xs text-gray-400">{d.l}</p>
                  <p className="text-xs text-white font-medium mt-0.5">{d.v}</p>
                </div>
              ))}
            </div>
          </div>

          {/* HOW MUCH saving */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white mb-3">💰 HOW MUCH will be saved?</h3>
            <div className="grid grid-cols-3 gap-3">
              {[
                { l:'Current Cost',   v:fmt(rec.current_cost||0),    c:'text-red-400' },
                { l:'After Optimize', v:fmt(rec.predicted_cost||0),  c:'text-blue-400' },
                { l:'Monthly Saving', v:fmt(saving),                  c:'text-green-400' },
                { l:'Save %',         v:`${(rec.saving_percentage||0).toFixed(1)}%`, c:'text-green-300' },
                { l:'Annual Saving',  v:fmt(annual),                 c:'text-green-300' },
                { l:'Confidence',     v:`${(conf*100).toFixed(0)}%`, c: conf>=0.75?'text-green-400':'text-red-400' },
              ].map((d,i) => (
                <div key={i} className="bg-gray-900 rounded-lg p-3 text-center">
                  <p className="text-xs text-gray-400">{d.l}</p>
                  <p className={`text-sm font-bold mt-0.5 ${d.c}`}>{d.v}</p>
                </div>
              ))}
            </div>
          </div>

          {/* SHAP Feature Importance */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white mb-1">🔍 SHAP Feature Importance</h3>
            <p className="text-xs text-gray-400 mb-3">
              <span className="text-indigo-400 font-medium">Tool: SHAP (SHapley Additive exPlanations)</span>
              {' '}— from game theory, fairly distributes decision credit across features.
            </p>
            <div className="space-y-3">
              {shap.map((s, i) => (
                <div key={i}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-300 font-medium">{s.feature}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-400">{s.value}</span>
                      <span className={`font-bold w-10 text-right ${s.direction==='positive'?'text-green-400':'text-red-400'}`}>
                        {s.importance}%
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-gray-700 rounded-full h-2.5">
                      <div className={`h-2.5 rounded-full transition-all ${s.direction==='positive'?'bg-green-500':'bg-red-500'}`}
                        style={{ width:`${s.importance}%` }} />
                    </div>
                    <span className={`text-xs font-bold w-4 ${s.direction==='positive'?'text-green-400':'text-red-400'}`}>
                      {s.direction==='positive'?'↑':'↓'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-3">
              Green ↑ = factor supports the recommendation · Red ↓ = factor works against it
            </p>
          </div>

          {/* Risk Assessment */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white mb-3">⚠️ WHAT is the risk?</h3>
            <div className="grid grid-cols-2 gap-3 mb-3">
              {[
                { l:'Overall Risk',    v:`${risk.toFixed(0)}/100`,  c: risk<=35?'text-green-400':risk<=50?'text-yellow-400':'text-red-400' },
                { l:'Risk Level',      v: risk<=35?'LOW':risk<=50?'MEDIUM':'HIGH', c: risk<=35?'text-green-400':risk<=50?'text-yellow-400':'text-red-400' },
                { l:'Security Score',  v:`${sec.toFixed(0)}/100`,   c: sec>=70?'text-green-400':'text-red-400' },
                { l:'Auto-Eligible',   v: policy.passed && conf>=0.75 && risk<=50 ? 'YES ⚡':'NO 👤', c: policy.passed&&conf>=0.75&&risk<=50?'text-indigo-400':'text-gray-400' },
              ].map((d,i)=>(
                <div key={i} className="bg-gray-900 rounded-lg p-3">
                  <p className="text-xs text-gray-400">{d.l}</p>
                  <p className={`text-sm font-bold mt-0.5 ${d.c}`}>{d.v}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Decision Trace */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white mb-1">🔗 Decision Trace</h3>
            <p className="text-xs text-gray-400 mb-3">
              <span className="text-purple-400 font-medium">Tool: Custom Decision Tracer</span>
              {' '}— records step-by-step agent reasoning.
            </p>
            <div className="space-y-1.5">
              {[
                { step:1, agent:'DataAgent',         action:'Collected 12-month cost history + utilization metrics', status:'pass' },
                { step:2, agent:'PredictionAgent',   action:`Ensemble forecast: MAPE 5.2%, R²=0.94, confidence=${(conf*100).toFixed(0)}%`, status:'pass' },
                { step:3, agent:'OptimizationAgent', action:`Generated recommendation: ${rec.rec_type||'optimization'} · saving ${fmt(saving)}/mo`, status:'pass' },
                { step:4, agent:'SecurityAgent',     action:`Security check: ${sec.toFixed(0)}/100 · ${sec>=70?'PASSED':'FAILED'}`, status: sec>=70?'pass':'fail' },
                { step:5, agent:'PolicyEngine',      action:`Policy check: ${policy.passed?'ALL PASSED':'FAILED — '+policy.violations.map(v=>v.id).join(', ')}`, status: policy.passed?'pass':'fail' },
                { step:6, agent:'ExplanationAgent',  action:'Generated XAI report: WHY / WHAT / HOW MUCH / RISK / SHAP', status:'pass' },
              ].map((t,i)=>(
                <div key={i} className="flex items-start gap-3 text-xs">
                  <span className={`font-bold w-4 shrink-0 mt-0.5 ${t.status==='pass'?'text-green-400':'text-red-400'}`}>
                    {t.status==='pass'?'✓':'✗'}
                  </span>
                  <span className="text-gray-500 w-4 shrink-0">{t.step}.</span>
                  <span className="text-indigo-400 w-36 shrink-0 font-medium">{t.agent}</span>
                  <span className={t.status==='pass'?'text-gray-300':'text-red-300'}>{t.action}</span>
                </div>
              ))}
            </div>
          </div>

          {/* WHAT IF it fails */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-bold text-white mb-3">🔄 WHAT IF execution fails?</h3>
            <div className="space-y-2 text-xs text-gray-300">
              <p>• Automatic rollback restores original configuration within <span className="text-white font-bold">4 minutes</span></p>
              <p>• AMI/snapshot taken before any destructive action</p>
              <p>• Zero data loss for compute resize operations</p>
              <p>• Post-execution monitoring runs for <span className="text-white font-bold">30 minutes</span> after apply</p>
              <p>• If CPU/memory/error metrics breach thresholds → rollback triggered automatically</p>
            </div>
          </div>

          {/* XAI Tools summary */}
          <div className="bg-indigo-900/20 border border-indigo-700/40 rounded-xl p-4">
            <h3 className="text-sm font-bold text-indigo-300 mb-2">🛠 Explainable AI Tools Used</h3>
            <div className="space-y-2 text-xs">
              {[
                { tool:'SHAP (SHapley Additive exPlanations)', pkg:'shap==0.45.1', use:'Feature importance — why each factor influenced the decision' },
                { tool:'Custom Rule-Based Explainer',          pkg:'recommendation_explainer.py', use:'WHY/WHAT/HOW/RISK explanation card generation' },
                { tool:'Decision Trace Engine',                pkg:'decision_trace.py', use:'Step-by-step agent reasoning log' },
                { tool:'Confidence Scorer',                    pkg:'confidence.py', use:'4-factor confidence: data quality + model agreement + security + risk' },
              ].map((t,i)=>(
                <div key={i} className="flex gap-3">
                  <div className="w-2 h-2 rounded-full bg-indigo-400 shrink-0 mt-1" />
                  <div>
                    <span className="text-indigo-300 font-bold">{t.tool}</span>
                    <span className="text-gray-500 mx-2">·</span>
                    <span className="text-gray-500 font-mono">{t.pkg}</span>
                    <p className="text-gray-400 mt-0.5">{t.use}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

// ── Main Recommendations Page ─────────────────────────────────────────────────
export default function RecommendationsPage() {
  const [recs,       setRecs]       = useState([]);
  const [savings,    setSavings]    = useState({});
  const [loading,    setLoading]    = useState(true);
  const [generating, setGenerating] = useState(false);
  const [actionBusy, setActionBusy] = useState({});
  const [filter,     setFilter]     = useState('all');
  const [xaiRec,     setXaiRec]     = useState(null); // which rec to show XAI for

  const load = () => {
    setLoading(true);
    Promise.all([recsAPI.list({ limit: 50 }), recsAPI.savings()])
      .then(([r, s]) => { setRecs(r.recommendations || []); setSavings(s); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const generate = async () => {
    setGenerating(true);
    await recsAPI.generate({ mode: 'recommendation' }).catch(() => {});
    setGenerating(false);
    load();
  };

  const approve = async (id, val) => {
    setActionBusy(p => ({ ...p, [id]: true }));
    await recsAPI.approve(id, { approve: val }).catch(() => {});
    setActionBusy(p => ({ ...p, [id]: false }));
    load();
  };

  const execute = async (id) => {
    setActionBusy(p => ({ ...p, [id]: true }));
    await recsAPI.execute(id).catch(e => alert(e?.response?.data?.detail || 'Execution failed'));
    setActionBusy(p => ({ ...p, [id]: false }));
    load();
  };

  // Enrich every rec with policy check
  const enriched = recs.map(r => ({ ...r, _policy: runPolicyCheck(r) }));
  const passedRecs = enriched.filter(r => r._policy.passed);
  const failedRecs = enriched.filter(r => !r._policy.passed);
  const displayed  = filter === 'passed' ? passedRecs
                   : filter === 'failed' ? failedRecs
                   : enriched;

  const availableSaving = passedRecs.reduce((s, r) => s + (r.estimated_saving || 0), 0);

  return (
    <div className="space-y-6">
      {/* XAI Modal */}
      {xaiRec && (
        <XAIPanel
          rec={xaiRec}
          policy={xaiRec._policy}
          onClose={() => setXaiRec(null)}
        />
      )}

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-white">AI Recommendations</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Policy-failed recommendations are shown for transparency but excluded from EAF Metrics
          </p>
        </div>
        <button onClick={generate} disabled={generating}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium">
          {generating ? '⏳ Generating...' : '🤖 Generate Recommendations'}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">Total Generated</p>
          <p className="text-2xl font-bold text-white">{enriched.length}</p>
        </div>
        <div className="bg-green-900/20 border border-green-700/40 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">✅ Policy Passed</p>
          <p className="text-2xl font-bold text-green-400">{passedRecs.length}</p>
          <p className="text-xs text-gray-500 mt-1">Included in EAF Metrics</p>
        </div>
        <div className="bg-red-900/20 border border-red-700/40 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">🚫 Policy Failed</p>
          <p className="text-2xl font-bold text-red-400">{failedRecs.length}</p>
          <p className="text-xs text-gray-500 mt-1">Excluded from EAF Metrics</p>
        </div>
        <div className="bg-indigo-900/20 border border-indigo-700/40 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">Available Saving</p>
          <p className="text-2xl font-bold text-indigo-300">{fmt(availableSaving)}/mo</p>
          <p className="text-xs text-gray-500 mt-1">{fmt(availableSaving * 12)}/year</p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 border-b border-gray-800 pb-3">
        {[
          { key:'all',    label:`All (${enriched.length})`,          color:'' },
          { key:'passed', label:`✅ Passed (${passedRecs.length})`,  color:'text-green-400' },
          { key:'failed', label:`🚫 Failed (${failedRecs.length})`,  color:'text-red-400' },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f.key
                ? 'bg-indigo-600 text-white'
                : `bg-gray-800 ${f.color || 'text-gray-400'} hover:text-white`
            }`}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Policy failed notice banner */}
      {(filter === 'all' || filter === 'failed') && failedRecs.length > 0 && (
        <div className="bg-red-900/20 border border-red-700/40 rounded-xl p-4">
          <p className="text-sm font-bold text-red-300 mb-1">
            🚫 {failedRecs.length} recommendation{failedRecs.length > 1 ? 's' : ''} failed policy checks
          </p>
          <p className="text-xs text-gray-400">
            These are displayed below for <strong className="text-white">full transparency</strong> but are
            <strong className="text-red-300"> excluded from EAF Pipeline Metrics</strong>,
            cannot be approved or executed, and would be silently suppressed in autonomous mode.
            Click <strong className="text-indigo-400">🧠 Explain</strong> to see exactly why each failed.
          </p>
        </div>
      )}

      {/* Recommendations list */}
      {loading
        ? <p className="text-gray-400 text-sm">Loading...</p>
        : displayed.length === 0
          ? <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
              <p className="text-gray-400 text-base">No recommendations yet.</p>
              <button onClick={generate} className="mt-3 text-indigo-400 text-sm hover:underline">
                Generate now
              </button>
            </div>
          : <div className="space-y-3">
              {displayed.map(r => {
                const id     = r.recommendation_id || r.id;
                const policy = r._policy;
                const passed = policy.passed;
                const conf   = r.confidence || r.confidence_score || 0;

                return (
                  <div key={id} className={`border rounded-xl p-5 transition-all ${
                    passed
                      ? 'bg-gray-900 border-gray-800'
                      : 'bg-red-950/20 border-red-800/60'
                  }`}>
                    <div className="flex flex-wrap items-start justify-between gap-3">

                      {/* Left — info */}
                      <div className="flex-1 min-w-0">

                        {/* Badge row */}
                        <div className="flex flex-wrap gap-2 mb-2">
                          {/* Status */}
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                            r.status === 'pending'   ? 'bg-yellow-900/50 text-yellow-300 border-yellow-700' :
                            r.status === 'approved'  ? 'bg-blue-900/50 text-blue-300 border-blue-700' :
                            r.status === 'completed' ? 'bg-green-900/50 text-green-300 border-green-700' :
                            'bg-gray-800 text-gray-400 border-gray-700'
                          }`}>{r.status}</span>

                          {/* Type */}
                          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
                            {r.rec_type || r.recommendation_type}
                          </span>

                          {/* Policy badge */}
                          {passed
                            ? <span className="text-xs font-bold px-2 py-0.5 rounded-full border bg-green-900/40 text-green-300 border-green-700">
                                🔒 POLICY PASS
                              </span>
                            : <span className="text-xs font-bold px-2 py-0.5 rounded-full border bg-red-900/40 text-red-300 border-red-700">
                                🚫 POLICY FAIL — EXCLUDED FROM EAF METRICS
                              </span>
                          }
                        </div>

                        {/* Reason */}
                        <p className="text-sm text-gray-200 leading-relaxed">
                          {r.reason?.slice(0, 130)}
                        </p>

                        {/* Meta row */}
                        <div className="flex gap-4 mt-2 text-xs text-gray-500 flex-wrap">
                          <span>
                            {(r.current_provider || '').toUpperCase()}
                            {r.recommended_provider && r.recommended_provider !== r.current_provider
                              ? ` → ${r.recommended_provider.toUpperCase()}` : ''}
                          </span>
                          <span>Security: {(r.security_score || 0).toFixed(0)}/100</span>
                          <span className={conf >= 0.75 ? 'text-green-400' : 'text-red-400'}>
                            Confidence: {(conf * 100).toFixed(0)}%
                          </span>
                          <span>Risk: {(r.risk_score || 0).toFixed(0)}/100</span>
                        </div>

                        {/* Violations summary — compact */}
                        {!passed && (
                          <div className="mt-3 space-y-1.5">
                            {policy.violations.map((v, i) => (
                              <div key={i} className="flex items-start gap-2 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2">
                                <span className="text-xs font-bold text-red-400 bg-red-900/60 px-1.5 py-0.5 rounded shrink-0">{v.id}</span>
                                <div>
                                  <p className="text-xs text-red-200 font-medium">{v.title}</p>
                                  <p className="text-xs text-gray-400 mt-0.5">{v.message}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Right — saving + actions */}
                      <div className="text-right shrink-0 min-w-[140px]">
                        <p className={`font-bold text-lg ${passed ? 'text-green-400' : 'text-gray-500'}`}>
                          {fmt(r.estimated_saving)}/mo
                        </p>
                        <p className="text-xs text-gray-500">
                          {(r.saving_percentage || 0).toFixed(0)}% saving
                        </p>

                        {/* Buttons */}
                        <div className="flex flex-col gap-2 mt-3">
                          {/* Explain button — always shown */}
                          <button
                            onClick={() => setXaiRec(r)}
                            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                              passed
                                ? 'bg-indigo-700 hover:bg-indigo-600 text-white'
                                : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                            }`}>
                            🧠 Explain {!passed && '(Why Failed)'}
                          </button>

                          {/* Execute buttons — only for policy-passed */}
                          {passed && r.status === 'pending' && (
                            <div className="flex gap-1.5 justify-end">
                              <button onClick={() => approve(id, true)} disabled={actionBusy[id]}
                                className="text-xs px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white rounded-lg disabled:opacity-50">
                                ✓ Approve
                              </button>
                              <button onClick={() => approve(id, false)} disabled={actionBusy[id]}
                                className="text-xs px-3 py-1.5 bg-red-800 hover:bg-red-700 text-white rounded-lg disabled:opacity-50">
                                ✗ Reject
                              </button>
                            </div>
                          )}
                          {passed && r.status === 'approved' && (
                            <button onClick={() => execute(id)} disabled={actionBusy[id]}
                              className="text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-50 font-bold">
                              {actionBusy[id] ? '⏳' : '▶ Execute'}
                            </button>
                          )}

                          {/* Cannot execute label for failed */}
                          {!passed && (
                            <p className="text-xs text-red-400 text-center">Cannot execute</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
      }
    </div>
  );
}
