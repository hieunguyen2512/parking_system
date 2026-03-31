import { useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '../store/useStore';
import {
  LayoutDashboard, Car, History, Wallet, Bell, UserCircle,
} from 'lucide-react';

const NAV_ITEMS = [
  { path: '/dashboard',      icon: LayoutDashboard, label: 'Tổng quan' },
  { path: '/vehicles',       icon: Car,             label: 'Xe của tôi' },
  { path: '/sessions',       icon: History,         label: 'Lịch sử' },
  { path: '/wallet',         icon: Wallet,          label: 'Ví' },
  { path: '/notifications',  icon: Bell,            label: 'Thông báo' },
  { path: '/profile',        icon: UserCircle,      label: 'Hồ sơ' },
];

export default function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const unreadCount = useStore(s => s.unreadCount);

  return (
    <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md bg-white border-t border-slate-100 z-40">
      <div className="grid grid-cols-6 h-16">
        {NAV_ITEMS.map(({ path, icon: Icon, label }) => {
          const active = location.pathname === path;
          const isBell = path === '/notifications';
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`flex flex-col items-center justify-center gap-0.5 transition-colors
                ${active ? 'text-blue-600' : 'text-slate-400 hover:text-slate-600'}`}
            >
              <div className="relative">
                <Icon size={20} strokeWidth={active ? 2.5 : 1.8} />
                {isBell && unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold
                                   rounded-full min-w-[14px] h-[14px] flex items-center justify-center px-0.5">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </div>
              <span className="text-[10px] font-medium leading-none">{label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
