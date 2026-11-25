import React, { useState } from 'react';
import { api } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Lock, Mail, User, Key, CheckCircle, AlertCircle } from 'lucide-react';

interface AuthModalProps {
  onSuccess?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ onSuccess }) => {
  const { login: setAuthSession } = useAuth();
  const [activeTab, setActiveTab] = useState<'signin' | 'register' | 'forgot'>('signin');

  // Form states
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin_secure_password');
  const [email, setEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');

  // Forgot password states
  const [forgotIdentifier, setForgotIdentifier] = useState('');
  const [recoveryToken, setRecoveryToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Status feedback
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.login(username, password);
      setAuthSession(res.access_token, res.user);
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (regPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    setLoading(true);
    try {
      const res = await api.register(username, email, regPassword);
      setAuthSession(res.access_token, res.user);
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestRecoveryToken = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const res = await api.forgotPassword(forgotIdentifier);
      if (res.reset_token) {
        setRecoveryToken(res.reset_token);
        setSuccess(`Recovery token issued! Valid for ${res.expires_in_minutes || 15} minutes.`);
      } else {
        setSuccess(res.message);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to request recovery token.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (!recoveryToken) {
      setError('Please provide a valid recovery token.');
      return;
    }
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const res = await api.resetPassword(recoveryToken, newPassword);
      setSuccess(`${res.message} You can now sign in.`);
      setPassword(newPassword);
      setActiveTab('signin');
    } catch (err: any) {
      setError(err.message || 'Password reset failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-obsidian-950/90 backdrop-blur-md flex items-center justify-center p-4 z-50">
      <div className="w-full max-w-md bg-obsidian-900 border border-border-medium rounded-xl shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-6 text-center border-b border-border-medium">
          <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-bloomberg-amber/15 border border-bloomberg-amber/30 flex items-center justify-center text-2xl shadow-inner">
            ⚡
          </div>
          <h2 className="text-xl font-bold tracking-wider text-slate-100 font-sans">QUANTUM TRADER</h2>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Institutional AI Paper Trading & Analytics Terminal
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="grid grid-cols-3 border-b border-border-medium bg-obsidian-950/50 text-xs font-semibold">
          <button
            onClick={() => { setActiveTab('signin'); setError(null); }}
            className={`py-2.5 transition border-b-2 ${
              activeTab === 'signin'
                ? 'border-bloomberg-amber text-bloomberg-amber bg-obsidian-900 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            🔐 Sign In
          </button>
          <button
            onClick={() => { setActiveTab('register'); setError(null); }}
            className={`py-2.5 transition border-b-2 ${
              activeTab === 'register'
                ? 'border-bloomberg-amber text-bloomberg-amber bg-obsidian-900 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            ✨ Register
          </button>
          <button
            onClick={() => { setActiveTab('forgot'); setError(null); }}
            className={`py-2.5 transition border-b-2 ${
              activeTab === 'forgot'
                ? 'border-bloomberg-amber text-bloomberg-amber bg-obsidian-900 font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            🔑 Forgot?
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 rounded-lg bg-neon-green/10 border border-neon-green/20 text-neon-green text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {/* 1. SIGN IN TAB */}
          {activeTab === 'signin' && (
            <form onSubmit={handleSignIn} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Username or Email</label>
                <div className="relative">
                  <User className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-bloomberg-amber"
                    placeholder="admin or trader_one"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-bloomberg-amber"
                    placeholder="Enter your password"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-bloomberg-amber hover:bg-bloomberg-orange text-black font-bold text-sm tracking-wide transition shadow-md disabled:opacity-50"
              >
                {loading ? 'Authenticating...' : 'Sign In to Terminal'}
              </button>

              <div className="p-2.5 rounded bg-white/5 border border-white/5 text-[11px] text-slate-400 font-mono text-center">
                💡 Default Admin: <code className="text-slate-200">admin</code> / <code className="text-slate-200">admin_secure_password</code>
              </div>
            </form>
          )}

          {/* 2. REGISTER TAB */}
          {activeTab === 'register' && (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Trader Username</label>
                <div className="relative">
                  <User className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-bloomberg-amber"
                    placeholder="pro_trader"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-bloomberg-amber"
                    placeholder="trader@quantum.ai"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">Password (Min 8 chars)</label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="password"
                    required
                    value={regPassword}
                    onChange={e => setRegPassword(e.target.value)}
                    className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-bloomberg-amber"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-bloomberg-amber hover:bg-bloomberg-orange text-black font-bold text-sm tracking-wide transition shadow-md disabled:opacity-50"
              >
                {loading ? 'Creating Account...' : 'Register & Launch Terminal'}
              </button>
            </form>
          )}

          {/* 3. FORGOT PASSWORD TAB */}
          {activeTab === 'forgot' && (
            <div className="space-y-4">
              {/* Step 1: Request Token */}
              <form onSubmit={handleRequestRecoveryToken} className="space-y-2">
                <label className="block text-xs font-mono text-slate-400">Step 1: Request 15-Min Token</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    required
                    value={forgotIdentifier}
                    onChange={e => setForgotIdentifier(e.target.value)}
                    className="flex-1 bg-obsidian-950 border border-border-medium rounded-lg py-2 px-3 text-xs text-slate-100 focus:outline-none focus:border-bloomberg-amber"
                    placeholder="Username or email"
                  />
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-3 py-2 bg-white/10 hover:bg-white/15 text-xs font-semibold rounded-lg text-slate-200 transition"
                  >
                    Generate
                  </button>
                </div>
              </form>

              {/* Step 2: Apply Token */}
              <form onSubmit={handleResetPassword} className="space-y-3 pt-2 border-t border-border-medium">
                <label className="block text-xs font-mono text-slate-400">Step 2: Enter Token & New Password</label>
                <input
                  type="text"
                  required
                  value={recoveryToken}
                  onChange={e => setRecoveryToken(e.target.value)}
                  className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-1.5 px-3 text-xs text-slate-100 font-mono focus:outline-none focus:border-bloomberg-amber"
                  placeholder="Paste 15-minute recovery token"
                />
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-1.5 px-3 text-xs text-slate-100 focus:outline-none focus:border-bloomberg-amber"
                  placeholder="New password (8+ chars)"
                />
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  className="w-full bg-obsidian-950 border border-border-medium rounded-lg py-1.5 px-3 text-xs text-slate-100 focus:outline-none focus:border-bloomberg-amber"
                  placeholder="Confirm new password"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2 bg-bloomberg-amber hover:bg-bloomberg-orange text-black font-bold text-xs tracking-wide rounded-lg transition"
                >
                  {loading ? 'Updating Password...' : 'Reset Password & Proceed'}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
