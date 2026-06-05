'use client';

import Link from 'next/link';
import {
  ArrowRight,
  ChartNoAxesCombined,
  FlaskConical,
  Radio,
  Shield,
  type LucideIcon,
} from 'lucide-react';
import { useLocale } from '../components/locale-context';
import { Panel, SiteShell } from '../components/site-shell';
import type { Locale } from '../lib/i18n';
import { withLocale } from '../lib/i18n';

type HomeNavKey = 'simulator' | 'results' | 'hardware' | 'reproducibility';

type HomeCopy = {
  shell: {
    eyebrow: string;
    title: string;
    intro: string;
  };
  northStar: {
    title: string;
    description: string;
    modes: Array<{
      eyebrow: string;
      title: string;
      text: string;
    }>;
  };
  fast: {
    title: string;
    description: string;
    items: Record<HomeNavKey, { label: string; text: string }>;
  };
  boundaries: Array<{
    title: string;
    text: string;
  }>;
};

const COPY = {
  en: {
    shell: {
      eyebrow: 'Replay Research Platform',
      title: 'ReplayBench-IoT',
      intro:
        'A thesis-grade replay-attack defense simulator with a static public showcase, a browser-side demo path, and a Python runtime for authoritative research runs.',
    },
    northStar: {
      title: 'Product contract',
      description:
        'The simulator, validation workflow, and website now point at the same evidence chain instead of separate demo surfaces.',
      modes: [
        {
          eyebrow: 'Public deploy',
          title: 'Static evidence reader',
          text:
            'GitHub Pages serves generated artifacts, figures, methodology, reproducibility notes, and a browser-side simulator for quick exploration.',
        },
        {
          eyebrow: 'Local full stack',
          title: 'Authoritative runtime',
          text:
            'FastAPI delegates live runs, sweeps, and physical-alignment checks to the Python core used by the thesis workflow.',
        },
      ],
    },
    fast: {
      title: 'Fast navigation',
      description: 'Use the site as a thesis evidence map, not only as a form for one simulation run.',
      items: {
        simulator: {
          label: 'Authoritative Simulator',
          text: 'Run replay-defense scenarios locally through Python or use the public browser fallback.',
        },
        results: {
          label: 'Results & Figures',
          text: 'Inspect sweep datasets, generated artifacts, and reference charts.',
        },
        hardware: {
          label: 'Physical Validation',
          text: 'Trace how simulation assumptions connect to HackRF-backed experiments.',
        },
        reproducibility: {
          label: 'Reproducibility',
          text: 'Find commands, artifacts, and boundary notes needed for independent checks.',
        },
      },
    },
    boundaries: [
      {
        title: 'Authority boundary',
        text:
          'The browser simulator is for exploration. Release artifacts, CLI/API runs, and research-grade numbers come from the Python runtime.',
      },
      {
        title: 'Experiment boundary',
        text:
          'Simulation sweeps and physical comparisons produce versioned artifacts with explicit metadata.',
      },
      {
        title: 'Migration boundary',
        text:
          'Legacy CLI, API, and GUI entrypoints remain as compatibility shells while the new product structure settles.',
      },
    ],
  },
  ja: {
    shell: {
      eyebrow: 'Replay 研究プラットフォーム',
      title: 'ReplayBench-IoT',
      intro:
        'リプレイ攻撃防御を評価する研究用シミュレータです。公開サイト、ブラウザ内デモ、正式な Python 実行環境を一つの証拠ラインとして扱います。',
    },
    northStar: {
      title: 'プロダクトの基準',
      description:
        'シミュレータ、検証フロー、Web サイトを別々のデモではなく、同じ研究証拠の流れとして揃えています。',
      modes: [
        {
          eyebrow: '公開デプロイ',
          title: '静的な証拠ビューア',
          text:
            'GitHub Pages では生成済みアーティファクト、図、手法、再現性メモ、ブラウザ内シミュレータを確認できます。',
        },
        {
          eyebrow: 'ローカル実行',
          title: '正式な実行環境',
          text:
            'FastAPI がライブ実行、スイープ、物理実験との照合を論文ワークフローの Python コアへ渡します。',
        },
      ],
    },
    fast: {
      title: 'クイックナビゲーション',
      description: 'このサイトは単なる入力フォームではなく、論文の証拠マップとして使えます。',
      items: {
        simulator: {
          label: '正式シミュレータ',
          text: 'ローカルでは Python 経由で実行し、公開サイトではブラウザ内フォールバックを使います。',
        },
        results: {
          label: '結果と図',
          text: 'スイープデータセット、生成アーティファクト、参照図を確認します。',
        },
        hardware: {
          label: '物理検証',
          text: 'シミュレーション仮定と HackRF 実験のつながりを示します。',
        },
        reproducibility: {
          label: '再現性',
          text: '独立確認に必要なコマンド、アーティファクト、境界条件を整理します。',
        },
      },
    },
    boundaries: [
      {
        title: '権威境界',
        text:
          'ブラウザシミュレータは探索用です。公開アーティファクト、CLI/API 実行、研究用数値は Python 実行環境を基準にします。',
      },
      {
        title: '実験境界',
        text:
          'シミュレーションスイープと物理比較は、明示的なメタデータ付きのバージョン化アーティファクトを出力します。',
      },
      {
        title: '移行境界',
        text:
          '従来の CLI、API、GUI エントリポイントは、新構造が安定するまで互換シェルとして残します。',
      },
    ],
  },
  zh: {
    shell: {
      eyebrow: 'Replay 研究平台',
      title: 'ReplayBench-IoT',
      intro:
        '面向论文级验证的重放攻击防御模拟器：公开站点负责证据展示，浏览器路径负责快速演示，Python 运行时负责正式研究结果。',
    },
    northStar: {
      title: '产品契约',
      description:
        '模拟器、验证流程和网站现在围绕同一条证据链组织，而不是分散在几个临时 demo 入口里。',
      modes: [
        {
          eyebrow: '公开部署',
          title: '静态证据阅读器',
          text:
            'GitHub Pages 展示生成后的 artifact、图表、方法说明、可复现性记录，并提供浏览器端模拟器用于快速探索。',
        },
        {
          eyebrow: '本地全栈',
          title: '正式运行时',
          text:
            'FastAPI 将实时运行、参数 sweep 和物理实验对齐检查交给论文工作流使用的 Python 核心。',
        },
      ],
    },
    fast: {
      title: '快速导航',
      description: '把这个网站当作论文证据地图使用，而不是只当作一次模拟运行的表单。',
      items: {
        simulator: {
          label: '正式模拟器',
          text: '本地通过 Python 跑正式结果；公开站点使用浏览器端 fallback 做快速演示。',
        },
        results: {
          label: '结果与图表',
          text: '查看 sweep 数据集、生成 artifact 和公开参考图。',
        },
        hardware: {
          label: '物理验证',
          text: '说明模拟假设如何连接到 HackRF 支撑的实验流程。',
        },
        reproducibility: {
          label: '可复现性',
          text: '整理独立复查需要的命令、artifact 和边界说明。',
        },
      },
    },
    boundaries: [
      {
        title: '权威边界',
        text:
          '浏览器模拟器用于交互探索。发布 artifact、CLI/API 运行和研究级数值都以 Python 运行时为准。',
      },
      {
        title: '实验边界',
        text:
          '模拟 sweep 与物理对比都会输出带明确元数据的版本化 artifact。',
      },
      {
        title: '迁移边界',
        text:
          '旧 CLI、API 和 GUI 入口继续作为兼容壳存在，直到新的产品结构稳定下来。',
      },
    ],
  },
} satisfies Record<Locale, HomeCopy>;

const SHELL_COPY = {
  eyebrow: {
    en: COPY.en.shell.eyebrow,
    ja: COPY.ja.shell.eyebrow,
    zh: COPY.zh.shell.eyebrow,
  },
  title: {
    en: COPY.en.shell.title,
    ja: COPY.ja.shell.title,
    zh: COPY.zh.shell.title,
  },
  intro: {
    en: COPY.en.shell.intro,
    ja: COPY.ja.shell.intro,
    zh: COPY.zh.shell.intro,
  },
};

const NAV_ITEMS: Array<{ key: HomeNavKey; href: string; icon: LucideIcon }> = [
  { href: '/simulator', key: 'simulator', icon: Shield },
  { href: '/results', key: 'results', icon: ChartNoAxesCombined },
  { href: '/hardware', key: 'hardware', icon: Radio },
  { href: '/reproducibility', key: 'reproducibility', icon: FlaskConical },
];

export default function HomePage() {
  const fallback = COPY.en.shell;
  return (
    <SiteShell
      eyebrow={fallback.eyebrow}
      title={fallback.title}
      intro={fallback.intro}
      shellCopy={SHELL_COPY}
    >
      <HomeContent />
    </SiteShell>
  );
}

function HomeContent() {
  const { locale } = useLocale();
  const copy = COPY[locale];

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel title={copy.northStar.title} description={copy.northStar.description}>
          <div className="grid gap-4 sm:grid-cols-2">
            {copy.northStar.modes.map((mode) => (
              <div key={mode.title} className="rounded-lg border border-stone-900/10 bg-white/70 p-5">
                <p className="eyebrow">{mode.eyebrow}</p>
                <h3 className="mt-3 text-xl font-semibold">{mode.title}</h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">{mode.text}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title={copy.fast.title} description={copy.fast.description}>
          <div className="grid gap-3">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const navCopy = copy.fast.items[item.key];
              return (
                <Link
                  key={item.href}
                  href={withLocale(item.href, locale)}
                  className="group flex items-start justify-between gap-4 rounded-lg border border-stone-900/10 bg-white/70 p-5 transition hover:-translate-y-0.5"
                >
                  <div className="flex min-w-0 items-start gap-4">
                    <Icon className="mt-1 h-5 w-5 shrink-0 text-teal-700" />
                    <div className="min-w-0">
                      <h3 className="text-lg font-semibold text-stone-950">{navCopy.label}</h3>
                      <p className="mt-2 max-w-md text-sm leading-6 text-stone-600">{navCopy.text}</p>
                    </div>
                  </div>
                  <ArrowRight className="mt-1 h-5 w-5 shrink-0 text-stone-400 transition group-hover:translate-x-1" />
                </Link>
              );
            })}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {copy.boundaries.map((boundary) => (
          <Panel key={boundary.title} title={boundary.title}>
            <p className="text-sm leading-7 text-stone-700">{boundary.text}</p>
          </Panel>
        ))}
      </div>
    </>
  );
}
