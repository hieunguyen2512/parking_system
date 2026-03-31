import { create } from 'zustand';
import {
  authApi, vehiclesApi, walletApi,
  sessionsApi, authorizationsApi, notificationsApi,
} from '../api/services';

export const useStore = create((set, get) => ({
  // ── Auth ─────────────────────────────────────────────────────
  isAuthenticated: !!localStorage.getItem('user_token'),
  currentUser: JSON.parse(localStorage.getItem('user_info') || 'null'),

  async login(phone_number, password) {
    const data = await authApi.login(phone_number, password);
    localStorage.setItem('user_token', data.token);
    localStorage.setItem('user_info', JSON.stringify(data.user));
    set({ isAuthenticated: true, currentUser: data.user });
  },

  async register(formData) {
    const data = await authApi.register(formData);
    return data;
  },

  async logout() {
    try { await authApi.logout(); } catch {}
    localStorage.removeItem('user_token');
    localStorage.removeItem('user_info');
    set({
      isAuthenticated: false, currentUser: null,
      wallet: null, vehicles: [], sessions: [], activeSessions: [],
      notifications: [], unreadCount: 0,
    });
  },

  async fetchMe() {
    try {
      const data = await authApi.me();
      const user = {
        id: data.id, full_name: data.full_name,
        phone_number: data.phone_number, avatar_path: data.avatar_path,
        is_verified: data.is_verified,
      };
      localStorage.setItem('user_info', JSON.stringify(user));
      set({
        currentUser: user,
        wallet: { balance: data.balance, low_balance_threshold: data.low_balance_threshold },
      });
    } catch {}
  },

  // ── Wallet ──────────────────────────────────────────────────
  wallet: null,
  walletTransactions: [],
  walletPage: 1,
  walletTotal: 0,

  async fetchWallet() {
    try {
      const data = await walletApi.info();
      set({ wallet: data });
    } catch {}
  },

  async fetchTransactions(page = 1) {
    try {
      const data = await walletApi.transactions(page, 20);
      set({ walletTransactions: data.transactions, walletPage: page, walletTotal: data.total });
    } catch {}
  },

  async topup(amount, gateway) {
    const data = await walletApi.topup({ amount, payment_gateway: gateway });
    set(state => ({
      wallet: state.wallet ? { ...state.wallet, balance: data.new_balance } : null,
    }));
    return data;
  },

  // ── Vehicles ────────────────────────────────────────────────
  vehicles: [],

  async fetchVehicles() {
    try {
      const data = await vehiclesApi.list();
      set({ vehicles: data });
    } catch {}
  },

  async addVehicle(formData) {
    const data = await vehiclesApi.add(formData);
    set(state => ({ vehicles: [data, ...state.vehicles] }));
    return data;
  },

  async updateVehicle(id, formData) {
    const data = await vehiclesApi.update(id, formData);
    set(state => ({
      vehicles: state.vehicles.map(v => v.id === id ? { ...v, ...data } : v),
    }));
  },

  async removeVehicle(id) {
    await vehiclesApi.remove(id);
    set(state => ({ vehicles: state.vehicles.filter(v => v.id !== id) }));
  },

  // ── Sessions ────────────────────────────────────────────────
  sessions: [],
  sessionsPage: 1,
  sessionsTotal: 0,
  activeSessions: [],

  async fetchActiveSessions() {
    try {
      const data = await sessionsApi.active();
      set({ activeSessions: data });
    } catch {}
  },

  async fetchSessions(page = 1, status) {
    try {
      const params = { page, limit: 10 };
      if (status) params.status = status;
      const data = await sessionsApi.list(params);
      set({ sessions: data.sessions, sessionsPage: page, sessionsTotal: data.total });
    } catch {}
  },

  // ── Authorizations ──────────────────────────────────────────
  authorizations: [],

  async fetchAuthorizations() {
    try {
      const data = await authorizationsApi.list();
      set({ authorizations: data });
    } catch {}
  },

  async revokeAuthorization(id) {
    await authorizationsApi.revoke(id);
    set(state => ({
      authorizations: state.authorizations.map(a =>
        a.id === id ? { ...a, is_active: false } : a
      ),
    }));
  },

  // ── Notifications ───────────────────────────────────────────
  notifications: [],
  unreadCount: 0,
  notifPage: 1,

  async fetchNotifications(page = 1) {
    try {
      const data = await notificationsApi.list(page, 20);
      set({ notifications: data.notifications, unreadCount: data.unread_count, notifPage: page });
    } catch {}
  },

  async markNotificationRead(id) {
    try {
      await notificationsApi.markRead(id);
      set(state => ({
        notifications: state.notifications.map(n => n.id === id ? { ...n, is_read: true } : n),
        unreadCount: Math.max(0, state.unreadCount - 1),
      }));
    } catch {}
  },

  async markAllRead() {
    try {
      await notificationsApi.readAll();
      set(state => ({
        notifications: state.notifications.map(n => ({ ...n, is_read: true })),
        unreadCount: 0,
      }));
    } catch {}
  },
}));
