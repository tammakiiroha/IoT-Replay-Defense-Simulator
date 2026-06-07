'use client';

import { useLocale } from '../../components/locale-context';
import { Panel, SiteShell } from '../../components/site-shell';
import type { Locale } from '../../lib/i18n';

type MethodologyCopy = {
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
      eyebrow: 'Methodology',
      title: 'One inspectable method pipeline.',
      intro:
        'The platform separates core simulation logic, typed contracts, application services, and presentation surfaces so the methodology is inspectable instead of being buried in ad hoc entrypoints.',
    },
    panels: [
      {
        title: 'Core',
        text:
          'Sender, receiver, attacker, channel, RNG, and experiment runner sit behind the `src/replay/core` package boundary.',
      },
      {
        title: 'Contracts',
        text:
          'API requests, sweep specs, simulation responses, and static artifacts use versioned Pydantic contracts that also generate the web type surface.',
      },
      {
        title: 'Services',
        text:
          'CLI, API, and artifact generation call the same service layer, so presentation changes do not fork experiment behavior.',
      },
    ],
  },
  ja: {
    shell: {
      eyebrow: '手法',
      title: '確認できる手法パイプライン',
      intro:
        '中核シミュレーション、型付き契約、アプリケーションサービス、表示層を分離し、手法がアドホックな入口に埋もれない構造にしています。',
    },
    panels: [
      {
        title: 'コア',
        text:
          '送信者、受信者、攻撃者、チャネル、乱数、実験ランナーは `src/replay/core` の境界内に置かれています。',
      },
      {
        title: '契約',
        text:
          'API リクエスト、スイープ仕様、シミュレーション応答、静的アーティファクトは、Web 型定義も生成するバージョン付き Pydantic 契約で管理します。',
      },
      {
        title: 'サービス',
        text:
          'CLI、API、アーティファクト生成は同じサービス層を呼ぶため、表示変更で実験挙動が分岐しません。',
      },
    ],
  },
  zh: {
    shell: {
      eyebrow: '方法',
      title: '可审查的方法 pipeline',
      intro:
        '平台把核心模拟逻辑、类型化契约、应用服务和展示层拆开，使方法本身可审查，而不是埋在零散入口中。',
    },
    panels: [
      {
        title: '核心',
        text:
          '发送端、接收端、攻击者、信道、随机数和实验 runner 都收敛在 `src/replay/core` 包边界内。',
      },
      {
        title: '契约',
        text:
          'API 请求、sweep 规格、模拟响应和静态 artifact 使用版本化 Pydantic contract，并同步生成 Web 类型表面。',
      },
      {
        title: '服务层',
        text:
          'CLI、API 和 artifact 生成都调用同一层服务，因此展示层变化不会分叉实验行为。',
      },
    ],
  },
} satisfies Record<Locale, MethodologyCopy>;

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

export default function MethodologyPage() {
  const fallback = COPY.en.shell;
  return (
    <SiteShell
      eyebrow={fallback.eyebrow}
      title={fallback.title}
      intro={fallback.intro}
      shellCopy={SHELL_COPY}
    >
      <MethodologyContent />
    </SiteShell>
  );
}

function MethodologyContent() {
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
