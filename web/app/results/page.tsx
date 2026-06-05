import { ResultsOverview } from '../../components/results-overview';
import { SiteShell } from '../../components/site-shell';

const SHELL_COPY = {
  eyebrow: {
    en: 'Results',
    ja: '結果',
    zh: '结果',
  },
  title: {
    en: 'Generated result artifacts.',
    ja: '生成アーティファクトとしての結果',
    zh: '生成式结果 artifact',
  },
  intro: {
    en: 'The public site reads versioned JSON artifacts and reference figures generated from the research workflow. That keeps the showcase aligned with the thesis evidence chain.',
    ja: '公開サイトは、研究ワークフローから生成されたバージョン付き JSON アーティファクトと参照図を読み込みます。これにより表示内容を論文の証拠チェーンと一致させます。',
    zh: '公开站点读取研究流程生成的版本化 JSON artifact 和参考图，使展示内容与论文证据链保持一致。',
  },
};

export default function ResultsPage() {
  return (
    <SiteShell
      eyebrow={SHELL_COPY.eyebrow.en}
      title={SHELL_COPY.title.en}
      intro={SHELL_COPY.intro.en}
      shellCopy={SHELL_COPY}
    >
      <ResultsOverview />
    </SiteShell>
  );
}
