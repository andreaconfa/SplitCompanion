import { t } from "../i18n";
export function pushSupport(secure: boolean, available: boolean, permission: NotificationPermission) {
  if (!secure) return t("Apri Split Companion tramite HTTPS per attivare le notifiche.");
  if (!available) return t("Questo browser non supporta le notifiche push. Su iPhone o iPad (iOS 16.4+) aggiungi prima l’app alla schermata Home.");
  if (permission === 'denied') return t("Notifiche bloccate: consenti le notifiche nelle impostazioni del browser o del dispositivo.");
  return '';
}
export function applicationKey(value: string): Uint8Array<ArrayBuffer> {
  const decoded = atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4));
  return Uint8Array.from(decoded, c => c.charCodeAt(0));
}
