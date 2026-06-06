import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const root = resolve(process.cwd());
const contractsPath = resolve(root, 'lib/contracts.ts');
const manifestPath = resolve(root, 'public/data/manifest.json');

const [contractsSource, manifestSource] = await Promise.all([
  readFile(contractsPath, 'utf8'),
  readFile(manifestPath, 'utf8'),
]);

if (!contractsSource.includes('SimulationSpec')) {
  throw new Error('contracts.ts is missing SimulationSpec');
}

if (!contractsSource.includes("'sw_resync'")) {
  throw new Error("contracts.ts Mode union is missing 'sw_resync'");
}

if (!contractsSource.includes('g_hard')) {
  throw new Error('contracts.ts is missing g_hard');
}

if (!contractsSource.includes('resync_initiated')) {
  throw new Error('contracts.ts is missing resync counters');
}

const manifest = JSON.parse(manifestSource);
if (!Array.isArray(manifest.artifacts) || manifest.artifacts.length === 0) {
  throw new Error('manifest.json does not contain any artifacts');
}

console.log('contracts-ok');
