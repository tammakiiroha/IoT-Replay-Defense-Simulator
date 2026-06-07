'use client';

import { useLocale } from './locale-context';
import { Panel } from './site-shell';
import { SimulatorPanel } from './simulator-panel';

const COPY = {
  en: {
    title: 'Interactive control surface',
    description:
      'Run the Python API when it is available. On GitHub Pages, the same form falls back to a browser-side demo model so the simulator remains usable.',
  },
  ja: {
    title: 'インタラクティブ操作パネル',
    description:
      'Python API が利用可能な場合はそれを使用します。GitHub Pages ではブラウザ内のデモモデルに切り替わるため、シミュレータをそのまま試せます。',
  },
  zh: {
    title: '交互式控制面板',
    description:
      '可用时优先调用 Python API。在 GitHub Pages 上会自动切换到浏览器端演示模型，因此模拟器可以直接运行。',
  },
};

export function SimulatorPageContent() {
  const { locale } = useLocale();
  const copy = COPY[locale];
  return (
    <Panel title={copy.title} description={copy.description}>
      <SimulatorPanel />
    </Panel>
  );
}
