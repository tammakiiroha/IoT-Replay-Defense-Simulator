import { SimulatorPageContent } from '../../components/simulator-page-content';
import { SiteShell } from '../../components/site-shell';

export default function SimulatorPage() {
  return (
    <SiteShell
      eyebrow="Simulator"
      title="Run replay-defense scenarios in the browser."
      intro="The simulator uses the Python API when available and falls back to a browser-side demo model on static GitHub Pages. Authoritative research runs still belong to the Python core."
      shellCopy={{
        eyebrow: {
          en: 'Simulator',
          ja: 'シミュレータ',
          zh: '模拟器',
        },
        title: {
          en: 'Run replay-defense scenarios in the browser.',
          ja: 'ブラウザでリプレイ防御シナリオを実行。',
          zh: '在浏览器中运行重放防御场景。',
        },
        intro: {
          en: 'The simulator uses the Python API when available and falls back to a browser-side demo model on static GitHub Pages. Authoritative research runs still belong to the Python core.',
          ja: 'Python API が利用可能な場合はそれを使い、静的な GitHub Pages ではブラウザ内のデモモデルに切り替わります。研究用の正式な実行結果は引き続き Python コアを基準にします。',
          zh: '模拟器会在可用时调用 Python API；在静态 GitHub Pages 上则自动切换为浏览器端演示模型。正式研究结果仍以 Python 核心为准。',
        },
      }}
    >
      <SimulatorPageContent />
    </SiteShell>
  );
}
