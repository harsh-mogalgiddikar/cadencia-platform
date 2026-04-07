'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, setAccessToken } from '@/lib/api';
import type { User, Enterprise } from '@/types';
import { ROUTES } from '@/lib/constants';

interface AuthContextValue {
  user: User | null;
  enterprise: Enterprise | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  setEnterprise: (enterprise: Enterprise) => void;
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

  // Silent refresh on mount
  useEffect(() => {
    const init = async () => {
      try {
        const { data } = await api.post('/v1/auth/refresh');
        setAccessToken(data.data.access_token);
        // In future phases, fetch user profile here using the token
        // For Phase 0, use mock enterprise data
        const enterpriseRes = await api.get('/v1/enterprises/ent-001');
        setEnterprise(enterpriseRes.data.data);
      } catch {
        setAccessToken(null);
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, []);

  const login = async (email: string, password: string) => {
    const { data } = await api.post('/v1/auth/login', { email, password });
    setAccessToken(data.data.access_token);
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
      login, logout, setUser, setEnterprise,
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
