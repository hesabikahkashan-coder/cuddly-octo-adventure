/**
 * Main Dashboard Page
 * Real-time overview of portfolio, positions, risk status, and market data.
 */
import React, { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, IChartApi } from 'lightweight-charts'
import { useTradingStore, useUIStore } from '../store'
import { TrendingUp, TrendingDown, Shield, AlertTriangle, Activity, DollarSign } from 'lucide-react'
import clsx from 'clsx'

// ─── Stat Card ────────────────────────────────────────────

interface StatCardProps {
  title: string
  value: string
  change?: number
  icon: React.ReactNode
  color?: 'green' | 'red' | 'blue' | 'yellow'
}

const StatCard: React.FC<StatCardProps> = ({ title, value, change, icon, color = 'blue' }) => {
  const colorMap = {
    green: 'bg-green-500/10 border-green-500/20 text-green-400',
    red: 'bg-red-500/10 border-red-500/20 text-red-400',
    blue: 'bg-blue-500/10 border-blue-500/20 text-blue-400',
    yellow: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400',
  }
  return (
    <div className={clsx('rounded-xl border p-4', colorMap[color])}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm opacity-70">{title}</span>
        {icon}
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {change !== undefined && (
        <div className={clsx('text-sm mt-1', change >= 0 ? 'text-green-400' : 'text-red-400')}>
          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
        </div>
      )}
    </div>
  )
}

// ─── Risk Gauge ───────────────────────────────────────────

const RiskGauge: React.FC<{ drawdown: number; maxDrawdown: number; halted: boolean }> = ({
  drawdown, maxDrawdown, halted
}) => {
  const percent = Math.min((drawdown / maxDrawdown) * 100, 100)
  const color = percent > 80 ? 'bg-red-500' : percent > 50 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-400">Daily Risk Usage</span>
        {halted && <span className="text-xs bg-red-500 text-white px-2 py-1 rounded">HALTED</span>}
      </div>
      <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${percent}%` }} />
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{drawdown.toFixed(2)}% used</span>
        <span>{maxDrawdown}% max</span>
      </div>
    </div>
  )
}

// ─── Positions Table ──────────────────────────────────────

const PositionsTable: React.FC = () => {
  const { positions } = useTradingStore()

  if (positions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 text-center text-gray-400">
        No open positions
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-900">
          <tr>
            {['Symbol', 'Direction', 'Entry', 'Current', 'PnL', 'Stop Loss'].map(h => (
              <th key={h} className="px-4 py-3 text-left text-gray-400 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => (
            <tr key={pos.id} className="border-t border-gray-700 hover:bg-gray-750">
              <td className="px-4 py-3 font-mono text-white">{pos.symbol}</td>
              <td className="px-4 py-3">
                <span className={clsx(
                  'px-2 py-1 rounded text-xs font-bold',
                  pos.direction === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                )}>
                  {pos.direction.toUpperCase()}
                </span>
              </td>
              <td className="px-4 py-3 font-mono text-gray-300">${pos.entry_price.toLocaleString()}</td>
              <td className="px-4 py-3 font-mono text-gray-300">${pos.current_price.toLocaleString()}</td>
              <td className={clsx('px-4 py-3 font-mono font-bold', pos.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400')}>
                {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl.toFixed(2)}
                <span className="text-xs ml-1">({pos.unrealized_pnl_percent.toFixed(2)}%)</span>
              </td>
              <td className="px-4 py-3 font-mono text-yellow-400">${pos.stop_loss.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Main Dashboard ───────────────────────────────────────

const Dashboard: React.FC = () => {
  const { riskStatus, paperBalance, tradingMode, tickers } = useTradingStore()
  const { theme } = useUIStore()
  const chartRef = useRef<HTMLDivElement>(null)
  const [chart, setChart] = useState<IChartApi | null>(null)

  useEffect(() => {
    if (!chartRef.current) return

    const c = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#1f2937' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      width: chartRef.current.clientWidth,
      height: 300,
      timeScale: { borderColor: '#374151' },
    })

    const candleSeries = c.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    // Placeholder data — will be replaced by WebSocket feed
    const sampleData = Array.from({ length: 50 }, (_, i) => {
      const base = 45000 + Math.random() * 5000
      return {
        time: (Math.floor(Date.now() / 1000) - (50 - i) * 3600) as any,
        open: base,
        high: base + Math.random() * 500,
        low: base - Math.random() * 500,
        close: base + (Math.random() - 0.5) * 400,
      }
    })

    candleSeries.setData(sampleData)
    c.timeScale().fitContent()
    setChart(c)

    const handleResize = () => {
      if (chartRef.current) c.applyOptions({ width: chartRef.current.clientWidth })
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      c.remove()
    }
  }, [])

  const dailyPnl = riskStatus?.daily_pnl ?? 0
  const drawdown = riskStatus?.daily_drawdown_percent ?? 0

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">
            Mode: <span className={clsx('font-bold', tradingMode === 'live' ? 'text-green-400' : 'text-blue-400')}>
              {tradingMode.toUpperCase()}
            </span>
          </p>
        </div>
        {riskStatus?.trading_halted && (
          <div className="flex items-center gap-2 bg-red-500/20 border border-red-500/50 rounded-lg px-4 py-2">
            <AlertTriangle className="text-red-400" size={16} />
            <span className="text-red-400 font-bold">TRADING HALTED</span>
          </div>
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Balance"
          value={`$${paperBalance.toLocaleString('en', { minimumFractionDigits: 2 })}`}
          icon={<DollarSign size={18} />}
          color="blue"
        />
        <StatCard
          title="Daily PnL"
          value={`$${dailyPnl.toFixed(2)}`}
          change={riskStatus?.daily_pnl_percent ?? 0}
          icon={dailyPnl >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
          color={dailyPnl >= 0 ? 'green' : 'red'}
        />
        <StatCard
          title="Open Trades"
          value={String(riskStatus?.open_trades ?? 0)}
          icon={<Activity size={18} />}
          color="yellow"
        />
        <StatCard
          title="Risk Status"
          value={riskStatus?.trading_halted ? 'HALTED' : 'Active'}
          icon={<Shield size={18} />}
          color={riskStatus?.trading_halted ? 'red' : 'green'}
        />
      </div>

      {/* Risk Gauge */}
      <RiskGauge
        drawdown={drawdown}
        maxDrawdown={riskStatus ? 5.0 : 5.0}
        halted={riskStatus?.trading_halted ?? false}
      />

      {/* Chart */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
        <h2 className="text-white font-semibold mb-4">BTC/USDT — Live Chart</h2>
        <div ref={chartRef} />
      </div>

      {/* Positions */}
      <div>
        <h2 className="text-white font-semibold mb-3">Open Positions</h2>
        <PositionsTable />
      </div>
    </div>
  )
}

export default Dashboard
