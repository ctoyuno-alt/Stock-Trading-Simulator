import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, UserProfile } from '../lib/api';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  isAdmin: boolean;
  login: (token: string, user: UserProfile) => void;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(() => api.getToken());
  const [loading, setLoading] = useState<boolean>(true);

  const refreshProfile = async () => {
    const currentToken = api.getToken();
    if (!currentToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const profile = await api.getMe();
      setUser(profile);
    } catch (err) {
      console.warn('Failed to restore session profile:', err);
      api.setToken(null);
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshProfile();
  }, []);

  const login = (newToken: string, newUser: UserProfile) => {
    api.setToken(newToken);
    setToken(newToken);
    setUser(newUser);
  };

  const logout = () => {
    api.setToken(null);
    setToken(null);
    setUser(null);
  };

  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        isAdmin,
        login,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
