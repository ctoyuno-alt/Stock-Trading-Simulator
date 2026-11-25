import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Shield, Users, Key, DollarSign, RotateCcw, AlertTriangle, CheckCircle2 } from 'lucide-react';

export const AdminTab: React.FC = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');

  // Password reset dialog state
  const [targetUser, setTargetUser] = useState<any>(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetReason, setResetReason] = useState('');
  const [statusFeedback, setStatusFeedback] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [uRes, sRes, aRes] = await Promise.all([
        api.getAdminUsers({ search: search || undefined, role: roleFilter || undefined }),
        api.getAdminSummary(),
        api.getAdminAuditLogs(1, 30),
      ]);
      setUsers(uRes?.users || []);
      setSummary(sRes || null);
      setAuditLogs(aRes?.logs || []);
    } catch (err) {
      console.error('Failed to load admin data:', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search, roleFilter]);

  const handleUpdateRole = async (userId: number, role: string) => {
    try {
      await api.updateUserRole(userId, role);
      setStatusFeedback(`Role updated to ${role} successfully.`);
      fetchData();
    } catch (err: any) {
      alert(`Role update failed: ${err.message}`);
    }
  };

  const handleToggleStatus = async (userId: number, currentActive: boolean) => {
    try {
      await api.toggleUserStatus(userId, !currentActive, 'Admin Toggle in React Workbench');
      setStatusFeedback(`User ${currentActive ? 'deactivated' : 'reactivated'} successfully.`);
      fetchData();
    } catch (err: any) {
      alert(`Status toggle failed: ${err.message}`);
    }
  };

  const handleAdminResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetUser) return;
    if (newPassword.length < 8) {
      alert('Password must be at least 8 characters long.');
      return;
    }
    try {
      const res = await api.adminResetPassword(targetUser.id, newPassword, resetReason || 'Admin password reset');
      setStatusFeedback(res.message);
      setTargetUser(null);
      setNewPassword('');
      setResetReason('');
      fetchData();
    } catch (err: any) {
      alert(`Password override failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-4">
      {/* 1. Admin KPI Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Total Registered Users</div>
          <div className="text-xl font-bold text-slate-100 mt-0.5">{summary?.total_users || users.length}</div>
          <div className="text-[10px] text-neon-green mt-1">{summary?.active_users || users.length} Active</div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Operational Accounts</div>
          <div className="text-xl font-bold text-slate-100 mt-0.5">{summary?.active_accounts || users.length}</div>
          <div className="text-[10px] text-neon-cyan mt-1">Multi-Tenant Portfolios</div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Total Managed Capital</div>
          <div className="text-xl font-bold text-bloomberg-amber mt-0.5">
            ₹{summary?.total_capital_inr ? Number(summary.total_capital_inr).toLocaleString() : '1,000,000'}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">INR Paper Capital</div>
        </div>

        <div className="bg-obsidian-900 border border-border-medium rounded-xl p-3.5 font-mono">
          <div className="text-[10px] text-slate-400 uppercase">Audit Trail Events</div>
          <div className="text-xl font-bold text-slate-100 mt-0.5">{summary?.audit_events_count || auditLogs.length}</div>
          <div className="text-[10px] text-neon-green mt-1">Immutable Log Records</div>
        </div>
      </div>

      {statusFeedback && (
        <div className="p-3 bg-neon-green/10 border border-neon-green/30 text-neon-green rounded-lg text-xs font-mono flex items-center justify-between">
          <span>{statusFeedback}</span>
          <button onClick={() => setStatusFeedback(null)} className="text-slate-400 hover:text-slate-200">×</button>
        </div>
      )}

      {/* 2. User Directory Table */}
      <div className="bg-obsidian-900 border border-border-medium rounded-xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-border-medium flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-100 font-sans">
            <Users className="w-4 h-4 text-neon-cyan" />
            User Directory & RBAC Workbench
          </div>

          <div className="flex gap-2 text-xs font-mono">
            <input
              type="text"
              placeholder="Search user or email..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="bg-obsidian-950 border border-border-medium rounded px-2.5 py-1 text-slate-200 placeholder-slate-500 focus:outline-none"
            />
            <select
              value={roleFilter}
              onChange={e => setRoleFilter(e.target.value)}
              className="bg-obsidian-950 border border-border-medium rounded px-2.5 py-1 text-slate-200 focus:outline-none"
            >
              <option value="">All Roles</option>
              <option value="admin">Admin</option>
              <option value="trader">Trader</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-obsidian-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-border-medium">
              <tr>
                <th className="p-3">ID</th>
                <th className="p-3">Username</th>
                <th className="p-3">Email</th>
                <th className="p-3">Role</th>
                <th className="p-3">Status</th>
                <th className="p-3">Capital (INR)</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-medium text-slate-200">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-white/[0.02] transition">
                  <td className="p-3 text-slate-400">#{u.id}</td>
                  <td className="p-3 font-bold text-slate-100">{u.username}</td>
                  <td className="p-3 text-slate-400">{u.email}</td>
                  <td className="p-3">
                    <select
                      value={u.role}
                      onChange={e => handleUpdateRole(u.id, e.target.value)}
                      className="bg-obsidian-950 border border-border-medium rounded px-2 py-0.5 text-xs text-bloomberg-amber font-semibold uppercase"
                    >
                      <option value="admin">ADMIN</option>
                      <option value="trader">TRADER</option>
                      <option value="viewer">VIEWER</option>
                    </select>
                  </td>
                  <td className="p-3">
                    <button
                      onClick={() => handleToggleStatus(u.id, u.is_active)}
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        u.is_active
                          ? 'bg-neon-green/10 border-neon-green/30 text-neon-green'
                          : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                      }`}
                    >
                      {u.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </button>
                  </td>
                  <td className="p-3">₹{u.total_equity_inr ? Number(u.total_equity_inr).toLocaleString() : '100,000'}</td>
                  <td className="p-3 text-right space-x-2">
                    <button
                      onClick={() => setTargetUser(u)}
                      className="px-2 py-1 bg-bloomberg-amber/15 hover:bg-bloomberg-amber/25 border border-bloomberg-amber/30 text-bloomberg-amber rounded text-[11px] font-semibold transition"
                    >
                      Reset Password
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Password Reset Modal */}
      {targetUser && (
        <div className="fixed inset-0 bg-obsidian-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-sm bg-obsidian-900 border border-border-medium rounded-xl p-5 shadow-2xl space-y-4">
            <h4 className="text-sm font-bold text-slate-100 font-sans border-b border-border-medium pb-2">
              🔑 Administrative Password Override for {targetUser.username}
            </h4>
            <form onSubmit={handleAdminResetPassword} className="space-y-3 font-mono text-xs">
              <div>
                <label className="block text-slate-400 mb-1">New Password (8+ chars)</label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  className="w-full bg-obsidian-950 border border-border-medium rounded p-2 text-slate-100 focus:outline-none focus:border-bloomberg-amber"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Reason for Override</label>
                <input
                  type="text"
                  value={resetReason}
                  onChange={e => setResetReason(e.target.value)}
                  className="w-full bg-obsidian-950 border border-border-medium rounded p-2 text-slate-100 focus:outline-none focus:border-bloomberg-amber"
                  placeholder="e.g. User requested unlock"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setTargetUser(null)}
                  className="flex-1 py-2 bg-white/5 hover:bg-white/10 rounded text-slate-300 font-bold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 bg-bloomberg-amber hover:bg-bloomberg-orange text-black font-bold rounded"
                >
                  Confirm Reset
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
