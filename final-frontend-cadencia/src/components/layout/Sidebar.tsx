'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, ShoppingCart, Handshake, Landmark, Banknote,
  ClipboardList, Settings, ShieldCheck, LogOut, Building2,
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';

const navItems = [
  { label: 'Dashboard',    href: ROUTES.DASHBOARD,     icon: LayoutDashboard },
  { label: 'Marketplace',  href: ROUTES.MARKETPLACE,   icon: ShoppingCart },
  { label: 'Negotiations', href: ROUTES.NEGOTIATIONS,  icon: Handshake },
  { label: 'Escrow',       href: ROUTES.ESCROW,        icon: Landmark },
  { label: 'Treasury',     href: ROUTES.TREASURY,      icon: Banknote },
  { label: 'Compliance',   href: ROUTES.COMPLIANCE,    icon: ClipboardList },
  { label: 'Settings',     href: ROUTES.SETTINGS,      icon: Settings },
];

const adminItem = { label: 'Admin', href: ROUTES.ADMIN, icon: ShieldCheck };

export function Sidebar() {
  const pathname = usePathname();
  const { enterprise, user, logout, isAdmin } = useAuth();

  const allItems = isAdmin ? [...navItems, adminItem] : navItems;

  return (
    <aside className="w-60 min-h-screen bg-sidebar border-r border-sidebar-border flex flex-col shrink-0">

      {/* Enterprise header */}
      <div className="p-4 border-b border-sidebar-border">
        <div className="flex items-center gap-2 mb-2">
          <div className="bg-sidebar-accent rounded-md p-1.5">
            <Building2 className="h-4 w-4 text-sidebar-foreground" />
          </div>
          <span className="text-sm font-semibold text-sidebar-foreground truncate">
            {enterprise?.legal_name ?? 'Cadencia'}
          </span>
        </div>
        {enterprise?.kyc_status && (
          <StatusBadge status={enterprise.kyc_status} size="sm" />
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 p-3 space-y-0.5">
        {allItems.map(({ label, href, icon: Icon }) => {
          const isActive = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-secondary text-primary font-medium'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-sidebar-border">
        <div className="flex items-center justify-between px-2 py-1.5">
          <div className="min-w-0">
            <p className="text-sm font-medium text-sidebar-foreground truncate">
              {user?.full_name ?? 'User'}
            </p>
            <p className="text-xs text-muted-foreground truncate">
              {user?.email ?? ''}
            </p>
          </div>
          <button
            onClick={logout}
            className="ml-2 p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-sidebar-accent transition-colors shrink-0"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>

    </aside>
  );
}
