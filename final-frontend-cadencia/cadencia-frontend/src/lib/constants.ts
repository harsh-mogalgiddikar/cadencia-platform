export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const ROUTES = {
  LOGIN: '/login',
  REGISTER: '/register',
  DASHBOARD: '/dashboard',
  SETTINGS: '/settings',
  WALLET: '/settings/wallet',
  MARKETPLACE: '/marketplace',
  SELLER_PROFILE: '/marketplace/profile',
  NEGOTIATIONS: '/negotiations',
  ESCROW: '/escrow',
  COMPLIANCE: '/compliance',
  ADMIN: '/admin',
} as const;
