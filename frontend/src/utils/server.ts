import { getLanguage } from '../i18n';
export type ServerStatus = 'checking' | 'online' | 'offline';
export async function probeServer(signal: AbortSignal): Promise<Exclude<ServerStatus, 'checking'>> {
  try {
    const response = await fetch('/api/ready', { signal, headers: {'Accept-Language':getLanguage()}, cache: 'no-store', credentials: 'same-origin' });
    return response.ok && (await response.json()).status === 'ready' ? 'online' : 'offline';
  } catch { return 'offline'; }
}
