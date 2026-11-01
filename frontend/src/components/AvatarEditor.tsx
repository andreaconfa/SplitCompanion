import { t, translateMessage } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Session, User } from "../api/types";
import { api } from "../api/client";
import { useData } from "./context";
import { UserPhoto } from "./Person";
import { avatarFileError } from "../utils/people";
export function AvatarEditor({ user: original }: { user: User }) {
  useLanguage();
  const { users } = useData();
  const user = users.find(value => value.id === original.id) ?? original;
  const cache = useQueryClient();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const action = useMutation({
    mutationFn: async (file: File | null) => {
      const body = file ? new FormData() : undefined;
      if (file) body!.append("file", file);
      return api<User>(`/users/${user.id}/avatar`, { method: file ? "POST" : "DELETE", body });
    },
    onSuccess: (updated, file) => {
      cache.setQueryData<User[]>(["/users"], current => current?.map(value => value.id === updated.id ? updated : value));
      cache.setQueryData<Session>(["/auth/me"], current => current?.user.id === updated.id ? { ...current, user: updated } : current);
      void cache.invalidateQueries({ queryKey: ["/users"] });
      void cache.invalidateQueries({ queryKey: ["/auth/me"] });
      setNotice(file ? t("Foto aggiornata.") : t("Foto rimossa."));
    },
    onError: (failure) => setError(failure instanceof Error ? failure.message : t("Non è stato possibile aggiornare la foto.")),
  });
  return <div className="avatar-editor">
    <div className="avatar-editor-preview"><UserPhoto user={user} /><strong>{t("Foto di")}{" "}{user.display_name}</strong></div>
    <div className="avatar-editor-actions">
      <label className="btn btn-secondary avatar-file-label" aria-disabled={action.isPending}>
        {user.avatar_version ? t("Sostituisci foto") : t("Carica foto")}
        <input className="avatar-file-input" type="file" accept="image/png,image/jpeg,image/webp" aria-label={t("Scegli la foto di {0}", {0: user.display_name})} disabled={action.isPending} onChange={event => {
          const file = event.target.files?.[0]; event.target.value = "";
          if (!file) return;
          setNotice(""); const failure = avatarFileError(file); setError(failure);
          if (!failure) action.mutate(file);
        }} />
      </label>
      {user.avatar_version && <button type="button" className="btn btn-secondary" disabled={action.isPending} onClick={() => { setError(""); setNotice(""); action.mutate(null); }}>{t("Rimuovi foto")}</button>}
    </div>
    <small className="muted">{t("PNG, JPEG o WebP · massimo 2 MB e 2048 × 2048 pixel.")}</small>
    {action.isPending && <p role="status">{t("Aggiornamento della foto…")}</p>}
    {notice && <p role="status">{translateMessage(notice)}</p>}
    {error && <p className="notice error" role="alert">{translateMessage(error)}</p>}
  </div>;
}
