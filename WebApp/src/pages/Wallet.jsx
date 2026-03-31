import { useEffect, useState } from 'react';
import { useStore } from '../store/useStore';
import { Wallet, ArrowDownLeft, ArrowUpRight, RefreshCw, Plus, X } from 'lucide-react';

function fmtCurrency(n) {
  if (n == null) return '—';
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(n);
}

function fmtDateTime(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

const GATEWAYS = [
  { value: 'momo',          label: 'MoMo' },
  { value: 'vnpay',         label: 'VNPay' },
  { value: 'zalopay',       label: 'ZaloPay' },
  { value: 'bank_transfer', label: 'Chuyển khoản' },
];

const QUICK_AMOUNTS = [50000, 100000, 200000, 500000];

function TxIcon({ type }) {
  if (type === 'topup')  return <div className="w-9 h-9 bg-green-100 rounded-full flex items-center justify-center"><ArrowDownLeft size={18} className="text-green-600" /></div>;
  if (type === 'deduct') return <div className="w-9 h-9 bg-red-100 rounded-full flex items-center justify-center"><ArrowUpRight size={18} className="text-red-500" /></div>;
  if (type === 'refund') return <div className="w-9 h-9 bg-blue-100 rounded-full flex items-center justify-center"><RefreshCw size={18} className="text-blue-600" /></div>;
  return <div className="w-9 h-9 bg-slate-100 rounded-full flex items-center justify-center"><ArrowUpRight size={18} className="text-slate-500" /></div>;
}

const TX_LABEL = {
  topup: 'Nạp tiền', deduct: 'Phí gửi xe', withdraw: 'Rút tiền', refund: 'Hoàn tiền',
};

export default function WalletPage() {
  const { wallet, walletTransactions, walletTotal, walletPage, fetchWallet, fetchTransactions, topup } = useStore();
  const [showTopup, setShowTopup] = useState(false);
  const [amount, setAmount] = useState('');
  const [gateway, setGateway] = useState('momo');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchWallet();
    fetchTransactions(1);
  }, []);

  async function handleTopup(e) {
    e.preventDefault();
    setError(''); setSuccess('');
    const num = parseInt(amount.replace(/\D/g, ''), 10);
    setLoading(true);
    try {
      const data = await topup(num, gateway);
      setSuccess(`Nạp thành công ${fmtCurrency(num)}! Số dư mới: ${fmtCurrency(data.new_balance)}`);
      setAmount('');
      setShowTopup(false);
      fetchTransactions(1);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  const totalPages = Math.ceil(walletTotal / 20);

  return (
    <div className="p-4 space-y-4">
      {/* Số dư */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl p-5 text-white">
        <p className="text-blue-200 text-sm">Số dư hiện tại</p>
        <p className="text-3xl font-bold mt-1">{fmtCurrency(wallet?.balance)}</p>
        <button
          onClick={() => { setShowTopup(v => !v); setError(''); setSuccess(''); }}
          className="mt-4 flex items-center gap-1.5 bg-white text-blue-600 font-semibold text-sm px-4 py-2 rounded-xl hover:bg-blue-50"
        >
          <Plus size={16} /> Nạp tiền
        </button>
      </div>

      {/* Thông báo */}
      {success && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">{success}</div>
      )}

      {/* Form nạp tiền */}
      {showTopup && (
        <form onSubmit={handleTopup} className="card border-2 border-blue-200 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-800">Nạp tiền vào ví</h3>
            <button type="button" onClick={() => setShowTopup(false)}><X size={18} className="text-slate-400" /></button>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}

          {/* Số tiền nhanh */}
          <div>
            <p className="text-sm text-slate-500 mb-2">Chọn nhanh</p>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_AMOUNTS.map(a => (
                <button
                  type="button" key={a}
                  onClick={() => setAmount(a.toString())}
                  className={`py-2 rounded-xl text-sm font-medium border transition-colors
                    ${amount === a.toString()
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'}`}
                >
                  {fmtCurrency(a)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Hoặc nhập số tiền (VND)</label>
            <input
              type="number"
              className="input-field"
              placeholder="100000"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              min={10000}
              max={10000000}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Phương thức thanh toán</label>
            <div className="grid grid-cols-2 gap-2">
              {GATEWAYS.map(g => (
                <button
                  type="button" key={g.value}
                  onClick={() => setGateway(g.value)}
                  className={`py-2 rounded-xl text-sm font-medium border transition-colors
                    ${gateway === g.value
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'}`}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          <button type="submit" disabled={loading || !amount} className="btn-primary">
            {loading ? 'Đang xử lý...' : `Nạp ${amount ? fmtCurrency(parseInt(amount, 10)) : ''}`}
          </button>
        </form>
      )}

      {/* Lịch sử giao dịch */}
      <div>
        <p className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Lịch sử giao dịch ({walletTotal})
        </p>

        {walletTransactions.length === 0 ? (
          <div className="text-center py-10 text-slate-400 text-sm">Chưa có giao dịch nào</div>
        ) : (
          <div className="space-y-2">
            {walletTransactions.map(t => (
              <div key={t.id} className="card flex items-center gap-3">
                <TxIcon type={t.transaction_type} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800">
                    {TX_LABEL[t.transaction_type] || t.transaction_type}
                  </p>
                  {t.session_plate && (
                    <p className="text-xs text-slate-400">{t.session_plate}</p>
                  )}
                  <p className="text-xs text-slate-300">{fmtDateTime(t.created_at)}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className={`font-semibold text-sm
                    ${t.transaction_type === 'topup' || t.transaction_type === 'refund'
                      ? 'text-green-600' : 'text-red-500'}`}>
                    {t.transaction_type === 'topup' || t.transaction_type === 'refund' ? '+' : '-'}
                    {fmtCurrency(t.amount)}
                  </p>
                  <p className="text-xs text-slate-400">{fmtCurrency(t.balance_after)}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Phân trang */}
        {totalPages > 1 && (
          <div className="flex justify-center gap-2 mt-4">
            <button disabled={walletPage <= 1} onClick={() => fetchTransactions(walletPage - 1)}
              className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40">Trước</button>
            <span className="px-3 py-1.5 text-sm text-slate-500">{walletPage} / {totalPages}</span>
            <button disabled={walletPage >= totalPages} onClick={() => fetchTransactions(walletPage + 1)}
              className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg disabled:opacity-40">Tiếp</button>
          </div>
        )}
      </div>
    </div>
  );
}
