import { Panel, SiteShell } from '../../components/site-shell';

export default function HardwarePage() {
  return (
    <SiteShell
      eyebrow="Hardware"
      title="Physical validation is now a first-class product lane."
      intro="The HackRF and GNU Radio flowgraphs stay in the repository, but the web now explains them as part of the same product architecture instead of a sidecar folder."
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="What stays physical">
          <p className="text-sm leading-7 text-stone-700">
            Flowgraphs, device orchestration, and Linux/HackRF assumptions remain under
            `physical_experiment/flowgraphs` and `physical_experiment/scripts`.
          </p>
        </Panel>
        <Panel title="What becomes shared">
          <p className="text-sm leading-7 text-stone-700">
            Validation outputs, config snapshots, and sim-vs-hardware comparisons now feed the same artifact
            pipeline used by the showcase website.
          </p>
        </Panel>
      </div>
    </SiteShell>
  );
}
