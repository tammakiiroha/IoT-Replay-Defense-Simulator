'use client';

import { useLocale } from '../../components/locale-context';
import { Panel, SiteShell } from '../../components/site-shell';
import type { Locale } from '../../lib/i18n';

type ReproducibilityCopy = {
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
      eyebrow: 'Reproducibility',
      title: 'Auditable research artifacts.',
      intro:
        'This page frames the repository as a reproducible research product: static evidence for examiners, browser demo runs for quick exploration, local authoritative runtime for deep verification, and explicit contracts between them.',
    },
    panels: [
      {
        title: 'Static data',
        text: '`web/public/data/manifest.json` and versioned artifact files back the public Pages deployment.',
      },
      {
        title: 'Local runtime',
        text:
          '`start_app.sh` runs FastAPI plus Next.js so the site can submit authoritative simulations to the Python backend.',
      },
      {
        title: 'Static simulator',
        text: 'The public `/simulator` page falls back to a browser-side demo model when the Python API is absent.',
      },
      {
        title: 'Validation chain',
        text:
          'Physical validation artifacts remain readable, and normalized wrappers make them easier to compare and surface in the website.',
      },
    ],
  },
  ja: {
    shell: {
      eyebrow: '再現性',
      title: '監査可能な研究アーティファクト',
      intro:
        'このページでは、リポジトリを再現可能な研究プロダクトとして整理します。審査用の静的証拠、素早い探索用のブラウザ実行、深い検証用のローカル正式実行環境、それらをつなぐ契約を明示します。',
    },
    panels: [
      {
        title: '静的データ',
        text:
          '`web/public/data/manifest.json` とバージョン付きアーティファクトが公開 Pages デプロイを支えます。',
      },
      {
        title: 'ローカル実行環境',
        text:
          '`start_app.sh` は FastAPI と Next.js を起動し、サイトから Python バックエンドへ正式なシミュレーションを送れるようにします。',
      },
      {
        title: '静的シミュレータ',
        text:
          '公開 `/simulator` ページは、Python API がない場合にブラウザ内デモモデルへ切り替わります。',
      },
      {
        title: '検証チェーン',
        text:
          '物理検証アーティファクトは読みやすく保ち、正規化ラッパーによって比較と Web 表示をしやすくします。',
      },
    ],
  },
  zh: {
    shell: {
      eyebrow: '可复现性',
      title: '可审查的研究 artifact',
      intro:
        '本页把仓库整理成可复现研究产品：给审查者看的静态证据、用于快速探索的浏览器演示、本地正式验证运行时，以及连接它们的明确契约。',
    },
    panels: [
      {
        title: '静态数据',
        text: '`web/public/data/manifest.json` 和版本化 artifact 文件支撑公开 Pages 部署。',
      },
      {
        title: '本地运行时',
        text:
          '`start_app.sh` 会启动 FastAPI 与 Next.js，使网站可以把正式模拟请求提交给 Python 后端。',
      },
      {
        title: '静态模拟器',
        text: '公开 `/simulator` 页面在没有 Python API 时会切换到浏览器端演示模型。',
      },
      {
        title: '验证链',
        text:
          '物理验证 artifact 保持可读，并通过规范化 wrapper 变得更容易比较和展示到网站中。',
      },
    ],
  },
} satisfies Record<Locale, ReproducibilityCopy>;

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

export default function ReproducibilityPage() {
  const fallback = COPY.en.shell;
  return (
    <SiteShell
      eyebrow={fallback.eyebrow}
      title={fallback.title}
      intro={fallback.intro}
      shellCopy={SHELL_COPY}
    >
      <ReproducibilityContent />
    </SiteShell>
  );
}

function ReproducibilityContent() {
  const { locale } = useLocale();
  const copy = COPY[locale];

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {copy.panels.map((panel) => (
        <Panel key={panel.title} title={panel.title}>
          <p className="text-sm leading-7 text-stone-700">{panel.text}</p>
        </Panel>
      ))}
    </div>
  );
}
