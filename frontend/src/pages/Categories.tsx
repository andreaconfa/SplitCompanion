import { t } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useState, useRef, type FormEvent } from "react";
import { useApi, useAction, send, api } from "../api/client";
import type { Category } from "../api/types";
import { PageHead, State, Button, ErrorBox, Section } from "../components/ui";
import { CategoryIcon, IconPicker } from "../components/Categories";

export default function Categories() {
  useLanguage();
  const query = useApi<Category[]>("/categories");
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [icon, setIcon] = useState<string | null>("tag");
  const fileInput = useRef<HTMLInputElement>(null);
  const save = useAction(() => send(
    "/categories" + (editing ? "/" + editing : ""),
    editing ? "PATCH" : "POST", { name, icon_key: icon },
  ));
  const remove = useAction((id: number) => send("/categories/" + id, "DELETE"));
  const upload = useAction(async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const uploaded = await api<{ icon_key: string }>("/icons", { method: "POST", body });
    setIcon(uploaded.icon_key);
  });
  const reset = () => {
    setEditing(null);
    setName("");
    setIcon("tag");
    upload.reset();
    save.reset();
    if (fileInput.current) fileInput.current.value = "";
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (upload.isPending) return;
    try {
      await save.mutateAsync(undefined);
      reset();
    } catch { /* rendered */ }
  };
  const busy = save.isPending || upload.isPending;
  return <>
    <PageHead eyebrow={t("AMMINISTRAZIONE")} title={t("Categorie")}
      description={t("Un nome e un’icona per riconoscere ogni spesa. Le modifiche si applicano a tutti i movimenti della categoria.")}
      back="/profile" />
    <Section title={editing ? t("Modifica categoria") : t("Nuova categoria")}>
      <form className="card form-card" onSubmit={submit}>
        <label>{t("Nome categoria")}<input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200}
            disabled={busy} placeholder={t("Per esempio: Il nostro orto")} />
        </label>
        <fieldset disabled={busy} className="category-icon-fields">
          <IconPicker value={icon} onChange={setIcon} allowDefault={false} />
          <label>{t("Immagine personalizzata (opzionale)")}<input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp"
              onChange={(e) => { const file = e.target.files?.[0]; if (file) upload.mutate(file); }} />
          </label>
          <p className="muted">{t("PNG, JPEG o WebP, fino a 1 MB. L’immagine caricata viene selezionata automaticamente per questa categoria.")}</p>
        </fieldset>
        <div className="category-preview" aria-live="polite">
          <span className="category-badge"><CategoryIcon iconKey={icon} /><span>{name || t("Anteprima")}</span></span>
          {upload.isPending && <span className="muted">{t("Caricamento immagine…")}</span>}
        </div>
        <ErrorBox error={upload.error || save.error} />
        <div className="form-footer">
          {editing !== null && <Button type="button" variant="secondary" disabled={busy} onClick={reset}>{t("Annulla")}</Button>}
          <Button disabled={busy}>{t("Salva categoria")}</Button>
        </div>
      </form>
    </Section>
    <Section title={t("Le categorie")}>
      <State pending={query.isPending} error={query.error}>
        <div className="card">
          {query.data?.map((c) => <div className="list-row" key={c.id}>
            <span className="row-icon"><CategoryIcon iconKey={c.icon_key} /></span>
            <div className="row-main"><strong>{c.display_name ?? c.name}</strong><small>{c.slug ? t("Predefinita") : t("Personalizzata")}</small></div>
            <div className="category-actions">
              <Button variant="secondary" disabled={busy} onClick={() => {
                reset(); setEditing(c.id); setName(c.name); setIcon(c.icon_key);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}>{t("Modifica")}</Button>
              {!c.slug && <Button variant="danger" disabled={remove.isPending || busy} onClick={() => {
                if (confirm(t("Eliminare la categoria {0}?", {0: c.name}))) remove.mutate(c.id, {
                  onSuccess: () => { if (editing === c.id) reset(); },
                });
              }}>{t("Elimina")}</Button>}
            </div>
          </div>)}
        </div>
        <ErrorBox error={remove.error} />
      </State>
    </Section>
  </>;
}
