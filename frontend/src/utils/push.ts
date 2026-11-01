export function pushSupport(secure: boolean, available: boolean, permission: NotificationPermission) {
  if (!secure) return 'Apri Split Companion tramite HTTPS per attivare le notifiche.';
  if (!available) return 'Questo browser non supporta le notifiche push. Su iPhone o iPad (iOS 16.4+) aggiungi prima l’app alla schermata Home.';
  if (permission === 'denied') return 'Notifiche bloccate: consenti le notifiche nelle impostazioni del browser o del dispositivo.';
  return '';
}
export function applicationKey(value: string): Uint8Array<ArrayBuffer> {
  const decoded = atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4));
  return Uint8Array.from(decoded, c => c.charCodeAt(0));
}
