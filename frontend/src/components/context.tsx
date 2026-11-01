import { t } from "../i18n";
import { createContext, useContext } from "react";
import type { Session, User, Group } from "../api/types";
export const SessionContext = createContext<{
  session: Session;
  logout: () => Promise<void>;
  invalidate: (message: string) => void;
} | null>(null);
export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error(t("Sessione mancante"));
  return context;
}
export const DataContext = createContext<{ users: User[]; groups: Group[] }>({
  users: [],
  groups: [],
});
export const useData = () => useContext(DataContext);
