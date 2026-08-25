import React, { useEffect, useState } from 'react';
import { execution as execAPI } from '../services/api';

const TYPE_COLORS = {
  execution_action: 'bg-blue-900/40 text-blue-300',
  rollback:         'bg-red-900/40 text-red-300',
  approval:         'bg-green-900/40 text-green-300',
  user_action:      'bg-purple-900/40 text-purple-300',
  system_event:     'bg-gray-700 text-gray-300',
};

export default function AuditLogsPage() {
  const [logs, setLogs]   = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    execAPI.history({ limit: 100 })
      .then(d => setLogs(d.logs || []))
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter ? logs.filter(l => l.event_type === filter) : logs;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Audit Logs</h1>
        <select value={filter} onChange={e => setFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-1.5">
          <option value="">All Events</option>
          <option value="execution_action">Execution Actions</option>
          <option value="rollback">Rollbacks</option>
          <option value="approval">Approvals</option>
          <option value="user_action">User Actions</option>
        </select>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? <p className="p-6 text-gray-400 text-sm">Loading logs...</p> : (
          filtered.length === 0
            ? <p className="p-6 text-gray-400 text-sm">No audit logs found.</p>
            : <div className="divide-y divide-gray-800">
                {filtered.map((log, i) => (
                  <div key={log.log_id || i} className="px-5 py-4 hover:bg-gray-800/40 transition-colors">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLORS[log.event_type] || 'bg-gray-700 text-gray-300'}`}>
                            {log.event_type?.replace('_', ' ').toUpperCase()}
                          </span>
                          <span className="text-xs text-gray-400 font-mono">
                            {log.action || log.event || log.action_type || '—'}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5 flex gap-4 flex-wrap">
                          {log.provider && <span>Provider: {log.provider?.toUpperCase()}</span>}
                          {log.resource_id && <span>Resource: {log.resource_id?.slice(0,30)}</span>}
                          {log.status && <span className={log.status==='success'?'text-green-400':log.status==='failed'?'text-red-400':'text-gray-400'}>
                            Status: {log.status}
                          </span>}
                          {log.estimated_saving > 0 && <span className="text-green-400">Saving: ₹{Number(log.estimated_saving).toLocaleString('en-IN')}</span>}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-xs text-gray-500 font-mono">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString('en-IN') : '—'}
                        </p>
                        <p className="text-xs text-gray-600 font-mono mt-0.5">{(log.log_id || '').slice(0,8)}...</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
        )}
      </div>
    </div>
  );
}
