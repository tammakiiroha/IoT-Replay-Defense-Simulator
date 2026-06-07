'use client';

import { startTransition, useEffect, useState } from 'react';
import Image from 'next/image';
import { ArrowRight, FileSpreadsheet, RadioTower } from 'lucide-react';
import { useLocale } from './locale-context';
import type { ArtifactManifest, ExperimentArtifact } from '../lib/contracts';
import { loadArtifact, loadManifest } from '../lib/data';
import type { Locale } from '../lib/i18n';
import { withBasePath } from '../lib/site';

type FigureKey = 'frontier' | 'loss' | 'reorder' | 'hardwareLegit';

type ResultsCopy = {
  loading: string;
  datasetsTitle: string;
  figuresTitle: string;
  highlights: Record<string, { label: string; value: string }>;
  artifactKinds: Record<string, string>;
  artifacts: Record<string, { title: string; description: string }>;
  summaryLabels: Record<string, string>;
  figures: Record<FigureKey, { alt: string }>;
};

const COPY = {
  en: {
    loading: 'Loading versioned artifacts...',
    datasetsTitle: 'Versioned datasets',
    figuresTitle: 'Reference figures',
    highlights: {
      Authority: {
        label: 'Authority',
        value: 'Python core is the sole simulation source of truth',
      },
      Modes: {
        label: 'Modes',
        value: 'Hybrid local runtime plus static public showcase',
      },
      Evidence: {
        label: 'Evidence',
        value: 'Simulation sweeps and physical validation artifacts are versioned',
      },
    },
    artifactKinds: {
      simulation_dataset: 'Simulation dataset',
      lab_validation: 'Lab validation',
    },
    artifacts: {
      'p-loss-sweep': {
        title: 'Packet-loss sweep',
        description: 'Versioned simulation dataset exported from the packet-loss sweep.',
      },
      'p-reorder-sweep': {
        title: 'Packet-reorder sweep',
        description: 'Versioned simulation dataset exported from the packet-reordering sweep.',
      },
      'window-sweep': {
        title: 'Window-size sweep',
        description: 'Versioned simulation dataset for sliding-window tradeoff analysis.',
      },
      'validation-20260316-164739': {
        title: 'Physical validation run',
        description: 'HackRF/GNU Radio validation artifact aligned with the simulation evidence chain.',
      },
    },
    summaryLabels: {
      records: 'Records',
      best_legit_mode: 'Best legitimate mode',
      best_legit_rate: 'Best legitimate rate',
      lowest_attack_mode: 'Lowest attack mode',
      lowest_attack_rate: 'Lowest attack rate',
      total_configs: 'Total configs',
      passed: 'Passed',
      failed: 'Failed',
      loss_samples_tested: 'Loss samples tested',
    },
    figures: {
      frontier: { alt: 'Security-cost frontier figure' },
      loss: { alt: 'Packet-loss sweep figure' },
      reorder: { alt: 'Packet-reordering sweep figure' },
      hardwareLegit: { alt: 'Simulation versus hardware legitimate-acceptance figure' },
    },
  },
  ja: {
    loading: 'バージョン付きアーティファクトを読み込んでいます...',
    datasetsTitle: 'バージョン付きデータセット',
    figuresTitle: '参照図',
    highlights: {
      Authority: {
        label: '基準',
        value: 'シミュレーションの唯一の基準は Python コアです',
      },
      Modes: {
        label: 'モード',
        value: 'ローカルのハイブリッド実行環境と静的公開サイトを併用します',
      },
      Evidence: {
        label: '証拠',
        value: 'シミュレーションスイープと物理検証アーティファクトをバージョン管理します',
      },
    },
    artifactKinds: {
      simulation_dataset: 'シミュレーションデータセット',
      lab_validation: 'ラボ検証',
    },
    artifacts: {
      'p-loss-sweep': {
        title: 'パケット損失スイープ',
        description: 'パケット損失スイープから出力したバージョン付きシミュレーションデータです。',
      },
      'p-reorder-sweep': {
        title: 'パケット並べ替えスイープ',
        description: 'パケット並べ替え条件から出力したバージョン付きシミュレーションデータです。',
      },
      'window-sweep': {
        title: 'ウィンドウサイズスイープ',
        description: 'スライディングウィンドウのトレードオフ分析用データです。',
      },
      'validation-20260316-164739': {
        title: '物理検証実行',
        description: 'シミュレーション証拠チェーンに対応する HackRF/GNU Radio 検証アーティファクトです。',
      },
    },
    summaryLabels: {
      records: 'レコード数',
      best_legit_mode: '正規通信の最良モード',
      best_legit_rate: '正規通信の最良率',
      lowest_attack_mode: '攻撃成功率が最小のモード',
      lowest_attack_rate: '最小攻撃成功率',
      total_configs: '設定数',
      passed: '成功',
      failed: '失敗',
      loss_samples_tested: '検証した損失サンプル',
    },
    figures: {
      frontier: { alt: 'セキュリティとコストのフロンティア図' },
      loss: { alt: 'パケット損失スイープ図' },
      reorder: { alt: 'パケット並べ替えスイープ図' },
      hardwareLegit: { alt: 'シミュレーションとハードウェアの正規受理率比較図' },
    },
  },
  zh: {
    loading: '正在加载版本化 artifact...',
    datasetsTitle: '版本化数据集',
    figuresTitle: '参考图表',
    highlights: {
      Authority: {
        label: '权威来源',
        value: 'Python 核心是模拟结果的唯一事实来源',
      },
      Modes: {
        label: '运行模式',
        value: '本地混合运行时加静态公开展示',
      },
      Evidence: {
        label: '证据链',
        value: '模拟 sweep 与物理验证 artifact 都有版本记录',
      },
    },
    artifactKinds: {
      simulation_dataset: '模拟数据集',
      lab_validation: '实验室验证',
    },
    artifacts: {
      'p-loss-sweep': {
        title: '丢包 sweep',
        description: '从丢包参数 sweep 导出的版本化模拟数据集。',
      },
      'p-reorder-sweep': {
        title: '乱序 sweep',
        description: '从包乱序参数 sweep 导出的版本化模拟数据集。',
      },
      'window-sweep': {
        title: '窗口大小 sweep',
        description: '用于分析滑动窗口权衡关系的版本化模拟数据集。',
      },
      'validation-20260316-164739': {
        title: '物理验证运行',
        description: '与模拟证据链对齐的 HackRF/GNU Radio 验证 artifact。',
      },
    },
    summaryLabels: {
      records: '记录数',
      best_legit_mode: '合法通过率最佳模式',
      best_legit_rate: '最佳合法通过率',
      lowest_attack_mode: '攻击成功率最低模式',
      lowest_attack_rate: '最低攻击成功率',
      total_configs: '配置数',
      passed: '通过',
      failed: '失败',
      loss_samples_tested: '已测试丢包样本',
    },
    figures: {
      frontier: { alt: '安全成本前沿图' },
      loss: { alt: '丢包 sweep 图' },
      reorder: { alt: '乱序 sweep 图' },
      hardwareLegit: { alt: '模拟与硬件合法通过率对比图' },
    },
  },
} satisfies Record<Locale, ResultsCopy>;

const FIGURES: Array<{ key: FigureKey; src: string }> = [
  { key: 'frontier', src: '/data/security_cost_frontier.png' },
  { key: 'loss', src: '/data/p_loss_dual.png' },
  { key: 'reorder', src: '/data/p_reorder_dual.png' },
  { key: 'hardwareLegit', src: '/data/sim_vs_hw_legit.png' },
];

const MODE_LABELS: Record<string, Record<Locale, string>> = {
  no_def: { en: 'No defense', ja: '防御なし', zh: '无防御' },
  rolling: { en: 'Rolling counter', ja: 'ローリングカウンタ', zh: '滚动计数器' },
  window: { en: 'Sliding window', ja: 'スライディングウィンドウ', zh: '滑动窗口' },
  challenge_response: { en: 'Challenge-response', ja: 'チャレンジレスポンス', zh: '挑战-响应' },
  hsw_cr: { en: 'HSW-CR adaptive', ja: 'HSW-CR 適応型', zh: 'HSW-CR 自适应' },
  oscore_like: { en: 'OSCORE-like window', ja: 'OSCORE-like ウィンドウ', zh: 'OSCORE-like 窗口' },
};

export function ResultsOverview() {
  const { locale } = useLocale();
  const copy: ResultsCopy = COPY[locale];
  const [manifest, setManifest] = useState<ArtifactManifest | null>(null);
  const [artifacts, setArtifacts] = useState<ExperimentArtifact[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const nextManifest = await loadManifest();
        const nextArtifacts = await Promise.all(
          nextManifest.artifacts.map((artifact) => loadArtifact(artifact.path)),
        );
        if (!active) {
          return;
        }
        startTransition(() => {
          setError(null);
          setManifest(nextManifest);
          setArtifacts(nextArtifacts);
        });
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load manifest');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <div className="panel">
        <p className="text-sm text-rose-700">{error}</p>
      </div>
    );
  }

  if (!manifest) {
    return (
      <div className="panel">
        <p className="text-sm text-stone-600">{copy.loading}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-3">
        {manifest.highlights.map((highlight) => {
          const highlightCopy = copy.highlights[String(highlight.label)];
          return (
            <div key={String(highlight.label)} className="panel">
              <p className="eyebrow">{highlightCopy?.label ?? String(highlight.label)}</p>
              <p className="mt-3 text-lg font-semibold text-stone-950">
                {highlightCopy?.value ?? String(highlight.value)}
              </p>
            </div>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="panel">
          <div className="mb-6 flex items-center gap-3">
            <FileSpreadsheet className="h-5 w-5 text-teal-700" />
            <h3 className="text-xl font-semibold">{copy.datasetsTitle}</h3>
          </div>
          <div className="space-y-4">
            {artifacts.map((artifact) => {
              const artifactCopy = copy.artifacts[artifact.artifact_id];
              return (
                <article key={artifact.artifact_id} className="rounded-lg border border-stone-900/10 bg-white/70 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="eyebrow">{copy.artifactKinds[artifact.kind] ?? artifact.kind}</p>
                      <h4 className="mt-2 text-lg font-semibold">
                        {artifactCopy?.title ?? artifact.title}
                      </h4>
                      <p className="mt-2 text-sm leading-6 text-stone-600">
                        {artifactCopy?.description ?? artifact.description}
                      </p>
                    </div>
                    <ArrowRight className="mt-1 h-5 w-5 shrink-0 text-stone-400" />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {Object.entries(artifact.summary).slice(0, 4).map(([key, value]) => (
                      <div key={key} className="rounded-md border border-stone-900/10 bg-stone-50/80 p-3">
                        <p className="text-[11px] uppercase text-stone-500">
                          {copy.summaryLabels[key] ?? key}
                        </p>
                        <p className="mt-2 text-sm font-medium text-stone-950">
                          {formatSummaryValue(key, value, locale)}
                        </p>
                      </div>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <div className="panel">
            <div className="mb-4 flex items-center gap-3">
              <RadioTower className="h-5 w-5 text-amber-700" />
              <h3 className="text-xl font-semibold">{copy.figuresTitle}</h3>
            </div>
            <div className="space-y-4">
              {FIGURES.map((figure) => (
                <div key={figure.src} className="overflow-hidden rounded-lg border border-stone-900/10 bg-white/70">
                  <Image
                    src={withBasePath(figure.src)}
                    alt={copy.figures[figure.key].alt}
                    width={1200}
                    height={800}
                    loading="eager"
                    className="h-auto w-full"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatSummaryValue(key: string, value: unknown, locale: Locale): string {
  if (typeof value === 'string' && MODE_LABELS[value]) {
    return MODE_LABELS[value][locale];
  }

  if (typeof value === 'number') {
    if (key.endsWith('_rate')) {
      return `${(value * 100).toLocaleString(locale, { maximumFractionDigits: 1 })}%`;
    }
    return value.toLocaleString(locale, { maximumFractionDigits: 3 });
  }

  if (Array.isArray(value)) {
    return value.map((entry) => formatSummaryValue(key, entry, locale)).join(', ');
  }

  return String(value);
}
