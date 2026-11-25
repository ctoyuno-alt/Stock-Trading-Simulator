/**
 * Unified API Client for Quantum Trader React Workstation.
 * Connects to FastAPI backend endpoints on port 8000 via relative dev proxy (/api) or direct URL.
 */

const BASE_URL = (import.meta as any).env?.VITE_BACKEND_URL || '';

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'trader' | 'viewer';
  is_active: boolean;
  api_key?: string;
  accounts?: Array<{
    id: number;
    account_name: string;
    equity: number;
    currency: string;
  }>;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('qt_auth_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('qt_auth_token', token);
    } else {
      localStorage.removeItem('qt_auth_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T = any>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${BASE_URL}${path}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const resp = await fetch(url, { ...options, headers });
      if (!resp.ok) {
        let errMessage = `HTTP ${resp.status} ${resp.statusText}`;
        try {
          const errBody = await resp.json();
          if (errBody && errBody.detail) {
            errMessage = typeof errBody.detail === 'string' ? errBody.detail : JSON.stringify(errBody.detail);
          }
        } catch (_) {}
        throw new Error(errMessage);
      }
      return (await resp.json()) as T;
    } catch (err: any) {
      console.error(`API Error on ${path}:`, err);
      throw err;
    }
  }

  // --- Auth Endpoints ---
  async login(username: string, password: string): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async register(username: string, email: string, password: string): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async getMe(): Promise<UserProfile> {
    return this.request<UserProfile>('/api/v1/auth/me');
  }

  async forgotPassword(username_or_email: string): Promise<{ message: string; reset_token?: string; expires_in_minutes: number }> {
    return this.request('/api/v1/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ username_or_email }),
    });
  }

  async resetPassword(token: string, new_password: string): Promise<{ message: string }> {
    return this.request('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    });
  }

  // --- Market & Universe ---
  async getUniverse(market: string = 'IN', search?: string, limit?: number): Promise<any[]> {
    const params = new URLSearchParams({ market });
    if (search) params.append('search', search);
    if (limit) params.append('limit', limit.toString());
    return this.request(`/api/v1/market-data/universe?${params.toString()}`);
  }

  async getCandles(symbol: string, timeframe: string = '1d', period: string = '6mo'): Promise<any> {
    return this.request(`/api/v1/market-data/candles/${symbol}?timeframe=${timeframe}&period=${period}`);
  }

  async getIndicators(symbol: string, timeframe: string = '1d'): Promise<any> {
    return this.request(`/api/v1/indicators/${symbol}?timeframe=${timeframe}&include_series=true`);
  }

  async getSignal(symbol: string, timeframe: string = '1d'): Promise<any> {
    return this.request(`/api/v1/strategies/signal/${symbol}?timeframe=${timeframe}`);
  }

  async getAiAnalysis(symbol: string, timeframe: string = '1d'): Promise<any> {
    return this.request(`/api/v1/ai/analyze/${symbol}`, {
      method: 'POST',
      body: JSON.stringify({ timeframe }),
    });
  }

  // --- Trading & Execution ---
  async getPortfolio(currency: string = 'INR'): Promise<any> {
    return this.request(`/api/v1/trading/portfolio?currency=${currency}`);
  }

  async getPositions(status_filter?: string, currency?: string): Promise<any[]> {
    const params = new URLSearchParams();
    if (status_filter) params.append('status_filter', status_filter);
    if (currency) params.append('currency', currency);
    return this.request(`/api/v1/trading/positions?${params.toString()}`);
  }

  async getOrders(limit: number = 50, currency?: string): Promise<any[]> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (currency) params.append('currency', currency);
    return this.request(`/api/v1/trading/orders?${params.toString()}`);
  }

  async getMetrics(currency: string = 'INR'): Promise<any> {
    return this.request(`/api/v1/trading/metrics?currency=${currency}`);
  }

  async placeBuyOrder(payload: {
    symbol: string;
    price: number;
    stop_loss_price: number;
    take_profit_price?: number;
    quantity?: number;
    enforce_market_hours?: boolean;
    reason?: string;
  }): Promise<any> {
    return this.request('/api/v1/trading/order', {
      method: 'POST',
      body: JSON.stringify({
        side: 'BUY',
        ...payload,
      }),
    });
  }

  async closePosition(positionId: number, reason: string = 'Manual Close'): Promise<any> {
    return this.request(`/api/v1/trading/positions/${positionId}/close`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  async runBacktest(params: {
    symbol: string;
    timeframe?: string;
    period?: string;
    initial_capital_inr?: number;
    max_risk_per_trade?: number;
    slippage_bps?: number;
  }): Promise<any> {
    return this.request('/api/v1/backtest/run', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  // --- System & Auto-Trader ---
  async getSystemStatus(): Promise<any> {
    return this.request('/api/v1/system/status');
  }

  async getHealthReady(): Promise<any> {
    return this.request('/health/ready');
  }

  async toggleKillSwitch(activate: boolean, reason: string = 'Terminal User Action'): Promise<any> {
    return this.request('/api/v1/system/kill-switch', {
      method: 'POST',
      body: JSON.stringify({ activate, reason }),
    });
  }

  async resetPaperAccount(currency: string = 'INR', initial_capital: number = 100000): Promise<any> {
    return this.request('/api/v1/trading/reset', {
      method: 'POST',
      body: JSON.stringify({ currency, initial_capital }),
    });
  }

  async runAutoTraderTick(market: string = 'IN', timeframe: string = '1d'): Promise<any> {
    return this.request(`/api/v1/autotrader/tick?market=${market}&timeframe=${timeframe}`, {
      method: 'POST',
    });
  }

  async getDaemonLogs(limit: number = 40): Promise<any> {
    return this.request(`/api/v1/autotrader/logs?limit=${limit}`);
  }

  // --- Admin Endpoints ---
  async getAdminUsers(params: { page?: number; limit?: number; role?: string; is_active?: boolean; search?: string }): Promise<any> {
    const q = new URLSearchParams();
    if (params.page) q.append('page', params.page.toString());
    if (params.limit) q.append('limit', params.limit.toString());
    if (params.role) q.append('role', params.role);
    if (params.is_active !== undefined) q.append('is_active', params.is_active ? 'true' : 'false');
    if (params.search) q.append('search', params.search);
    return this.request(`/api/v1/admin/users?${q.toString()}`);
  }

  async getAdminSummary(): Promise<any> {
    return this.request('/api/v1/admin/summary');
  }

  async updateUserRole(userId: number, role: string): Promise<any> {
    return this.request(`/api/v1/admin/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    });
  }

  async toggleUserStatus(userId: number, is_active: boolean, reason?: string): Promise<any> {
    return this.request(`/api/v1/admin/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active, reason }),
    });
  }

  async fundAccount(accountId: number, amount: number, reason?: string): Promise<any> {
    return this.request(`/api/v1/admin/accounts/${accountId}/fund`, {
      method: 'POST',
      body: JSON.stringify({ amount, reason }),
    });
  }

  async adminResetPassword(userId: number, new_password: string, reason?: string): Promise<any> {
    return this.request(`/api/v1/admin/users/${userId}/password`, {
      method: 'PUT',
      body: JSON.stringify({ new_password, reason }),
    });
  }

  async getAdminAuditLogs(page: number = 1, limit: number = 50, action?: string): Promise<any> {
    const q = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
    if (action) q.append('action', action);
    return this.request(`/api/v1/admin/audit-logs?${q.toString()}`);
  }
}

export const api = new ApiClient();
