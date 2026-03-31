import { create } from 'zustand'
import { authApi, dashboardApi, sessionsApi, devicesApi, alertsApi, configApi, barriersApi } from '../api/services'
import {
  mockAlerts, mockDevices, mockActiveSessions,
  mockPricing, mockSystemConfig, mockLot,
} from '../data/mockData'

// Kiểm tra backend có sẵn không
async function isBackendAvailable() {
  try {
    const res = await fetch((import.meta.env.VITE_API_URL || 'http://localhost:4000/api') + '/health', { signal: AbortSignal.timeout(1500) })
    return res.ok
  } catch { return false }
}

export const useStore = create((set, get) => ({
  // ── Auth ────────────────────────────────────────────────────
  isAuthenticated: !!localStorage.getItem('admin_token'),
  currentAdmin: JSON.parse(localStorage.getItem('admin_info') || 'null'),
  useApi: false, // sẽ được set true nếu backend online

  // Kiểm tra backend khi app khởi động (tránh mất useApi sau khi reload trang)
  async initApi() {
    if (!localStorage.getItem('admin_token')) return
    const ok = await isBackendAvailable()
    if (ok) set({ useApi: true })
  },

  async login(credentials) {
    const backendUp = await isBackendAvailable()
    if (backendUp) {
      try {
        const data = await authApi.login(credentials.username, credentials.password)
        localStorage.setItem('admin_token', data.token)
        localStorage.setItem('admin_info', JSON.stringify(data.admin))
        set({ isAuthenticated: true, currentAdmin: data.admin, useApi: true })
        return true
      } catch (err) {
        throw err
      }
    }
    // Fallback mock khi không có backend
    if (credentials.username === 'admin' && credentials.password === 'admin123') {
      const admin = { id: 'adm-001', username: 'admin', full_name: 'Quản trị viên', role: 'superadmin' }
      localStorage.setItem('admin_info', JSON.stringify(admin))
      set({ isAuthenticated: true, currentAdmin: admin, useApi: false })
      return true
    }
    throw new Error('Sai tài khoản hoặc mật khẩu')
  },

  async logout() {
    if (get().useApi) {
      try { await authApi.logout() } catch {}
    }
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_info')
    set({ isAuthenticated: false, currentAdmin: null, useApi: false })
  },

  // ── Lot / Dashboard stats ────────────────────────────────────
  lot: { ...mockLot },
  dashboardStats: null,

  async fetchDashboardStats() {
    if (!get().useApi) return
    try {
      const stats = await dashboardApi.stats()
      set({ dashboardStats: stats })
    } catch {}
  },

  // ── Devices ─────────────────────────────────────────────────
  devices: mockDevices.map(d => ({ ...d })),

  async fetchDevices() {
    if (!get().useApi) return
    try {
      const data = await devicesApi.list()
      set({ devices: data })
    } catch {}
  },

  async updateDeviceStatus(device_id, status, note) {
    if (get().useApi) {
      try {
        const updated = await devicesApi.setStatus(device_id, status, note)
        set(s => ({ devices: s.devices.map(d => d.id === device_id ? updated : d) }))
        return
      } catch {}
    }
    set(s => ({
      devices: s.devices.map(d =>
        d.device_id === device_id ? { ...d, status, last_heartbeat: new Date() } : d
      ),
    }))
  },

  // ── Active Sessions ──────────────────────────────────────────
  activeSessions: mockActiveSessions.map(s => ({ ...s })),

  async fetchActiveSessions() {
    if (!get().useApi) return
    try {
      const res = await sessionsApi.list({ status: 'active', limit: 100 })
      set({ activeSessions: res.data || [] })
    } catch {}
  },

  // ── Alerts ──────────────────────────────────────────────────
  alerts: mockAlerts.map(a => ({ ...a })),

  async fetchAlerts() {
    if (!get().useApi) return
    try {
      const res = await alertsApi.list({ limit: 100 })
      set({ alerts: res.data })
    } catch {}
  },

  async resolveAlert(alertId, note) {
    if (get().useApi) {
      try {
        await alertsApi.resolve(alertId, note)
        await get().fetchAlerts()
        return
      } catch {}
    }
    set(s => ({
      alerts: s.alerts.map(a =>
        (a.alert_id === alertId || a.id === alertId)
          ? { ...a, status: 'resolved', is_resolved: true, resolved_at: new Date(), resolution_note: note }
          : a
      ),
    }))
  },

  get unresolvedCount() {
    return get().alerts.filter(a => a.status === 'unresolved' || !a.is_resolved).length
  },

  // ── Pricing ─────────────────────────────────────────────────
  pricing: mockPricing.map(p => ({ ...p })),

  async fetchPricing() {
    if (!get().useApi) return
    try {
      const data = await configApi.getPricing()
      set({ pricing: data })
    } catch {}
  },

  async updatePricing(id, fields) {
    if (get().useApi) {
      try {
        await configApi.updatePricing(id, fields)
        await get().fetchPricing()
        return
      } catch {}
    }
    set(s => ({
      pricing: s.pricing.map(p => (p.id === id || p.config_id === id) ? { ...p, ...fields } : p),
    }))
  },

  // ── System Config ───────────────────────────────────────────
  systemConfig: mockSystemConfig.map(c => ({ ...c })),

  async fetchSystemConfig() {
    if (!get().useApi) return
    try {
      const data = await configApi.getSystem()
      set({ systemConfig: data })
    } catch {}
  },

  async updateConfig(key, value) {
    if (get().useApi) {
      try {
        await configApi.updateSystem({ [key]: value })
        await get().fetchSystemConfig()
        return
      } catch {}
    }
    set(s => ({
      systemConfig: s.systemConfig.map(c =>
        (c.key === key || c.config_key === key) ? { ...c, value, config_value: value } : c
      ),
    }))
  },

  // ── Manual Barrier ──────────────────────────────────────────
  barrierLogs: [],

  async openBarrierManual(deviceId, reason, adminName) {
    if (get().useApi) {
      try {
        await barriersApi.open(deviceId, reason)
      } catch {}
    }
    const entry = { id: Date.now(), lane: deviceId, reason, admin_name: adminName, executed_at: new Date() }
    set(s => ({ barrierLogs: [entry, ...s.barrierLogs] }))
  },
}))
