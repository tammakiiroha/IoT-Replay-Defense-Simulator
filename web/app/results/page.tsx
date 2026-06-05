import { ResultsOverview } from '../../components/results-overview';
import { SiteShell } from '../../components/site-shell';

export default function ResultsPage() {
  return (
    <SiteShell
      eyebrow="Results"
      title="Charts are artifacts, not screenshots of a toy UI."
      intro="The public site reads versioned JSON artifacts and reference figures generated from the research workflow. That keeps the showcase aligned with the thesis evidence chain."
    >
      <ResultsOverview />
    </SiteShell>
  );
}
