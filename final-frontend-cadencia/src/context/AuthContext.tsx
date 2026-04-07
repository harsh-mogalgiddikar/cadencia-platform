'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api, setAccessToken } from '@/lib/api';
import type { User, Enterprise } from '@/types';
import { ROUTES } from '@/lib/constants';

interface AuthContextValue {
  user: User | null;
  enterprise: Enterprise | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: Record<string, unknown>) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  setEnterprise: (enterprise: Enterprise) => void;
  refreshProfile: () => Promise<void>;
  isAdmin: boolean;
  isBuyer: boolean;
  isSeller: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [enterprise, setEnterprise] = useState<Enterprise | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  /** Fetch user profile + enterprise using current access token */
  const fetchProfile = useCallback(async () => {
    try {
      const { data: meRes } = await api.get('/v1/auth/me');
      const me: User = meRes.data;
      setUser(me);

      if (me.enterprise_id) {
        const { data: entRes } = await api.get(`/v1/enterprises/${me.enterprise_id}`);
        setEnterprise(entRes.data);
      }
    } catch {
      // Profile fetch failed — clear auth state
      setAccessToken(null);
      setUser(null);
      setEnterprise(null);
    }
  }, []);

  // Silent refresh on mount
  useEffect(() => {
    const init = async () => {
      try {
        const { data } = await api.post('/v1/auth/refresh');
        setAccessToken(data.data.access_token);
        await fetchProfile();
      } catch {
        setAccessToken(null);
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, [fetchProfile]);

  const login = async (email: string, password: string) => {
    const { data } = await api.post('/v1/auth/login', { email, password });
    setAccessToken(data.data.access_token);
    await fetchProfile();
    router.push(ROUTES.DASHBOARD);
  };

  const register = async (payload: Record<string, unknown>) => {
    const { data } = await api.post('/v1/auth/register', payload);
    setAccessToken(data.data.access_token);
    await fetchProfile();
    router.push(ROUTES.DASHBOARD);
  };

  const logout = () => {
    setAccessToken(null);
    setUser(null);
    setEnterprise(null);
    router.push(ROUTES.LOGIN);
  };

  const isAdmin = user?.role === 'ADMIN';
  const isBuyer = enterprise?.trade_role === 'BUYER' || enterprise?.trade_role === 'BOTH';
  const isSeller = enterprise?.trade_role === 'SELLER' || enterprise?.trade_role === 'BOTH';

  return (
    <AuthContext.Provider value={{
      user, enterprise, isLoading,
      login, register, logout,
      setUser, setEnterprise,
      refreshProfile: fetchProfile,
      isAdmin, isBuyer, isSeller,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
