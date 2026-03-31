import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store/useStore'
import { mockDailyReports, mockHourlyTraffic } from '../data/mockData'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  ParkingSquare, Car, CheckCircle, BanknoteIcon,
  Cpu, AlertTriangle, ChevronRight, DoorOpen, DoorClosed,
} from 'lucide-react'
import clsx from 'clsx'

const fmtVND = n => n?.toLocaleString('vi-VN') + 'đ'
const fmtDuration = (entry) => {
  const diff = Math.floor((Date.now() - new Date(entry).getTime()) / 60000)
  if (diff < 60) return `${diff} phút`
  const h = Math.floor(diff / 60), m = diff % 60
  return `${h}g ${m}p`
}

const DeviceTypeLookup = {
  computer:'Máy tính', arduino:'Arduino', camera_face:'Camera Mặt',
  camera_plate:'Camera Biển', barrier:'Barrier', sensor:'Cảm biến',
  led:'Đèn LED', speaker:'Loa',
}

export default function Dashboard() {
  const { lot, devices, activeSessions, alerts, openBarrierManual, currentAdmin } = useStore()
  const navigate = useNavigate()
  const [showBarrierModal, setShowBarrierModal] = useState(false)
  const [barrierForm, setBarrierForm] = useState({ lane: 'entry', reason: '' })
  const [tick, setTick] = useState(0)

  // refresh durations every 30s
  useEffect(() => {
    const t = setInterval(() => setTick(v => v + 1), 30000)
    return () => clearInterval(t)
  }, [])

  const onlineCount  = devices.filter(d => d.status === 'online').length
  const offlineCount = devices.filter(d => d.status !== 'online').length
  const unresolved   = alerts.filter(a => !a.is_resolved).length
  const todayRevenue = mockDailyReports.at(-1)?.total_revenue ?? 0
  const todaySessions= mockDailyReports.at(-1)?.total_sessions ?? 0
  const occupancyPct = Math.round(lot.current_occupancy * 100 / lot.total_capacity)

  const handleBarrierOpen = () => {
    if (!barrierForm.reason) return
    openBarrierManual(barrierForm.lane, barrierForm.reason, currentAdmin.full_name)
    setShowBarrierModal(false)
    setBarrierForm({ lane: 'entry', reason: '' })
  }

  return (
    <div className="space-y-6">
      {/* ── Stat cards ──────────────────────────────────── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          icon={<ParkingSquare size={22} />}
          iconBg="bg-blue-100 text-blue-600"
          label="Tổng sức chứa"
          value={lot.total_capacity}
          sub="chỗ đỗ"
        />
        <StatCard
          icon={<Car size={22} />}
          iconBg="bg-amber-100 text-amber-600"
          label="Đang đỗ"
          value={lot.current_occupancy}
          sub={`${occupancyPct}% lấp đầy`}
          valueClass="text-amber-600"
        />
        <StatCard
          icon={<CheckCircle size={22} />}
          iconBg="bg-emerald-100 text-emerald-600"
          label="Còn trống"
          value={lot.total_capacity - lot.current_occupancy}
          sub="chỗ có sẵn"
          valueClass="text-emerald-600"
        />
        <StatCard
          icon={<BanknoteIcon size={22} />}
          iconBg="bg-purple-100 text-purple-600"
          label="Doanh thu hôm nay"
          value={fmtVND(todayRevenue)}
          sub={`${todaySessions} lần gửi`}
          valueClass="text-purple-700 text-xl"
        />
      </div>

      {/* ── Occupancy bar + Quick controls ──────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-semibold text-gray-800">{lot.name}</h2>
              <p className="text-xs text-gray-500 mt-0.5">{lot.address}</p>
            </div>
            <span className={clsx(
              'text-xs font-semibold px-2.5 py-1 rounded-full',
              occupancyPct >= 90 ? 'bg-rose-100 text-rose-700'
              : occupancyPct >= 70 ? 'bg-amber-100 text-amber-700'
              : 'bg-emerald-100 text-emerald-700'
            )}>
              {occupancyPct}% đầy
            </span>
          </div>
          <div className="flex items-center gap-4 mb-2">
            <span className="text-3xl font-bold text-gray-900">{lot.current_occupancy}</span>
            <span className="text-gray-400">/</span>
            <span className="text-2xl text-gray-500">{lot.total_capacity}</span>
            <span className="text-sm text-gray-500">xe đang đỗ</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
            <div
              className={clsx(
                'h-3 rounded-full transition-all duration-700',
                occupancyPct >= 90 ? 'bg-rose-500'
                : occupancyPct >= 70 ? 'bg-amber-500'
                : 'bg-emerald-500'
              )}
              style={{ width: `${occupancyPct}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0</span>
            <span>{lot.total_capacity}</span>
          </div>
        </div>

        {/* Quick controls */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="font-semibold text-gray-800 mb-4">Điều khiển nhanh</h2>
          <div className="space-y-3">
            <button
              onClick={() => { setBarrierForm(f => ({ ...f, lane: 'entry' })); setShowBarrierModal(true) }}
              className="w-full flex items-center gap-3 px-4 py-3 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-sm font-medium transition-colors"
            >
              <DoorOpen size={18} />
              Mở barrier cổng VÀO (thủ công)
            </button>
            <button
              onClick={() => { setBarrierForm(f => ({ ...f, lane: 'exit' })); setShowBarrierModal(true) }}
              className="w-full flex items-center gap-3 px-4 py-3 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-lg text-sm font-medium transition-colors"
            >
              <DoorOpen size={18} />
              Mở barrier cổng RA (thủ công)
            </button>
            <button
              onClick={() => navigate('/devices')}
              className="w-full flex items-center gap-3 px-4 py-3 bg-gray-50 hover:bg-gray-100 text-gray-700 rounded-lg text-sm font-medium transition-colors"
            >
              <Cpu size={18} />
              Xem trạng thái thiết bị
              <ChevronRight size={16} className="ml-auto" />
            </button>
          </div>
          {offlineCount > 0 && (
            <div className="mt-3 flex items-center gap-2 text-xs text-rose-600 bg-rose-50 rounded-lg px-3 py-2">
              <AlertTriangle size={13} />
              {offlineCount} thiết bị không online
            </div>
          )}
        </div>
      </div>

      {/* ── Active sessions + Device status ─────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Active sessions */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-gray-800">Xe đang trong bãi</h2>
              <span className="bg-amber-100 text-amber-700 text-xs font-semibold px-2 py-0.5 rounded-full">
                {activeSessions.length}
              </span>
            </div>
            <button onClick={() => navigate('/sessions')} className="text-xs text-blue-600 hover:underline">
              Xem tất cả →
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase font-medium">
                <tr>
                  <th className="px-5 py-3 text-left">Biển số</th>
                  <th className="px-5 py-3 text-left">Chủ xe</th>
                  <th className="px-5 py-3 text-left">Thời gian vào</th>
                  <th className="px-5 py-3 text-left">Đã gửi</th>
                  <th className="px-5 py-3 text-left">Loại</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {activeSessions.slice(0, 6).map(s => (
                  <tr key={s.session_id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-mono font-semibold text-gray-800">{s.license_plate}</td>
                    <td className="px-5 py-3 text-gray-700">{s.user_name ?? <span className="text-gray-400 italic">Khách vãng lai</span>}</td>
                    <td className="px-5 py-3 text-gray-600">
                      {new Date(s.entry_time).toLocaleTimeString('vi-VN', { hour:'2-digit', minute:'2-digit' })}
                    </td>
                    <td className="px-5 py-3 text-gray-600">{fmtDuration(s.entry_time)}</td>
                    <td className="px-5 py-3">
                      <SessionTypeBadge type={s.session_type} code={s.session_code} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Device status */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-800">Thiết bị</h2>
            <div className="flex gap-3 text-xs">
              <span className="text-emerald-600 font-medium">{onlineCount} online</span>
              <span className="text-rose-600 font-medium">{offlineCount} lỗi</span>
            </div>
          </div>
          <div className="divide-y divide-gray-100 max-h-64 overflow-y-auto">
            {devices.map(d => (
              <div key={d.device_id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50">
                <span className={clsx(
                  'w-2 h-2 rounded-full shrink-0',
                  d.status === 'online' ? 'bg-emerald-500'
                  : d.status === 'offline' ? 'bg-gray-400'
                  : 'bg-rose-500'
                )} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-gray-800 truncate">{d.device_name}</div>
                  <div className="text-xs text-gray-400">{DeviceTypeLookup[d.device_type]}</div>
                </div>
                <span className={clsx(
                  'text-xs font-medium',
                  d.status === 'online' ? 'text-emerald-600'
                  : d.status === 'offline' ? 'text-gray-500'
                  : 'text-rose-600'
                )}>
                  {d.status === 'online' ? 'OK' : d.status === 'offline' ? 'Offline' : 'Lỗi'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Charts ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="font-semibold text-gray-800 mb-4">Doanh thu 7 ngày gần nhất</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={mockDailyReports} margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={v => (v/1000) + 'k'} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [fmtVND(v), 'Doanh thu']} />
              <Bar dataKey="total_revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="font-semibold text-gray-800 mb-4">Lưu lượng theo giờ – Hôm nay</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={mockHourlyTraffic} margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={2} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [v + ' xe', 'Lượt vào']} />
              <Line type="monotone" dataKey="count" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Recent Alerts ───────────────────────────────── */}
      {unresolved > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-500" />
              <h2 className="font-semibold text-gray-800">Cảnh báo chưa xử lý</h2>
              <span className="bg-rose-100 text-rose-700 text-xs font-semibold px-2 py-0.5 rounded-full">{unresolved}</span>
            </div>
            <button onClick={() => navigate('/alerts')} className="text-xs text-blue-600 hover:underline">Xử lý ngay →</button>
          </div>
          <div className="divide-y divide-gray-100">
            {alerts.filter(a => !a.is_resolved).map(a => (
              <div key={a.alert_id} className="flex items-start gap-4 px-5 py-3 hover:bg-gray-50">
                <span className={clsx(
                  'mt-0.5 shrink-0 text-xs font-bold px-2 py-0.5 rounded',
                  a.severity === 'critical' ? 'bg-rose-100 text-rose-700'
                  : a.severity === 'warning' ? 'bg-amber-100 text-amber-700'
                  : 'bg-blue-100 text-blue-700'
                )}>
                  {a.severity === 'critical' ? 'NGHIÊM TRỌNG' : a.severity === 'warning' ? 'CẢNH BÁO' : 'THÔNG TIN'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800">{a.title}</div>
                  <div className="text-xs text-gray-500 mt-0.5 truncate">{a.description}</div>
                </div>
                <div className="text-xs text-gray-400 shrink-0">
                  {new Date(a.created_at).toLocaleTimeString('vi-VN', { hour:'2-digit', minute:'2-digit' })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Barrier Modal ────────────────────────────────── */}
      {showBarrierModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="px-6 py-5 border-b border-gray-100">
              <h3 className="font-semibold text-gray-800">Mở barrier thủ công – {barrierForm.lane === 'entry' ? 'Cổng Vào' : 'Cổng Ra'}</h3>
              <p className="text-xs text-gray-500 mt-1">Hành động này sẽ được ghi log đầy đủ.</p>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Làn đường</label>
                <select
                  value={barrierForm.lane}
                  onChange={e => setBarrierForm(f => ({ ...f, lane: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="entry">Cổng Vào</option>
                  <option value="exit">Cổng Ra</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Lý do mở thủ công <span className="text-rose-500">*</span>
                </label>
                <textarea
                  value={barrierForm.reason}
                  onChange={e => setBarrierForm(f => ({ ...f, reason: e.target.value }))}
                  rows={3}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  placeholder="VD: Xe bị kẹt barrier, xe khẩn cấp, kiểm tra kỹ thuật..."
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-100 flex gap-3 justify-end">
              <button
                onClick={() => setShowBarrierModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Hủy
              </button>
              <button
                onClick={handleBarrierOpen}
                disabled={!barrierForm.reason.trim()}
                className="px-4 py-2 text-sm font-semibold bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors"
              >
                Xác nhận mở Barrier
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon, iconBg, label, value, sub, valueClass }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}>
        {icon}
      </div>
      <div>
        <div className="text-xs text-gray-500 font-medium">{label}</div>
        <div className={`text-2xl font-bold text-gray-900 mt-0.5 ${valueClass ?? ''}`}>{value}</div>
        <div className="text-xs text-gray-400 mt-0.5">{sub}</div>
      </div>
    </div>
  )
}

function SessionTypeBadge({ type, code }) {
  if (type === 'guest') return (
    <span className="inline-flex items-center gap-1 bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded-full font-medium">
      Vãng lai {code && <span className="font-mono">{code}</span>}
    </span>
  )
  if (type === 'authorized') return (
    <span className="bg-purple-100 text-purple-700 text-xs px-2 py-0.5 rounded-full font-medium">Ủy quyền</span>
  )
  return <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full font-medium">Thành viên</span>
}
