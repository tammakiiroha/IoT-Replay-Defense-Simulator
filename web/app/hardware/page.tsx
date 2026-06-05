'use client';

import { useLocale } from '../../components/locale-context';
import { Panel, SiteShell } from '../../components/site-shell';
import type { Locale } from '../../lib/i18n';

type HardwareCopy = {
  shell: {
    eyebrow: string;
    title: string;
    intro: string;
  };
  panels: Array<{
    title: string;
    text: string;
  }>;
};

const COPY = {
  en: {
    shell: {
      eyebrow: 'Hardware',
      title: 'Physical validation lane.',
      intro:
        'The HackRF and GNU Radio flowgraphs stay in the repository, while the web explains them as part of the same research architecture instead of a sidecar folder.',
    },
    panels: [
      {
        title: 'What stays physical',
        text:
          'Flowgraphs, device orchestration, and Linux/HackRF assumptions remain under `physical_experiment/flowgraphs` and `physical_experiment/scripts`.',
      },
      {
        title: 'What becomes shared',
        text:
          'Validation outputs, config snapshots, and simulation-versus-hardware comparisons feed the same artifact pipeline used by the showcase website.',
      },
    ],
  },
  ja: {
    shell: {
      eyebrow: 'ハードウェア',
      title: '物理検証レーン',
      intro:
        'HackRF と GNU Radio のフローグラフはリポジトリに残しつつ、Web では別フォルダ扱いではなく同じ研究アーキテクチャの一部として説明します。',
    },
    panels: [
      {
        title: '物理側に残るもの',
        text:
          'フローグラフ、デバイス制御、Linux/HackRF 前提は `physical_experiment/flowgraphs` と `physical_experiment/scripts` に残します。',
      },
      {
        title: '共有されるもの',
        text:
          '検証出力、設定スナップショット、シミュレーション対ハードウェア比較は、公開サイトと同じアーティファクトパイプラインへ流します。',
      },
    ],
  },
  zh: {
    shell: {
      eyebrow: '硬件',
      title: '物理验证链路',
      intro:
        'HackRF 和 GNU Radio flowgraph 继续保留在仓库里，但网站会把它们解释为同一研究架构的一部分，而不是旁支文件夹。',
    },
    panels: [
      {
        title: '继续留在物理侧的内容',
        text:
          'Flowgraph、设备编排和 Linux/HackRF 假设仍位于 `physical_experiment/flowgraphs` 与 `physical_experiment/scripts`。',
      },
      {
        title: '进入共享链路的内容',
        text:
          '验证输出、配置快照和模拟-硬件对比会进入公开站点使用的同一条 artifact pipeline。',
      },
    ],
  },
} satisfies Record<Locale, HardwareCopy>;

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

export default function HardwarePage() {
  const fallback = COPY.en.shell;
  return (
    <SiteShell
      eyebrow={fallback.eyebrow}
      title={fallback.title}
      intro={fallback.intro}
      shellCopy={SHELL_COPY}
    >
      <HardwareContent />
    </SiteShell>
  );
}

function HardwareContent() {
  const { locale } = useLocale();
  const copy = COPY[locale];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {copy.panels.map((panel) => (
        <Panel key={panel.title} title={panel.title}>
          <p className="text-sm leading-7 text-stone-700">{panel.text}</p>
        </Panel>
      ))}
    </div>
  );
}
