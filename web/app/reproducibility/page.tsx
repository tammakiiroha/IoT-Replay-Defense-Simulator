import { Panel, SiteShell } from '../../components/site-shell';

export default function ReproducibilityPage() {
  return (
    <SiteShell
      eyebrow="Reproducibility"
      title="Artifacts, commands, and evidence are now easier to audit."
      intro="This page frames the repository as a reproducible research product: static data for examiners, local authoritative runtime for deep verification, and explicit contracts between them."
    >
      <div className="grid gap-6 lg:grid-cols-3">
        <Panel title="Static data">
          <p className="text-sm leading-7 text-stone-700">
            `web/public/data/manifest.json` and versioned artifact files back the public Pages deployment.
          </p>
        </Panel>
        <Panel title="Local runtime">
          <p className="text-sm leading-7 text-stone-700">
            `start_app.sh` runs FastAPI plus Next.js so the site can submit authoritative simulations to the
            Python backend.
          </p>
        </Panel>
        <Panel title="Validation chain">
          <p className="text-sm leading-7 text-stone-700">
            Physical validation artifacts remain readable, but new normalized wrappers make them easier to
            compare and surface in the website.
          </p>
        </Panel>
      </div>
    </SiteShell>
  );
}
