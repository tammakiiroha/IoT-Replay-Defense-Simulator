import type {
  ArtifactManifest,
  ExperimentArtifact,
  SimulationBatchResult,
  SimulationSpec,
} from './contracts';
import { runStaticSimulation } from './static-simulator';
import { apiBase, apiUrl, withBasePath } from './site';

async function fetchJson<T>(urls: string[]): Promise<T> {
  let lastError: unknown;
  for (const url of urls) {
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      return (await response.json()) as T;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error('Failed to fetch JSON resource');
}

export async function loadManifest(): Promise<ArtifactManifest> {
  return fetchJson<ArtifactManifest>([
    apiUrl('/api/v1/demo/manifest'),
    withBasePath('/data/manifest.json'),
  ]);
}

export async function loadArtifact(pathOrId: string): Promise<ExperimentArtifact> {
  const staticPath = pathOrId.startsWith('/data/')
    ? withBasePath(pathOrId)
    : withBasePath(`/data/artifacts/${pathOrId}.json`);
  const apiPath = pathOrId.startsWith('/data/')
    ? staticPath
    : apiUrl(`/api/v1/artifacts/${pathOrId}`);
  return fetchJson<ExperimentArtifact>([apiPath, staticPath]);
}

export async function runSimulation(spec: SimulationSpec): Promise<SimulationBatchResult> {
  try {
    const response = await fetch(apiUrl('/api/v1/simulations'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(spec),
    });

    if (response.ok) {
      return (await response.json()) as SimulationBatchResult;
    }

    if (apiBase) {
      const detail = await response.text();
      throw new Error(detail || `Simulation request failed with ${response.status}`);
    }
  } catch (error) {
    if (apiBase) {
      throw error;
    }
  }

  return runStaticSimulation(spec);
}
