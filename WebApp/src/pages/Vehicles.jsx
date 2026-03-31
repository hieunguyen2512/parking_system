import { useEffect, useState } from 'react';
import { useStore } from '../store/useStore';
import { Car, Plus, Pencil, Trash2, X, Check } from 'lucide-react';

export default function Vehicles() {
  const { vehicles, fetchVehicles, addVehicle, updateVehicle, removeVehicle } = useStore();
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({ license_plate: '', nickname: '' });
  const [editNickname, setEditNickname] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { fetchVehicles(); }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await addVehicle(form);
      setForm({ license_plate: '', nickname: '' });
      setShowAdd(false);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  async function handleUpdate(id) {
    setLoading(true);
    try {
      await updateVehicle(id, { nickname: editNickname });
      setEditId(null);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  async function handleRemove(id, plate) {
    if (!confirm(`Xóa xe ${plate} khỏi danh sách?`)) return;
    try { await removeVehicle(id); }
    catch (err) { alert(err.message); }
  }

  const activeVehicles = vehicles.filter(v => v.is_active);

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{activeVehicles.length} xe đã đăng ký</p>
        <button
          onClick={() => { setShowAdd(v => !v); setError(''); }}
          className="flex items-center gap-1 bg-blue-600 text-white text-sm font-medium px-3 py-2 rounded-xl hover:bg-blue-700"
        >
          <Plus size={16} /> Thêm xe
        </button>
      </div>

      {/* Form thêm xe */}
      {showAdd && (
        <form onSubmit={handleAdd} className="card space-y-3 border-blue-200 border-2">
          <h3 className="font-semibold text-slate-800">Thêm xe mới</h3>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Biển số xe *</label>
            <input
              className="input-field uppercase"
              placeholder="Ví dụ: 51F-12345"
              value={form.license_plate}
              onChange={e => setForm(f => ({ ...f, license_plate: e.target.value }))}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Tên gợi nhớ</label>
            <input
              className="input-field"
              placeholder="Ví dụ: Xe đi làm"
              value={form.nickname}
              onChange={e => setForm(f => ({ ...f, nickname: e.target.value }))}
            />
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={loading} className="btn-primary py-2">
              {loading ? 'Đang lưu...' : 'Lưu'}
            </button>
            <button type="button" onClick={() => setShowAdd(false)} className="btn-secondary py-2">
              Hủy
            </button>
          </div>
        </form>
      )}

      {/* Danh sách xe */}
      {activeVehicles.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Car size={40} className="mx-auto mb-3 opacity-30" />
          <p>Bạn chưa đăng ký xe nào</p>
          <p className="text-sm mt-1">Nhấn "Thêm xe" để bắt đầu</p>
        </div>
      ) : (
        <div className="space-y-3">
          {activeVehicles.map(v => (
            <div key={v.id} className="card">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0">
                  <Car size={20} className="text-blue-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-slate-800">{v.license_plate}</p>
                  {editId === v.id ? (
                    <div className="flex items-center gap-1 mt-1">
                      <input
                        className="input-field py-1 text-sm"
                        value={editNickname}
                        onChange={e => setEditNickname(e.target.value)}
                        placeholder="Tên gợi nhớ"
                        autoFocus
                      />
                      <button onClick={() => handleUpdate(v.id)} className="p-1 text-green-600 hover:bg-green-50 rounded">
                        <Check size={16} />
                      </button>
                      <button onClick={() => setEditId(null)} className="p-1 text-slate-400 hover:bg-slate-50 rounded">
                        <X size={16} />
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">{v.nickname || 'Chưa đặt tên'}</p>
                  )}
                </div>
                {editId !== v.id && (
                  <div className="flex gap-1 flex-shrink-0">
                    <button
                      onClick={() => { setEditId(v.id); setEditNickname(v.nickname || ''); }}
                      className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => handleRemove(v.id, v.license_plate)}
                      className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
