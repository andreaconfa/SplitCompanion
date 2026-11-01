import { useId, useState, useSyncExternalStore } from "react";
import type { User } from "../api/types";
import { useData } from "./context";
import { avatarURL, choosePeopleDisplay, initials, PEOPLE_DISPLAY_KEY, peopleDisplay, type PeopleDisplay } from "../utils/people";
import "./Person.css";
function subscribe(callback: () => void) {
  const storage = (event: StorageEvent) => { if (event.key === PEOPLE_DISPLAY_KEY || event.key === null) callback(); };
  window.addEventListener("people-display-change", callback);
  window.addEventListener("storage", storage);
  return () => { window.removeEventListener("people-display-change", callback); window.removeEventListener("storage", storage); };
}
export function usePeopleDisplay() { return useSyncExternalStore(subscribe, peopleDisplay, () => "both" as const); }
export function UserPhoto({ user, name, small = false }: { user?: User; name?: string; small?: boolean }) {
  const label = user?.display_name ?? name ?? "Utente";
  const url = user ? avatarURL(user.id, user.avatar_version) : null;
  const [failed, setFailed] = useState<string | null>(null);
  return <span className={`avatar person-photo ${small ? "small" : "normal"}`} aria-hidden="true">
    {url && failed !== url ? <img src={url} alt="" loading="lazy" onError={() => setFailed(url)} /> : initials(label)}
  </span>;
}
export function Person({ userId, user: supplied, name, forceName = false, small = false }: { userId?: number; user?: User; name?: string; forceName?: boolean; small?: boolean }) {
  const { users } = useData();
  const user = users.find(value => value.id === (userId ?? supplied?.id)) ?? supplied;
  const label = user?.display_name ?? name ?? "Utente";
  const display = usePeopleDisplay();
  const photoOnly = display === "photo" && !forceName;
  return <span className={`person-identity person-identity-${display}`} title={label}>
    {display !== "name" && <UserPhoto user={user} name={label} small={small} />}
    <span className={photoOnly ? "person-accessible-name" : "person-name"}>{label}</span>
  </span>;
}
export function PeopleDisplaySelector() {
  const value = usePeopleDisplay(); const id = useId();
  const options: { value: PeopleDisplay; label: string }[] = [{ value: "both", label: "Nome e foto" }, { value: "name", label: "Solo nome" }, { value: "photo", label: "Solo foto" }];
  return <fieldset className="people-display-selector"><legend>Come mostrare le persone</legend>
    <div>{options.map(option => <label key={option.value}><input type="radio" name={`people-${id}`} checked={value === option.value} onChange={() => choosePeopleDisplay(option.value)} />{option.label}</label>)}</div>
    <small className="muted">Preferenza per questo dispositivo. Quando scegli paganti e quote, il nome rimane sempre visibile.</small>
  </fieldset>;
}
