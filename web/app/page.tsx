'use client';

import { useState } from 'react';
import { Play, Settings2, ShieldCheck, AlertTriangle, CheckCircle2, RefreshCw, Languages, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList
} from 'recharts';
import clsx from 'clsx';
import { runSimulation, SimulationConfig, SimulationResult } from '../lib/engine';

type Mode = 'no_def' | 'rolling' | 'window' | 'challenge';
type Lang = 'zh' | 'ja' | 'en';

const MODE_META = {
  no_def: { color: '#ef4444' },
  rolling: { color: '#8b5cf6' },
  window: { color: '#3b82f6' },
  challenge: { color: '#10b981' },
};

const TRANSLATIONS = {
  zh: {
    app_title: "IoTSim 重放攻击仿真",
    subtitle: "无线重放攻击防御机制评估环境",
    scenario: "场景选择",
    env: "环境设置",
    pkt_loss: "丢包率",
    reorder: "乱序率",
    window: "窗口大小",
    runs: "模拟次数",
    modes: "防御协议",
    run_btn: "开始分析",
    running: "模拟中...",
    dashboard: "实时仪表盘",
    dash_desc: "实时蒙特卡洛模拟性能指标",
    runs_stat: "轮次/协议",
    ready_title: "准备就绪",
    ready_desc: "请选择一个场景或自定义参数，然后点击运行。",
    usability: "可用性评分",
    usability_sub: "合法请求接受率 (越高越好)",
    security: "漏洞风险",
    security_sub: "攻击成功率 (越低越好)",
    table_proto: "协议",
    table_usable: "可用性",
    table_risk: "安全风险",
    table_stab: "稳定性 (标准差)",
    mode_no: "无防御 (No Defense)",
    mode_rolling: "滚动计数器 (Rolling)",
    mode_window: "滑动窗口 (Window)",
    mode_challenge: "挑战应答 (Challenge)",
    desc_no: "无保护基准",
    desc_rolling: "严格序列验证",
    desc_window: "乱序容忍机制",
    desc_challenge: "Nonce 随机数验证"
  },
  ja: {
    app_title: "IoTSim リプレイ攻撃",
    subtitle: "無線リプレイ攻撃防御評価シミュレーター",
    scenario: "シナリオ選択",
    env: "環境設定",
    pkt_loss: "パケット損失率",
    reorder: "パケット乱順率",
    window: "ウィンドウサイズ",
    runs: "試行回数",
    modes: "防御プロトコル",
    run_btn: "分析開始",
    running: "実行中...",
    dashboard: "ダッシュボード",
    dash_desc: "リアルタイム・モンテカルロ・シミュレーション結果",
    runs_stat: "回試行/プロトコル",
    ready_title: "準備完了",
    ready_desc: "シナリオを選択するかパラメータを調整して実行してください。",
    usability: "ユーザビリティ",
    usability_sub: "正規リクエスト受理率 (高いほど良い)",
    security: "セキュリティリスク",
    security_sub: "攻撃成功率 (低いほど良い)",
    table_proto: "プロトコル",
    table_usable: "可用性",
    table_risk: "リスク",
    table_stab: "安定性 (標準偏差)",
    mode_no: "防御なし",
    mode_rolling: "ローリングカウンタ",
    mode_window: "スライディング窓",
    mode_challenge: "チャレンジ応答",
    desc_no: "ベースライン",
    desc_rolling: "厳密な順序検証",
    desc_window: "順序の乱れを許容",
    desc_challenge: "Nonceによる検証"
  },
  en: {
    app_title: "IoTSim Replay",
    subtitle: "Wireless replay attack defense evaluation.",
    scenario: "Select Scenario",
    env: "Environment",
    pkt_loss: "Packet Loss",
    reorder: "Reordering",
    window: "Window Size",
    runs: "Sim Runs",
    modes: "Target Protocols",
    run_btn: "Run Analysis",
    running: "Simulating...",
    dashboard: "Dashboard",
    dash_desc: "Real-time performance metrics",
    runs_stat: "Runs/Protocol",
    ready_title: "Ready to Simulate",
    ready_desc: "Select a scenario or adjust parameters to start.",
    usability: "Usability Score",
    usability_sub: "Legitimate Acceptance Rate (Higher is better)",
    security: "Vulnerability Risk",
    security_sub: "Attack Success Rate (Lower is better)",
    table_proto: "Protocol",
    table_usable: "Usability",
    table_risk: "Security Risk",
    table_stab: "Stability (Std Dev)",
    mode_no: "No Defense",
    mode_rolling: "Rolling Counter",
    mode_window: "Sliding Window",
    mode_challenge: "Challenge-Response",
    desc_no: "No protection baseline",
    desc_rolling: "Strict sequential",
    desc_window: "Reordering tolerance",
    desc_challenge: "Nonce-based auth"
  }
};

type Scenario = {
  id: string;
  name: { zh: string; ja: string; en: string };
  config: Partial<SimulationConfig>;
};

const SCENARIOS: Scenario[] = [
  {
    id: 'custom',
    name: { zh: '自定义设置 (Custom)', ja: 'カスタム設定', en: 'Custom Settings' },
    config: {}
  },
  {
    id: 'ideal',
    name: { zh: '理想信道 (基准)', ja: '理想的な通信 (基準)', en: 'Ideal Channel (Baseline)' },
    config: { p_loss: 0.0, p_reorder: 0.0, attack_mode: 'post' }
  },
  {
    id: 'office',
    name: { zh: '典型办公环境 (Wi-Fi干扰)', ja: 'オフィス環境 (Wi-Fi干渉)', en: 'Office (Wi-Fi Interference)' },
    config: { p_loss: 0.1, p_reorder: 0.05, attack_mode: 'post' }
  },
  {
    id: 'industrial',
    name: { zh: '恶劣工业环境 (强电磁干扰)', ja: '産業環境 (強い電磁干渉)', en: 'Industrial (High Interference)' },
    config: { p_loss: 0.25, p_reorder: 0.1, attack_mode: 'post' }
  },
  {
    id: 'multihop',
    name: { zh: '多跳传感器网络 (高乱序)', ja: 'マルチホップNW (高乱順)', en: 'Multi-hop Network (High Reordering)' },
    config: { p_loss: 0.1, p_reorder: 0.25, attack_mode: 'post' }
  },
  {
    id: 'attack_heavy',
    name: { zh: '高强度实时攻击 (Inline)', ja: '高強度リアルタイム攻撃', en: 'Active Inline Attack' },
    config: { p_loss: 0.1, p_reorder: 0.1, attack_mode: 'inline' }
  }
];

export default function SimulatorPage() {
  const [lang, setLang] = useState<Lang>('en');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SimulationResult[] | null>(null);
  const [activeScenario, setActiveScenario] = useState<string>('custom');

  const t = TRANSLATIONS[lang];

  const [config, setConfig] = useState<SimulationConfig>({
    modes: ['no_def', 'rolling', 'window', 'challenge'],
    runs: 50,
    p_loss: 0.1,
    p_reorder: 0.0,
    window_size: 5,
    num_legit: 20,
    num_replay: 50,
    attack_mode: 'post'
  });

  // Helper to get translated label
  const getModeLabel = (mode: Mode) => {
    switch (mode) {
      case 'no_def': return t.mode_no;
      case 'rolling': return t.mode_rolling;
      case 'window': return t.mode_window;
      case 'challenge': return t.mode_challenge;
      default: return mode;
    }
  };

  const getModeDesc = (mode: Mode) => {
    switch (mode) {
      case 'no_def': return t.desc_no;
      case 'rolling': return t.desc_rolling;
      case 'window': return t.desc_window;
      case 'challenge': return t.desc_challenge;
      default: return '';
    }
  };

  const handleRun = async () => {
    setLoading(true);
    try {
      // Artificial delay for UX
      await new Promise(resolve => setTimeout(resolve, 600));

      const res = await runSimulation(config);
      setResults(res);
    } catch (err) {
      console.error(err);
      alert('Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const updateConfig = (key: keyof SimulationConfig, value: any) => {
    setConfig(prev => ({ ...prev, [key]: value }));
    if (key === 'p_loss' || key === 'p_reorder' || key === 'attack_mode') {
      setActiveScenario('custom');
    }
  };

  const applyScenario = (scenarioId: string) => {
    setActiveScenario(scenarioId);
    const scenario = SCENARIOS.find(s => s.id === scenarioId);
    if (scenario && scenarioId !== 'custom') {
      setConfig(prev => ({
        ...prev,
        ...scenario.config
      }));
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col lg:flex-row overflow-hidden">
      {/* Sidebar Controls */}
      <aside className="w-full lg:w-96 bg-white border-r border-slate-200 p-6 flex-shrink-0 shadow-lg z-20 flex flex-col h-screen overflow-y-auto">
        <div className="mb-6">
          <div className="flex justify-between items-start mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-600 rounded-lg text-white shadow-md shadow-indigo-500/30">
                <ShieldCheck size={24} />
              </div>
              <div>
                <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">{t.app_title}</h1>
                <span className="text-xs font-semibold text-indigo-600 uppercase tracking-widest bg-indigo-50 px-2 py-0.5 rounded-full">Pro Edition</span>
              </div>
            </div>
            {/* Language Switcher */}
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
              <button onClick={() => setLang('zh')} className={clsx("p-1.5 rounded text-xs font-bold transition-all", lang === 'zh' ? "bg-white shadow text-indigo-600" : "text-slate-400 hover:text-slate-600")}>中</button>
              <button onClick={() => setLang('ja')} className={clsx("p-1.5 rounded text-xs font-bold transition-all", lang === 'ja' ? "bg-white shadow text-indigo-600" : "text-slate-400 hover:text-slate-600")}>日</button>
              <button onClick={() => setLang('en')} className={clsx("p-1.5 rounded text-xs font-bold transition-all", lang === 'en' ? "bg-white shadow text-indigo-600" : "text-slate-400 hover:text-slate-600")}>EN</button>
            </div>
          </div>
          <p className="text-sm text-slate-500 leading-relaxed">
            {t.subtitle}
          </p>
        </div>

        <div className="flex-1 space-y-8">
          {/* Scenario Selector */}
          <section className="space-y-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <Zap size={14} /> {t.scenario}
            </h2>
            <div className="space-y-2">
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => applyScenario(s.id)}
                  className={clsx(
                    "w-full text-left px-4 py-3 rounded-xl transition-all border text-sm font-medium",
                    activeScenario === s.id
                      ? "bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-200"
                      : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                  )}
                >
                  {s.name[lang]}
                </button>
              ))}
            </div>
          </section>

          {/* Network Conditions */}
          <section className="space-y-6">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <Settings2 size={14} /> {t.env}
            </h2>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-5">

              {/* Runs (NEW) */}
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-sm font-semibold text-slate-700">{t.runs}</label>
                  <span className="text-xs font-mono font-bold bg-slate-200 text-slate-600 px-2 py-1 rounded">{config.runs}</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="500"
                  step="10"
                  value={config.runs}
                  onChange={e => updateConfig('runs', parseInt(e.target.value))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600 hover:accent-indigo-500 transition-all"
                />
              </div>

              {/* Packet Loss */}
              <div>
                <div className="flex justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-semibold text-slate-700">{t.pkt_loss}</label>
                    {config.p_loss > 0 && <span className="text-[10px] uppercase font-bold text-orange-500 bg-orange-100 px-1 rounded">Simulated</span>}
                  </div>
                  <span className="text-xs font-mono font-bold bg-slate-200 text-slate-600 px-2 py-1 rounded">{(config.p_loss * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="0.5"
                  step="0.01"
                  value={config.p_loss}
                  onChange={e => updateConfig('p_loss', parseFloat(e.target.value))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600 hover:accent-indigo-500 transition-all"
                />
              </div>

              {/* Packet Reordering */}
              <div>
                <div className="flex justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-semibold text-slate-700">{t.reorder}</label>
                    {config.p_reorder > 0 && <span className="text-[10px] uppercase font-bold text-yellow-500 bg-yellow-100 px-1 rounded">Simulated</span>}
                  </div>
                  <span className="text-xs font-mono font-bold bg-slate-200 text-slate-600 px-2 py-1 rounded">{(config.p_reorder * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="0.5"
                  step="0.01"
                  value={config.p_reorder}
                  onChange={e => updateConfig('p_reorder', parseFloat(e.target.value))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600 hover:accent-indigo-500 transition-all"
                />
              </div>

              {/* Window Size */}
              <div className={clsx("transition-opacity", !config.modes.includes('window') && "opacity-50 grayscale")}>
                <div className="flex justify-between mb-2">
                  <label className="text-sm font-semibold text-slate-700">{t.window}</label>
                  <span className="text-xs font-mono font-bold bg-slate-200 text-slate-600 px-2 py-1 rounded">{config.window_size}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="1"
                  value={config.window_size}
                  onChange={e => updateConfig('window_size', parseInt(e.target.value))}
                  disabled={!config.modes.includes('window')}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600 hover:accent-indigo-500 transition-all"
                />
              </div>
            </div>
          </section>

          {/* Modes */}
          <section className="space-y-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              {t.modes}
            </h2>
            <div className="grid grid-cols-1 gap-3">
              {(Object.keys(MODE_META) as Mode[]).map(modeId => (
                <label
                  key={modeId}
                  className={clsx(
                    "flex items-start space-x-3 p-3 rounded-xl border cursor-pointer transition-all duration-200",
                    config.modes.includes(modeId)
                      ? "bg-indigo-50/50 border-indigo-200 shadow-sm"
                      : "bg-white border-transparent hover:bg-slate-50"
                  )}
                >
                  <input
                    type="checkbox"
                    checked={config.modes.includes(modeId)}
                    onChange={(e) => {
                      if (e.target.checked) updateConfig('modes', [...config.modes, modeId]);
                      else updateConfig('modes', config.modes.filter(m => m !== modeId));
                    }}
                    className="mt-1 w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                  />
                  <div>
                    <span className={clsx("block text-sm font-bold", config.modes.includes(modeId) ? "text-indigo-900" : "text-slate-600")}>
                      {getModeLabel(modeId)}
                    </span>
                    <span className="text-xs text-slate-400">{getModeDesc(modeId)}</span>
                  </div>
                </label>
              ))}
            </div>
          </section>
        </div>

        <button
          onClick={handleRun}
          disabled={loading}
          className={`w-full mt-6 py-4 px-6 rounded-2xl flex items-center justify-center gap-2 text-white font-bold text-lg transition-all shadow-xl shadow-indigo-500/20 ${loading
            ? 'bg-slate-800 cursor-not-allowed opacity-80'
            : 'bg-slate-900 hover:bg-black hover:scale-[1.02] active:scale-[0.98]'
            }`}
        >
          {loading ? (
            <RefreshCw className="animate-spin" />
          ) : (
            <Play fill="currentColor" />
          )}
          {loading ? t.running : t.run_btn}
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6 lg:p-10 overflow-y-auto bg-slate-50/50">
        <header className="flex justify-between items-end mb-8">
          <div>
            <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">{t.dashboard}</h2>
            <p className="text-slate-500 mt-2">{t.dash_desc}</p>
          </div>
          {results && (
            <div className="text-right hidden sm:block">
              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider">{t.runs_stat}</span>
              <span className="text-2xl font-mono font-bold text-slate-900">{config.runs}</span>
            </div>
          )}
        </header>

        {!results && !loading && (
          <div className="flex flex-col items-center justify-center h-[60vh] text-slate-400 border-4 border-dashed border-slate-200 rounded-3xl bg-slate-100/50">
            <div className="w-20 h-20 bg-slate-200 rounded-full flex items-center justify-center mb-6">
              <Settings2 size={40} className="text-slate-400" />
            </div>
            <h3 className="text-xl font-bold text-slate-700 mb-2">{t.ready_title}</h3>
            <p className="max-w-md text-center">{t.ready_desc}</p>
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center h-[60vh]">
            <div className="relative">
              <div className="w-24 h-24 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <ShieldCheck className="text-indigo-600 animate-pulse" />
              </div>
            </div>
            <p className="mt-8 text-slate-500 font-medium animate-pulse">{t.running}... ({config.runs * config.modes.length} runs)</p>
          </div>
        )}

        {results && !loading && (
          <AnimatePresence>
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="space-y-8"
            >
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Chart 1: Usability */}
                <div className="bg-white p-8 rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100">
                  <div className="flex items-center gap-3 mb-8">
                    <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                      <CheckCircle2 size={20} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-900">{t.usability}</h3>
                      <p className="text-xs text-slate-500">{t.usability_sub}</p>
                    </div>
                  </div>

                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={results} layout="vertical" margin={{ left: 0, right: 30 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#e2e8f0" />
                        <XAxis type="number" domain={[0, 1]} hide />
                        <YAxis
                          dataKey="mode"
                          type="category"
                          width={140}
                          tickFormatter={(val) => getModeLabel(val).split(' ')[0]}
                          tick={{ fill: '#64748b', fontSize: 12, fontWeight: 600 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          cursor={{ fill: '#f8fafc' }}
                          contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                          formatter={(value: number) => [<span className="font-bold text-slate-800">{(value * 100).toFixed(1)}%</span>, "Acceptance"]}
                        />
                        <Bar dataKey="avg_legit_rate" radius={[0, 6, 6, 0]} barSize={40} background={{ fill: '#f1f5f9', radius: [0, 6, 6, 0] }}>
                          <LabelList
                            dataKey="avg_legit_rate"
                            position="insideRight"
                            fill="white"
                            formatter={(val: number) => `${(val * 100).toFixed(1)}%`}
                            style={{ fontWeight: 'bold', fontSize: '12px', paddingRight: '10px' }}
                          />
                          {results.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={MODE_META[entry.mode]?.color} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Chart 2: Security */}
                <div className="bg-white p-8 rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100">
                  <div className="flex items-center gap-3 mb-8">
                    <div className="p-2 bg-red-50 text-red-600 rounded-lg">
                      <AlertTriangle size={20} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-900">{t.security}</h3>
                      <p className="text-xs text-slate-500">{t.security_sub}</p>
                    </div>
                  </div>

                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={results} margin={{ top: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                        <XAxis
                          dataKey="mode"
                          tickFormatter={(val) => getModeLabel(val).split(' ')[0]}
                          tick={{ fill: '#64748b', fontSize: 11, fontWeight: 600 }}
                          axisLine={false}
                          tickLine={false}
                          dy={10}
                        />
                        <YAxis
                          tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                          tick={{ fill: '#94a3b8', fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          cursor={{ fill: '#f8fafc' }}
                          contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                          formatter={(value: number) => [<span className="font-bold text-slate-800">{(value * 100).toFixed(2)}%</span>, "Success Rate"]}
                        />
                        <Bar dataKey="avg_attack_rate" radius={[6, 6, 0, 0]} barSize={48}>
                          <LabelList
                            dataKey="avg_attack_rate"
                            position="top"
                            fill="#64748b"
                            formatter={(val: number) => val > 0 ? `${(val * 100).toFixed(1)}%` : ''}
                            style={{ fontWeight: 'bold', fontSize: '11px' }}
                          />
                          {results.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={MODE_META[entry.mode]?.color} fillOpacity={0.9} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Data Table */}
              <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-100">
                    <tr>
                      <th className="p-4 font-semibold text-slate-500">{t.table_proto}</th>
                      <th className="p-4 font-semibold text-slate-500">{t.table_usable}</th>
                      <th className="p-4 font-semibold text-slate-500">{t.table_risk}</th>
                      <th className="p-4 font-semibold text-slate-500">{t.table_stab}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {results.map((res) => (
                      <tr key={res.mode} className="hover:bg-slate-50/50 transition-colors">
                        <td className="p-4 font-bold text-slate-900 flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: MODE_META[res.mode]?.color }} />
                          {getModeLabel(res.mode)}
                        </td>
                        <td className="p-4">
                          <span className={clsx(
                            "px-2 py-1 rounded-md font-bold text-xs",
                            res.avg_legit_rate > 0.9 ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                          )}>
                            {(res.avg_legit_rate * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="p-4">
                          <span className={clsx(
                            "px-2 py-1 rounded-md font-bold text-xs",
                            res.avg_attack_rate < 0.01 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                          )}>
                            {(res.avg_attack_rate * 100).toFixed(2)}%
                          </span>
                        </td>
                        <td className="p-4 text-slate-400 font-mono text-xs">
                          ±{(res.std_legit_rate * 100).toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          </AnimatePresence>
        )}
      </main>
    </div>
  );
}
