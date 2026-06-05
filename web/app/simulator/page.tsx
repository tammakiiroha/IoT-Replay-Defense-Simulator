import { Panel, SiteShell } from '../../components/site-shell';
import { SimulatorPanel } from '../../components/simulator-panel';

export default function SimulatorPage() {
  return (
    <SiteShell
      eyebrow="Simulator"
      title="Interactive when local, honest when static."
      intro="This page only submits work to the authoritative API. In public static mode it will show the boundary clearly instead of silently forking the simulation logic in JavaScript."
    >
      <Panel
        title="Interactive control surface"
        description="Run the same Python implementation used by the CLI, the API, the sweep scripts, and the physical-validation comparison."
      >
        <SimulatorPanel />
      </Panel>
    </SiteShell>
  );
}
