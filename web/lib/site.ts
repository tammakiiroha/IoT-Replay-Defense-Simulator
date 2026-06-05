const defaultBasePath =
  process.env.NODE_ENV === 'production' ? '/IoT-Replay-Defense-Simulator' : '';

export const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? defaultBasePath;
export const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? '';

export function withBasePath(path: string): string {
  if (!path.startsWith('/')) {
    return `${basePath}/${path}`;
  }
  return `${basePath}${path}`;
}

export function apiUrl(path: string): string {
  if (apiBase) {
    return `${apiBase}${path}`;
  }
  return withBasePath(path);
}
