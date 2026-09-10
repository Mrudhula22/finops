import React, { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LineChart, Line, ReferenceLine, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from 'recharts';

const fmt = n => `₹${Number(n||0).toLocaleString('en-IN')}`;

/* ── Figure A ── Game Theory ─────────────────────────────────────────────── */
function FigureA() {
  const savingData = [
    { name: 'Naive Static\nComparison', value: 4300,   fill:'#6b7280' },
    { name: 'Game-Adjusted\nForecast',  value: 3620,   fill:'#6366f1' },
    { name: 'Realized\nSaving',         value: 2901.7, fill:'#22c55e' },
  ];

  const modelData = [
    { model:'ARIMA',    mape:7.2,  r2:0.91, fill:'#f59e0b' },
    { model:'Prophet',  mape:5.8,  r2:0.93, fill:'#8b5cf6' },
    { model:'XGBoost',  mape:6.4,  r2:0.92, fill:'#ec4899' },
    { model:'Ensemble', mape:5.2,  r2:0.94, fill:'#6366f1' },
  ];

  const nashData = [
    { provider:'AWS',   current:20318, equilibrium:19200, pred90:19800, risk:'MEDIUM', color:'#FF9900' },
    { provider:'Azure', current:17940, equilibrium:17100, pred90:17400, risk:'LOW',    color:'#0078D4' },
    { provider:'GCP',   current:15769, equilibrium:15200, pred90:15600, risk:'LOW',    color:'#4285F4' },
  ];

  const gtEvidence = [
    { action:'W1 – Rightsize worker-dev (intra-AWS)', naive:30.0, adjusted:30.0, naiveINR:1263,  adjINR:1263,  risk:'none',   signal:'Intra-provider resize — no demand shift, no repricing.' },
    { action:'W3 – Migrate web-server AWS→GCP',       naive:23.2, adjusted:20.8, naiveINR:4300,  adjINR:3850,  risk:'low',    signal:'0.0003% market demand shift. GCP elasticity=0.22 → +₹10.4/mo price rise.' },
    { action:'W6 – Migrate all compute AWS→GCP',      naive:18.5, adjusted:11.2, naiveINR:18500, adjINR:11200, risk:'medium', signal:'0.0021% demand shift. Copycat prob=1.05%. Equilibrium convergence at 6 months.' },
  ];

  return (
    <div className="bg-gray-950 text-white p-8 space-y-6" style={{width:940}}>
      {/* Header */}
      <div className="border-b border-gray-700 pb-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-indigo-600 flex items-center justify-center font-bold text-lg">A</div>
        <div>
          <h2 className="text-lg font-bold">Cross-Cloud Economic Game Theory</h2>
          <p className="text-xs text-gray-400">Multi-cloud arbitrage modelled as repeated game against adaptive provider pricing</p>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          {l:'Ensemble MAPE', v:'5.2%',      c:'text-indigo-300', bg:'bg-indigo-900/30 border-indigo-600/40'},
          {l:'R² Score',      v:'0.94',       c:'text-green-300',  bg:'bg-green-900/30 border-green-600/40'},
          {l:'Saving Realization', v:'95.2%', c:'text-purple-300', bg:'bg-purple-900/30 border-purple-600/40'},
          {l:'Game Correction',v:'−15.8%',    c:'text-yellow-300', bg:'bg-yellow-900/30 border-yellow-600/40'},
        ].map((c,i)=>(
          <div key={i} className={`border rounded-xl p-4 text-center ${c.bg}`}>
            <p className="text-xs text-gray-400 mb-1">{c.l}</p>
            <p className={`text-2xl font-bold ${c.c}`}>{c.v}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Saving comparison bar */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-xs font-bold text-gray-300 mb-1">Naive vs Game-Adjusted vs Realized (₹/month)</h3>
          <p className="text-xs text-gray-500 mb-3">
            Naive ₹4,300 → Game-adjusted ₹3,620 (−15.8%) → Realized ₹2,901.70 (95.2% of forecast)
          </p>
          <ResponsiveContainer width="100%" height={170}>
            <BarChart data={savingData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937"/>
              <XAxis dataKey="name" tick={{fill:'#9ca3af',fontSize:9}} />
              <YAxis tick={{fill:'#6b7280',fontSize:9}} tickFormatter={v=>`₹${(v/1000).toFixed(1)}k`}/>
              <Tooltip contentStyle={{background:'#111827',border:'1px solid #374151',borderRadius:8,fontSize:11}}
                formatter={v=>[fmt(v),'Saving']}/>
              <Bar dataKey="value" radius={[6,6,0,0]}>
                {savingData.map((e,i)=><Cell key={i} fill={e.fill}/>)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex justify-around text-xs text-gray-400 mt-2">
            <span>23.2% naive</span>
            <span className="text-indigo-400">19.5% adjusted</span>
            <span className="text-green-400">15.6% realized</span>
          </div>
        </div>

        {/* Model MAPE comparison */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-xs font-bold text-gray-300 mb-3">Forecasting Model Comparison — MAPE (%)</h3>
          <ResponsiveContainer width="100%" height={130}>
            <BarChart data={modelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937"/>
              <XAxis dataKey="model" tick={{fill:'#9ca3af',fontSize:10}}/>
              <YAxis tick={{fill:'#6b7280',fontSize:9}} domain={[4,8]}/>
              <Tooltip contentStyle={{background:'#111827',border:'1px solid #374151',borderRadius:8,fontSize:11}}
                formatter={v=>[`${v}%`,'MAPE']}/>
              <Bar dataKey="mape" radius={[4,4,0,0]}>
                {modelData.map((e,i)=><Cell key={i} fill={e.fill}/>)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-3 space-y-1">
            {modelData.map((m,i)=>(
              <div key={i} className="flex justify-between text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full inline-block" style={{background:m.fill}}/>
                  <span className="text-gray-300 w-16">{m.model}</span>
                </span>
                <span className="text-gray-400">MAPE {m.mape}%</span>
                <span className="text-gray-400">R² {m.r2}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Nash equilibrium table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-xs font-bold text-gray-300 mb-3">Nash Equilibrium Pricing vs Current Rates (₹/month — 4vCPU 16GB)</h3>
        <table className="w-full text-xs">
          <thead><tr className="text-gray-400 border-b border-gray-700">
            {['Provider','Current','Equilibrium','Predicted 90d','Δ','Repricing Risk'].map(h=>(
              <th key={h} className="text-left py-1.5 pr-4">{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {nashData.map((r,i)=>{
              const d=r.pred90-r.current;
              return (
                <tr key={i} className="border-b border-gray-800/50">
                  <td className="py-2 pr-4 font-bold" style={{color:r.color}}>{r.provider}</td>
                  <td className="py-2 pr-4 text-gray-300">{fmt(r.current)}</td>
                  <td className="py-2 pr-4 text-indigo-300">{fmt(r.equilibrium)}</td>
                  <td className="py-2 pr-4 text-white font-bold">{fmt(r.pred90)}</td>
                  <td className={`py-2 pr-4 font-bold ${d>0?'text-red-400':'text-green-400'}`}>{d>0?'+':''}{fmt(d)}</td>
                  <td className="py-2">
                    <span className={`px-2 py-0.5 rounded-full font-bold text-xs ${r.risk==='MEDIUM'?'bg-yellow-900/50 text-yellow-300':'bg-green-900/50 text-green-300'}`}>{r.risk}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Game theory evidence table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-xs font-bold text-gray-300 mb-3">Per-Action Game-Theory Adjustment — Demand Signal Evidence</h3>
        <table className="w-full text-xs">
          <thead><tr className="text-gray-400 border-b border-gray-700">
            {['Action','Naive %','Adj %','Naive ₹/mo','Adj ₹/mo','Risk','Demand Signal'].map(h=>(
              <th key={h} className="text-left py-1.5 pr-3">{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {gtEvidence.map((r,i)=>(
              <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                <td className="py-2 pr-3 text-gray-200 font-medium" style={{fontSize:9}}>{r.action}</td>
                <td className="py-2 pr-3 text-gray-400">{r.naive}%</td>
                <td className={`py-2 pr-3 font-bold ${r.adjusted<r.naive?'text-yellow-400':'text-green-400'}`}>{r.adjusted}%</td>
                <td className="py-2 pr-3 text-gray-400">{fmt(r.naiveINR)}</td>
                <td className="py-2 pr-3 text-white font-bold">{fmt(r.adjINR)}</td>
                <td className="py-2 pr-3">
                  <span className={`px-1.5 py-0.5 rounded font-bold ${r.risk==='none'?'bg-green-900/50 text-green-300':r.risk==='low'?'bg-blue-900/50 text-blue-300':'bg-yellow-900/50 text-yellow-300'}`} style={{fontSize:9}}>{r.risk.toUpperCase()}</span>
                </td>
                <td className="py-2 text-gray-400" style={{fontSize:9}}>{r.signal}</td>
              </tr>
            ))}
            <tr className="border-t border-gray-600">
              <td className="py-2 font-bold text-white">TOTAL</td>
              <td/><td/>
              <td className="py-2 text-gray-400 font-bold">{fmt(gtEvidence.reduce((s,r)=>s+r.naiveINR,0))}</td>
              <td className="py-2 text-white font-bold">{fmt(gtEvidence.reduce((s,r)=>s+r.adjINR,0))}</td>
              <td colSpan={2} className="py-2 text-yellow-400 text-xs">−15.8% avg repricing reduction</td>
            </tr>
          </tbody>
        </table>
        <p className="text-xs text-gray-500 mt-3">
          <span className="text-indigo-400 font-bold">Model Agreement 87.3/100: </span>
          100×(1−σ/μ) across ARIMA, Prophet, XGBoost, Ensemble predictions. σ/μ=0.127 → predictions cluster within ±6.4%.
        </p>
      </div>

      <p className="text-xs text-gray-500 text-center border-t border-gray-800 pt-3">
        Figure A — Cross-Cloud Economic Game Theory · Snapshot a3f8b2c1 · 2026-08-28 · All values in INR · Synthetic demo data
      </p>
    </div>
  );
}

/* ── Figure B ── Twin-Plan Reversibility Gating ──────────────────────────── */
function FigureB() {
  const [tab, setTab] = useState('forward');

  const revDist = [
    {label:'Fully Reversible',    n:2, pct:50, color:'#22c55e', icon:'✅', route:'AUTO-EXECUTE eligible'},
    {label:'Partially Reversible',n:1, pct:25, color:'#f59e0b', icon:'⚠️', route:'MANUAL + user ACK required'},
    {label:'Irreversible',         n:1, pct:25, color:'#ef4444', icon:'🚫', route:'Always MANUAL approval'},
  ];

  const workloads = [
    {id:'W1', name:'Rightsize worker-dev',          rev:'FULLY_REVERSIBLE',     route:'AUTO_EXECUTE',  revert:'4 min', cost:'₹0',   conf:91, risk:18},
    {id:'W2', name:'Purchase Reserved Instances',   rev:'FULLY_REVERSIBLE',     route:'AUTO_EXECUTE',  revert:'4 min', cost:'₹0',   conf:89, risk:12},
    {id:'W3', name:'Migrate web-server AWS→GCP',    rev:'PARTIALLY_REVERSIBLE', route:'MANUAL_REVIEW', revert:'60 min',cost:'₹500', conf:82, risk:38},
    {id:'W4', name:'Terminate batch-processor',     rev:'IRREVERSIBLE',         route:'MANUAL_REVIEW', revert:'10 min',cost:'₹0',   conf:95, risk:45},
  ];

  const FWD=`# FORWARD PLAN — W1: Rightsize worker-dev
# t3.medium → t3.small | Saving ₹1,263/mo
# Route: AUTO_EXECUTE | Policy: PASS (sig: a3f8b2c1)
# Risk: 18/100 | Confidence: 91%

resource "aws_instance" "worker_dev" {
  instance_type = "t3.small"   # ← was t3.medium
  lifecycle { prevent_destroy = false }
}
output "saving_inr" { value = 1263 }
output "revert_minutes" { value = 4 }`;

  const RBK=`# ROLLBACK PLAN — W1: Restore worker-dev
# t3.small → t3.medium | PRE-VALIDATED ✓
# Revert: ~4 min | Downtime: 30s | Data loss: NONE

resource "aws_instance" "worker_dev" {
  instance_type = "t3.medium"  # ← ORIGINAL RESTORED
  lifecycle {
    prevent_destroy = true      # safety lock
  }
}
output "rollback_complete" {
  value = "Restored to t3.medium"
}`;

  const RC={'FULLY_REVERSIBLE':'text-green-400','PARTIALLY_REVERSIBLE':'text-yellow-400','IRREVERSIBLE':'text-red-400'};
  const RI={'FULLY_REVERSIBLE':'✅','PARTIALLY_REVERSIBLE':'⚠️','IRREVERSIBLE':'🚫'};
  const RR={'AUTO_EXECUTE':'text-indigo-400','MANUAL_REVIEW':'text-blue-400'};

  const steps=[
    'Generate forward Terraform plan',
    'Generate rollback (inverse) plan',
    'Dry-run forward: terraform plan',
    'Dry-run rollback: terraform plan ✓',
    'Classify reversibility class',
    'Compute cost-of-reversal (₹)',
    'Validate revert time (4 min)',
    'Generate policy signature',
  ];

  return (
    <div className="bg-gray-950 text-white p-8 space-y-6" style={{width:940}}>
      <div className="border-b border-gray-700 pb-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-green-600 flex items-center justify-center font-bold text-lg">B</div>
        <div>
          <h2 className="text-lg font-bold">Twin-Plan Reversibility Gating</h2>
          <p className="text-xs text-gray-400">Forward + inverse Terraform plans generated & dry-run validated before any action is surfaced</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          {l:'Twin-Plan Coverage',  v:'75.0%', s:'3 of 4 actions',         c:'text-green-300', bg:'bg-green-900/30 border-green-600/40'},
          {l:'Dry-run Pass Rate',   v:'100%',  s:'All plans validated',     c:'text-green-300', bg:'bg-green-900/30 border-green-600/40'},
          {l:'Mean Revert Time',    v:'4 min', s:'FULLY_REVERSIBLE actions',c:'text-indigo-300',bg:'bg-indigo-900/30 border-indigo-600/40'},
          {l:'Auto-Execute Count',  v:'2',     s:'FULLY_REVERSIBLE only',   c:'text-indigo-300',bg:'bg-indigo-900/30 border-indigo-600/40'},
        ].map((c,i)=>(
          <div key={i} className={`border rounded-xl p-4 text-center ${c.bg}`}>
            <p className="text-xs text-gray-400 mb-1">{c.l}</p>
            <p className={`text-2xl font-bold ${c.c}`}>{c.v}</p>
            <p className="text-xs text-gray-500 mt-1">{c.s}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Reversibility distribution */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-xs font-bold text-gray-300 mb-4">Reversibility Classification</h3>
          {revDist.map((r,i)=>(
            <div key={i} className="mb-3">
              <div className="flex justify-between text-xs mb-1">
                <span>{r.icon} <span className="text-gray-200 font-medium">{r.label}</span></span>
                <span className="text-gray-400">{r.n} action{r.n>1?'s':''} ({r.pct}%)</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-700 rounded-full h-3">
                  <div className="h-3 rounded-full" style={{width:`${r.pct}%`,background:r.color}}/>
                </div>
                <span className="text-xs w-40 shrink-0" style={{color:r.color}}>{r.route}</span>
              </div>
            </div>
          ))}

          <div className="mt-5 border-t border-gray-800 pt-4">
            <p className="text-xs font-bold text-gray-400 mb-2">8-Step Validation Pipeline (W1 trace):</p>
            {steps.map((s,i)=>(
              <div key={i} className="flex items-center gap-2 text-xs mb-1">
                <span className="text-green-400 font-bold">✓</span>
                <span className="text-gray-500 w-3">{i+1}.</span>
                <span className="text-gray-300">{s}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Terraform twin plan viewer */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-gray-300">W1 Twin Plan — worker-dev Rightsizing</h3>
            <div className="flex gap-1">
              {['forward','rollback'].map(t=>(
                <button key={t} onClick={()=>setTab(t)}
                  className={`text-xs px-3 py-1 rounded font-medium ${tab===t?'bg-indigo-600 text-white':'bg-gray-800 text-gray-400'}`}>
                  {t==='forward'?'▶ Forward':'↩ Rollback'}
                </button>
              ))}
            </div>
          </div>
          <div className={`text-xs px-3 py-1.5 rounded-lg mb-2 font-medium ${tab==='forward'?'bg-indigo-900/40 text-indigo-300':'bg-green-900/40 text-green-300'}`}>
            {tab==='forward'
              ? '▶ FORWARD: t3.medium → t3.small | Saving ₹1,263/mo | Policy sig: a3f8b2c1'
              : '↩ ROLLBACK: PRE-VALIDATED ✓ | Revert ~4 min | Zero data loss'}
          </div>
          <pre className="text-xs font-mono text-green-300 bg-gray-950 rounded-lg p-3 overflow-x-auto" style={{maxHeight:220,fontSize:10}}>
            {tab==='forward'?FWD:RBK}
          </pre>
          <div className="mt-3 bg-gray-800 rounded-lg p-2 text-xs">
            <span className="text-yellow-400 font-bold">Cost-of-Reversal: </span>
            <span className="text-white">₹0</span>
            <span className="text-gray-500 mx-3">|</span>
            <span className="text-yellow-400 font-bold">Revert Time: </span>
            <span className="text-white">4 min</span>
            <span className="text-gray-500 mx-3">|</span>
            <span className="text-yellow-400 font-bold">Downtime: </span>
            <span className="text-white">~30s</span>
          </div>
        </div>
      </div>

      {/* Workload table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-xs font-bold text-gray-300 mb-3">All Actions — Reversibility Classification Summary</h3>
        <table className="w-full text-xs">
          <thead><tr className="text-gray-400 border-b border-gray-700">
            {['ID','Action','Reversibility','Route','Revert Time','Revert Cost','Confidence','Risk Score'].map(h=>(
              <th key={h} className="text-left py-1.5 pr-3">{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {workloads.map((w,i)=>(
              <tr key={i} className="border-b border-gray-800/50">
                <td className="py-2 pr-3 font-bold text-indigo-400">{w.id}</td>
                <td className="py-2 pr-3 text-gray-200">{w.name}</td>
                <td className={`py-2 pr-3 font-bold text-xs ${RC[w.rev]}`}>{RI[w.rev]} {w.rev.replace(/_/g,' ')}</td>
                <td className={`py-2 pr-3 font-bold ${RR[w.route]}`}>{w.route==='AUTO_EXECUTE'?'⚡ AUTO':'👤 MANUAL'}</td>
                <td className="py-2 pr-3 text-gray-300">{w.revert}</td>
                <td className="py-2 pr-3 text-gray-300">{w.cost}</td>
                <td className="py-2 pr-3 text-green-300">{w.conf}%</td>
                <td className="py-2 text-gray-300">{w.risk}/100</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-yellow-400 mt-3">
          ⚠️ Only FULLY_REVERSIBLE actions are AUTO_EXECUTE eligible.
          PARTIALLY_REVERSIBLE requires user acknowledgment of what is lost.
          IRREVERSIBLE always routes to MANUAL regardless of confidence.
        </p>
      </div>

      <p className="text-xs text-gray-500 text-center border-t border-gray-800 pt-3">
        Figure B — Twin-Plan Reversibility Gating · Snapshot a3f8b2c1 · 2026-08-28 · Coverage 75.0% · Mean revert 4 min
      </p>
    </div>
  );
}

/* ── Figure C ── Policy-Locked Action Templates ──────────────────────────── */
function FigureC() {
  const actions = [
    {id:'W1', name:'Rightsize worker-dev',         result:'PASS', sig:'a3f8b2c1', route:'AUTO_EXECUTE',  violations:[]},
    {id:'W2', name:'Purchase Reserved Instances',  result:'PASS', sig:'b4e9c3d2', route:'AUTO_EXECUTE',  violations:[]},
    {id:'W3', name:'Migrate web-server AWS→GCP',   result:'PASS', sig:'c5f0d4e3', route:'MANUAL_REVIEW', violations:[]},
    {id:'W4', name:'Terminate batch-processor',    result:'PASS', sig:'d6g1e5f4', route:'MANUAL_REVIEW', violations:[]},
    {id:'W5', name:'Terminate api-server-prod',    result:'FAIL', sig:null,       route:'SUPPRESSED',    violations:['IAM-001 BLOCKER: confidence 0.68 < 0.90 (only 3 days CPU data, need 7)']},
  ];

  const categories = [
    {name:'IAM Boundaries',    pass:4, fail:1, w:'25%', color:'#6366f1'},
    {name:'Security Baseline', pass:3, fail:1, w:'20%', color:'#ef4444'},
    {name:'Compliance',        pass:5, fail:0, w:'15%', color:'#22c55e'},
    {name:'Tagging Rules',     pass:5, fail:0, w:'10%', color:'#f59e0b'},
    {name:'Region Policy',     pass:5, fail:0, w:'15%', color:'#8b5cf6'},
    {name:'Cost Governance',   pass:5, fail:0, w:'15%', color:'#06b6d4'},
  ];

  const audit = [
    {ts:'21:03:31.311',event:'W5 policy check',  r:'FAIL',  d:'IAM-001 BLOCKER: conf=0.68 < 0.90 threshold'},
    {ts:'21:03:31.344',event:'W1 policy check',  r:'PASS',  d:'8 checks passed · sig: a3f8b2c1'},
    {ts:'21:03:31.390',event:'W2 policy check',  r:'PASS',  d:'8 checks passed · sig: b4e9c3d2'},
    {ts:'21:03:31.412',event:'W3 policy check',  r:'PASS',  d:'6 checks passed · sig: c5f0d4e3'},
    {ts:'21:03:31.430',event:'W4 policy check',  r:'PASS',  d:'7 checks passed · sig: d6g1e5f4'},
    {ts:'21:06:34.000',event:'W1 execute logged',r:'AUDIT', d:'action_id: exe-w1-001 · sig verified: a3f8b2c1'},
    {ts:'21:06:34.010',event:'W2 execute logged',r:'AUDIT', d:'action_id: exe-w2-001 · sig verified: b4e9c3d2'},
  ];

  return (
    <div className="bg-gray-950 text-white p-8 space-y-6" style={{width:940}}>
      <div className="border-b border-gray-700 pb-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-yellow-600 flex items-center justify-center font-bold text-lg">C</div>
        <div>
          <h2 className="text-lg font-bold">Policy-Locked Action Templates</h2>
          <p className="text-xs text-gray-400">Every action checked against compiled policies before surfacing — violations discarded before any human sees them</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          {l:'Policy Pass Rate',       v:'75.0%', s:'4 of 5 actions cleared', c:'text-green-300',  bg:'bg-green-900/30 border-green-600/40'},
          {l:'Actions Suppressed',     v:'1',     s:'W5 — never shown to user',c:'text-red-300',   bg:'bg-red-900/30 border-red-600/40'},
          {l:'Audit Log Completeness', v:'100%',  s:'All outcomes logged',     c:'text-green-300',  bg:'bg-green-900/30 border-green-600/40'},
          {l:'Signatures Logged',      v:'4',     s:'One per approved action', c:'text-indigo-300', bg:'bg-indigo-900/30 border-indigo-600/40'},
        ].map((c,i)=>(
          <div key={i} className={`border rounded-xl p-4 text-center ${c.bg}`}>
            <p className="text-xs text-gray-400 mb-1">{c.l}</p>
            <p className={`text-2xl font-bold ${c.c}`}>{c.v}</p>
            <p className="text-xs text-gray-500 mt-1">{c.s}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Category pass/fail bars */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-xs font-bold text-gray-300 mb-4">Policy Checks by Category</h3>
          {categories.map((c,i)=>{
            const total=c.pass+c.fail;
            return (
              <div key={i} className="mb-3">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-300">{c.name}</span>
                  <span className="text-gray-400">{c.pass}/{total} passed · {c.w}</span>
                </div>
                <div className="flex h-2.5 rounded-full overflow-hidden bg-gray-700">
                  <div style={{width:`${c.pass/total*100}%`,background:'#22c55e'}}/>
                  {c.fail>0&&<div style={{width:`${c.fail/total*100}%`,background:'#ef4444'}}/>}
                </div>
              </div>
            );
          })}

          {/* Pipeline flow */}
          <div className="mt-5 border-t border-gray-800 pt-4">
            <p className="text-xs font-bold text-gray-400 mb-2">Policy Gate — Intercept Point:</p>
            <div className="flex items-center gap-1 text-xs flex-wrap">
              {['Generate Action','IAM Check','Security Check','Compliance Check','→ PASS? Surface','→ FAIL? Discard'].map((s,i)=>(
                <React.Fragment key={i}>
                  <div className={`px-2 py-1 rounded text-center leading-tight ${i>=4?(i===4?'bg-green-900/50 text-green-300 border border-green-700':'bg-red-900/50 text-red-300 border border-red-700'):'bg-gray-800 text-gray-300 border border-gray-700'}`}
                    style={{fontSize:9,minWidth:64}}>
                    {s}
                  </div>
                  {i<5&&<span className="text-gray-600">→</span>}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>

        {/* W5 violation detail */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-xs font-bold text-gray-300 mb-3">W5 — Suppressed Action Detail</h3>
          <div className="bg-red-900/20 border border-red-700/40 rounded-xl p-3 mb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold text-red-400 bg-red-900/60 px-2 py-0.5 rounded">BLOCKER</span>
              <span className="text-xs text-red-300 font-bold">IAM-001: Termination Confidence Gate</span>
            </div>
            {[
              ['Action',              'Terminate api-server-prod (m5.xlarge)'],
              ['Actual Confidence',   '0.68  ✗'],
              ['Required Confidence', '≥ 0.90'],
              ['CPU Data Coverage',   '3 days  ✗  (need 7 days)'],
              ['Avg CPU',             '8.2% (ambiguous — not clearly idle)'],
              ['Checked at',          '21:03:31.311Z'],
              ['Outcome',             '🚫 DISCARDED — never surfaced to any user'],
            ].map(([k,v],i)=>(
              <div key={i} className="flex gap-2 text-xs py-0.5">
                <span className="text-gray-400 w-36 shrink-0">{k}:</span>
                <span className={`${v.includes('✗')?'text-red-300':v.includes('DISCARDED')?'text-red-400 font-bold':'text-gray-200'}`}>{v}</span>
              </div>
            ))}
          </div>
          <div className="bg-yellow-900/20 border border-yellow-700/40 rounded-lg p-2">
            <p className="text-xs text-yellow-300">
              <span className="font-bold">Remediation: </span>
              Extend monitoring to 7 days. If avg CPU remains &lt;5%, confidence will exceed 0.90 threshold and action will be surfaced.
            </p>
          </div>
        </div>
      </div>

      {/* Action × policy result table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-xs font-bold text-gray-300 mb-3">Policy Check Outcomes — All 5 Actions</h3>
        <table className="w-full text-xs">
          <thead><tr className="text-gray-400 border-b border-gray-700">
            {['ID','Action','Result','Policy Signature','Route','Violations'].map(h=>(
              <th key={h} className="text-left py-1.5 pr-3">{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {actions.map((a,i)=>(
              <tr key={i} className={`border-b border-gray-800/50 ${a.result==='FAIL'?'opacity-70':''}`}>
                <td className="py-2 pr-3 font-bold text-indigo-400">{a.id}</td>
                <td className="py-2 pr-3 text-gray-200">{a.name}</td>
                <td className="py-2 pr-3">
                  <span className={`px-2 py-0.5 rounded-full font-bold ${a.result==='PASS'?'bg-green-900/50 text-green-300':'bg-red-900/50 text-red-300'}`}>
                    {a.result==='PASS'?'✓ PASS':'✗ FAIL'}
                  </span>
                </td>
                <td className="py-2 pr-3 font-mono text-indigo-400">
                  {a.sig||<span className="text-gray-600 not-italic">— (suppressed)</span>}
                </td>
                <td className="py-2 pr-3">
                  <span className={`font-bold ${a.route==='AUTO_EXECUTE'?'text-indigo-400':a.route==='MANUAL_REVIEW'?'text-blue-400':'text-gray-500'}`}>
                    {a.route==='AUTO_EXECUTE'?'⚡ AUTO':a.route==='MANUAL_REVIEW'?'👤 MANUAL':'🚫 SUPPRESSED'}
                  </span>
                </td>
                <td className="py-2 text-red-300" style={{fontSize:9}}>
                  {a.violations.length>0?a.violations[0]:<span className="text-gray-600">None</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Audit log */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-xs font-bold text-gray-300 mb-2">Audit Log — 100% Completeness (7 entries)</h3>
        <div className="bg-gray-950 rounded-lg p-3 space-y-1">
          {audit.map((e,i)=>(
            <div key={i} className="flex items-center gap-3 text-xs font-mono">
              <span className="text-gray-500">{e.ts}</span>
              <span className={`font-bold w-4 ${e.r==='PASS'?'text-green-400':e.r==='FAIL'?'text-red-400':'text-yellow-400'}`}>
                {e.r==='PASS'?'✓':e.r==='FAIL'?'✗':'◉'}
              </span>
              <span className="text-gray-300 w-36">{e.event}</span>
              <span className="text-gray-500">{e.d}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-gray-500 text-center border-t border-gray-800 pt-3">
        Figure C — Policy-Locked Action Templates · Snapshot a3f8b2c1 · 2026-08-28 · Pass 75.0% · Suppressed 1 · Audit 100%
      </p>
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────────────────────────── */
export default function PaperFigures() {
  const [tab, setTab] = useState('A');
  const tabs = [
    {id:'A', label:'A — Game Theory',    icon:'🎮', comp:<FigureA/>},
    {id:'B', label:'B — Reversibility',  icon:'🔄', comp:<FigureB/>},
    {id:'C', label:'C — Policy Locking', icon:'🔒', comp:<FigureC/>},
  ];
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-white">Paper Figures A · B · C</h1>
        <p className="text-xs text-gray-500 mt-0.5">Screenshot-ready · Numbers locked to paper text · Snapshot a3f8b2c1</p>
      </div>
      <div className="flex items-center gap-2">
        {tabs.map(t=>(
          <button key={t.id} onClick={()=>setTab(t.id)}
            className={`px-5 py-2 rounded-xl text-sm font-bold transition-all ${tab===t.id?'bg-indigo-600 text-white shadow-lg':'bg-gray-800 text-gray-400 hover:text-white'}`}>
            {t.icon} {t.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-500">Press F11 → full screen → Ctrl+Shift+S to screenshot</span>
      </div>
      <div className="rounded-2xl overflow-hidden border border-gray-800 shadow-2xl">
        {tabs.find(t=>t.id===tab)?.comp}
      </div>
    </div>
  );
}
