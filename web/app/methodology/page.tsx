import { Panel, SiteShell } from '../../components/site-shell';

export default function MethodologyPage() {
  return (
    <SiteShell
      eyebrow="Methodology"
      title="Security, usability, and evidence live in one pipeline."
      intro="The platform now separates core simulation logic, typed contracts, application services, and presentation surfaces so the methodology is inspectable instead of being buried in ad hoc entrypoints."
    >
      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Core">
          <p className="text-sm leading-7 text-stone-700">
            Sender, receiver, attacker, channel, RNG, and experiment runner now sit behind the new
            `src/replay/core` package boundary.
          </p>
        </Panel>
        <Panel title="Contracts">
          <p className="text-sm leading-7 text-stone-700">
            API requests, sweep specs, simulation responses, and static artifacts are modeled with versioned
            Pydantic contracts that also generate the web type surface.
          </p>
        </Panel>
        <Panel title="Services">
          <p className="text-sm leading-7 text-stone-700">
            CLI, API, and artifact generation all call the same service layer, so presentation changes do not
            fork experiment behavior.
          </p>
        </Panel>
      </div>
    </SiteShell>
  );
}
