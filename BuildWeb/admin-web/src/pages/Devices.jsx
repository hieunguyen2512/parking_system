import { useState } from 'react'
import { useStore } from '../store/useStore'
import {
  Monitor, Cpu, Camera, Shield, Radio, Lightbulb, Volume2,
  Wifi, WifiOff, AlertCircle, CheckCircle2, RefreshCw, X
} from 'lucide-react'
import clsx from 'clsx'

const DeviceIcons = {
  computer:     Monitor,
  arduino:      Cpu,
  camera_face:  Camera,
  camera_plate: Camera,
  barrier:      Shield,
  sensor:       Radio,
  led:          Lightbulb,
  speaker:      Volume2,
}

const DeviceTypeLabel = {
  computer:'Máy tính Central AI', arduino:'Arduino USB Serial',
  camera_face:'Camera Khuôn Mặt', camera_plate:'Camera Biển Số',
  barrier:'Barrier (Thanh chắn)', sensor:'Cảm biến xe',
  led:'Đèn LED trợ sáng', speaker:'Loa thông báo',
}

const LaneLabel = { entry:'Cổng Vào', exit:'Cổng Ra', both:'Cả hai' }

const fmtAgo = (d) => {
  if (!d) return '—'
  const diff = Math.floor((Date.now() - new Date(d).getTime()) / 1000)
  if (diff < 60)   return `${diff} giây trước`
  if (diff < 3600) return `${Math.floor(diff/60)} phút trước`
  return `${Math.floor(diff/3600)} giờ trước`
}

const statusCfg = {
  online:      { label:'Online',    color:'text-emerald-600', bg:'bg-emerald-100', dot:'bg-emerald-500', Icon: CheckCircle2 },
  offline:     { label:'Offline',   color:'text-gray-500',    bg:'bg-gray-100',    dot:'bg-gray-400',    Icon: WifiOff      },
  error:       { label:'Lỗi',       color:'text-rose-600',    bg:'bg-rose-100',    dot:'bg-rose-500',    Icon: AlertCircle  },
  maintenance: { label:'Bảo trì',   color:'text-amber-600',   bg:'bg-amber-100',   dot:'bg-amber-500',   Icon: AlertCircle  },
}

export default function Devices() {
  const { devices, updateDeviceStatus } = useStore()
  const [selected, setSelected] = useState(null)
  const [restarting, setRestarting] = useState(null)

  const online  = devices.filter(d => d.status === 'online').length
  const offline = devices.filter(d => d.status === 'offline').length
  const error   = devices.filter(d => d.status === 'error').length

  const handleRestart = async (device_id) => {
    setRestarting(device_id)
    await new Promise(r => setTimeout(r, 1500))
    updateDeviceStatus(device_id, 'online')
    setRestarting(null)
  }

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-4">
          <CheckCircle2 size={24} className="text-emerald-600 shrink-0" />
          <div>
            <div className="text-2xl font-bold text-emerald-700">{online}</div>
            <div className="text-xs text-emerald-600 font-medium">Đang hoạt động</div>
          </div>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 flex items-center gap-4">
          <WifiOff size={24} className="text-gray-500 shrink-0" />
          <div>
            <div className="text-2xl font-bold text-gray-700">{offline}</div>
            <div className="text-xs text-gray-500 font-medium">Mất kết nối</div>
          </div>
        </div>
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center gap-4">
          <AlertCircle size={24} className="text-rose-600 shrink-0" />
          <div>
            <div className="text-2xl font-bold text-rose-700">{error}</div>
            <div className="text-xs text-rose-600 font-medium">Có lỗi</div>
          </div>
        </div>
      </div>

      {/* Device Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {devices.map(d => {
          const cfg = statusCfg[d.status] ?? statusCfg.offline
          const Icon = DeviceIcons[d.device_type] ?? Cpu
          const isRestarting = restarting === d.device_id

          return (
            <div
              key={d.device_id}
              className={clsx(
                'bg-white rounded-xl border shadow-sm p-5 cursor-pointer hover:shadow-md transition-shadow',
                d.status === 'error'   ? 'border-rose-200'
                : d.status === 'offline' ? 'border-gray-200'
                : 'border-gray-100'
              )}
              onClick={() => setSelected(d)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${cfg.bg}`}>
                  <Icon size={22} className={cfg.color} />
                </div>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.color}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} ${d.status === 'online' ? 'live-dot' : ''}`} />
                  {isRestarting ? 'Đang kết nối...' : cfg.label}
                </div>
              </div>

              <div className="space-y-1">
                <div className="font-semibold text-gray-800 text-sm">{d.device_name}</div>
                <div className="text-xs text-gray-500">{DeviceTypeLabel[d.device_type]}</div>
              </div>

              <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
                <div className="text-xs text-gray-400">
                  {d.serial_port
                    ? <span className="font-mono">USB: {d.serial_port}</span>
                    : d.ip_address
                    ? <span className="font-mono">IP: {d.ip_address}</span>
                    : <span>—</span>
                  }
                </div>
                <div className="text-xs text-gray-400">{fmtAgo(d.last_heartbeat)}</div>
              </div>

              {(d.status === 'error' || d.status === 'offline') && (
                <button
                  onClick={e => { e.stopPropagation(); handleRestart(d.device_id) }}
                  disabled={isRestarting}
                  className="mt-3 w-full flex items-center justify-center gap-2 text-xs font-medium px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors disabled:opacity-60"
                >
                  <RefreshCw size={13} className={isRestarting ? 'animate-spin' : ''} />
                  {isRestarting ? 'Đang kết nối lại...' : 'Kết nối lại'}
                </button>
              )}

              {d.lane && (
                <div className="mt-2 text-xs">
                  <span className="bg-slate-100 text-slate-600 rounded px-1.5 py-0.5 font-medium">
                    {LaneLabel[d.lane]}
                  </span>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-center gap-4 px-6 py-5 border-b border-gray-100">
              {(() => {
                const cfg = statusCfg[selected.status] ?? statusCfg.offline
                const Icon = DeviceIcons[selected.device_type] ?? Cpu
                return (
                  <>
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${cfg.bg}`}>
                      <Icon size={22} className={cfg.color} />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-800">{selected.device_name}</h3>
                      <p className="text-sm text-gray-500">{DeviceTypeLabel[selected.device_type]}</p>
                    </div>
                    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.color}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                      {cfg.label}
                    </div>
                    <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600">
                      <X size={20} />
                    </button>
                  </>
                )
              })()}
            </div>
            <div className="px-6 py-5 grid grid-cols-2 gap-3">
              <DevRow label="Loại thiết bị"  value={DeviceTypeLabel[selected.device_type]} />
              <DevRow label="Làn"             value={LaneLabel[selected.lane] ?? '—'} />
              <DevRow label="Cổng Serial"     value={<span className="font-mono">{selected.serial_port ?? '—'}</span>} />
              <DevRow label="Địa chỉ IP"      value={<span className="font-mono">{selected.ip_address ?? '—'}</span>} />
              <DevRow label="Heartbeat cuối"  value={fmtAgo(selected.last_heartbeat)} />
              <DevRow label="Kết nối"
                value={selected.serial_port
                  ? <span className="text-blue-600 font-medium">USB Serial</span>
                  : selected.ip_address
                  ? <span className="text-purple-600 font-medium">Ethernet/WiFi</span>
                  : <span className="text-gray-400">GPIO/Relay</span>
                }
              />
            </div>
            {selected.device_type === 'arduino' && (
              <div className="mx-6 mb-5 bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
                Arduino kết nối trực tiếp với máy tính qua <strong>USB Serial ({selected.serial_port})</strong>.
                Giao tiếp 2 chiều: máy tính gửi lệnh <code>OPEN_BARRIER / LED_ON / PLAY_SOUND</code>,
                Arduino gửi lại sự kiện <code>SENSOR_TRIGGERED / VEHICLE_PASSED</code>.
              </div>
            )}
            <div className="px-6 py-4 border-t border-gray-100 flex gap-3 justify-end">
              {(selected.status === 'error' || selected.status === 'offline') && (
                <button
                  onClick={() => { handleRestart(selected.device_id); setSelected(null) }}
                  className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2"
                >
                  <RefreshCw size={14} /> Kết nối lại
                </button>
              )}
              <button onClick={() => setSelected(null)}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function DevRow({ label, value }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-sm font-medium text-gray-800">{value}</div>
    </div>
  )
}
