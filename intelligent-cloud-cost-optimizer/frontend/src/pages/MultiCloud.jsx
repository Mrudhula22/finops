import React, { useEffect, useState } from 'react';
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { multicloud as mc } from '../services/api';

const fmt = n => `₹${Number(n||0).toLocaleString('en-IN')}`;
const COLORS = { aws:'#FF9900', azure:'#0078D4', gcp:'#4285F4' };

export default function MultiCloudPage() {
  const [compare, setCompare]   = useState(null);
  const [security, setSecurity] = useState(null);
  const [pricing, setPricing]   = useState(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    Promise.all([mc.compareAll(), mc.security(), mc.pricing('compute')])
      .then(([c, s, p]) => { setCompare(c); setSecurity(s); setPricing(p); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-gray-400 text-sm">Loading multi-cloud data...</p>;

  const secScores = security?.scores || {};
  const radarData = [
    { metric:'IAM',        aws: secScores.aws?.iam_score||0,   azure: secScores.azure?.iam_score||0,   gcp: secScores.gcp?.iam_score||0 },
    { metric:'Encryption', aws: secScores.aws?.encryption_score||0, azure: secScores.azure?.encryption_score||0, gcp: secScores.gcp?.encryption_score||0 },
    { metric:'Network',    aws: secScores.aws?.network_score||0,   azure: secScores.azure?.network_score||0,   gcp: secScores.gcp?.network_score||0 },
    { metric:'Compliance', aws: secScores.aws?.compliance_score||0, azure: secScores.azure?.compliance_score||0, gcp: secScores.gcp?.compliance_score||0 },
    { metric:'Overall',    aws: secScores.aws?.overall_score||0,   azure: secScores.azure?.overall_score||0,   gcp: secScores.gcp?.overall_score||0 },
  ];

  const pricingData = (pricing?.pricing || []).map(p => ({
    size: p.size?.toUpperCase(), aws: p.aws, azure: p.azure, gcp: p.gcp
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">Multi-Cloud Comparison</h1>

      {/* Security ranking */}
      <div className="grid grid-cols-3 gap-4">
        {(security?.ranking || []).map((r,i) => (
          <div key={r.provider} className={`rounded-xl border p-4 ${i===0?'border-indigo-500/50 bg-indigo-900/20':'border-gray-800 bg-gray-900'}`}>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ background: COLORS[r.provider] }} />
              <span className="text-sm font-bold text-white">{r.provider.toUpperCase()}</span>
              {i===0 && <span className="text-xs text-indigo-300 bg-indigo-900/50 px-2 py-0.5 rounded-full">Best</span>}
            </div>
            <p className="text-3xl font-bold text-white">{r.score?.toFixed(0)}</p>
            <p className="text-xs text-gray-400 mt-1">Security Score / 100</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Radar chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Security Radar</h2>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#374151" />
              <PolarAngleAxis dataKey="metric" tick={{ fill:'#9ca3af', fontSize:11 }} />
              <Radar name="AWS"   dataKey="aws"   stroke="#FF9900" fill="#FF9900" fillOpacity={0.15} />
              <Radar name="Azure" dataKey="azure" stroke="#0078D4" fill="#0078D4" fillOpacity={0.15} />
              <Radar name="GCP"   dataKey="gcp"   stroke="#4285F4" fill="#4285F4" fillOpacity={0.15} />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Pricing comparison */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Compute Pricing (INR/month)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={pricingData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="size" tick={{ fill:'#9ca3af', fontSize:11 }} />
              <YAxis tick={{ fill:'#6b7280', fontSize:10 }} tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
              <Tooltip contentStyle={{ background:'#111827', border:'1px solid #374151', borderRadius:8 }}
                formatter={v => fmt(v)} />
              <Legend />
              <Bar dataKey="aws"   fill="#FF9900" name="AWS"   radius={[4,4,0,0]} />
              <Bar dataKey="azure" fill="#0078D4" name="Azure" radius={[4,4,0,0]} />
              <Bar dataKey="gcp"   fill="#4285F4" name="GCP"   radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Workload comparison table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-4">Workload Optimization Opportunities</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 text-xs border-b border-gray-800">
                <th className="text-left py-2 pr-4">Workload</th>
                <th className="text-left py-2 pr-4">Best Provider</th>
                <th className="text-right py-2 pr-4">Best Cost</th>
                <th className="text-right py-2 pr-4">Saving vs AWS</th>
                <th className="text-left py-2">Recommendation</th>
              </tr>
            </thead>
            <tbody>
              {(compare?.comparisons || []).map((c,i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-3 pr-4 text-gray-200">{c.workload}</td>
                  <td className="py-3 pr-4">
                    <span className="font-bold" style={{ color: COLORS[c.best_provider] || '#fff' }}>
                      {c.best_provider?.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right text-white">{fmt(c.best_cost)}</td>
                  <td className="py-3 pr-4 text-right text-green-400 font-medium">{fmt(c.saving_vs_aws)}</td>
                  <td className="py-3 text-xs text-gray-400">{c.recommendation?.slice(0,80)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {compare?.total_potential_saving > 0 && (
          <div className="mt-4 bg-green-900/20 border border-green-700/40 rounded-lg px-4 py-3">
            <p className="text-sm text-green-300">
              💰 Total potential saving across all workloads: <strong>{fmt(compare.total_potential_saving)}/month</strong>
              {' '}({fmt(compare.total_potential_saving * 12)}/year)
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
