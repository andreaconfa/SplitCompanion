import { t } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useState } from "react";
import {
  Tag,
  ShoppingBasket,
  Utensils,
  House,
  Zap,
  Car,
  Plane,
  HeartPulse,
  PawPrint,
  Popcorn,
  ShoppingBag,
  Bot,
  GraduationCap,
  Gift,
  Dumbbell,
  Sparkles,
  Smartphone,
  ArrowLeftRight,
} from "lucide-react";
import { useApi, useAction, send } from "../api/client";
import type { Category, CategoryMetadata, IconCatalog } from "../api/types";
import { Button, ErrorBox } from "./ui";

const icons: Record<string, typeof Tag> = {
  tag: Tag,
  sparkles: Sparkles,
  smartphone: Smartphone,
  "arrow-left-right": ArrowLeftRight,
  "shopping-basket": ShoppingBasket,
  utensils: Utensils,
  house: House,
  zap: Zap,
  car: Car,
  plane: Plane,
  "heart-pulse": HeartPulse,
  "paw-print": PawPrint,
  popcorn: Popcorn,
  "shopping-bag": ShoppingBag,
  bot: Bot,
  "graduation-cap": GraduationCap,
  gift: Gift,
  dumbbell: Dumbbell,
};
export const iconNames: Record<string, string> = {
  tag: "Etichetta",
  sparkles: "Cura personale",
  smartphone: "Elettronica e accessori",
  "arrow-left-right": "Trasferimenti e rimborsi",
  "shopping-basket": "Spesa",
  utensils: "Ristorante",
  house: "Casa",
  zap: "Utenze",
  car: "Auto",
  plane: "Aereo",
  "heart-pulse": "Salute",
  "paw-print": "Animali",
  popcorn: "Svago",
  "shopping-bag": "Shopping",
  bot: "Software e AI",
  "graduation-cap": "Istruzione",
  gift: "Regalo",
  dumbbell: "Sport",
  chatgpt: "ChatGPT",
};
export function CategoryIcon({
  iconKey,
  size = 22,
}: {
  iconKey?: string | null;
  size?: number;
}) {
  useLanguage();
  if (iconKey === "chatgpt")
    return (
      <img
        className="category-image chatgpt-icon"
        src="/chatgpt.svg"
        width={size}
        height={size}
        alt="ChatGPT"
      />
    );
  if (iconKey?.startsWith("upload:"))
    return (
      <img
        className="category-image"
        src={`/api/icons/${iconKey.slice(7)}/image`}
        width={size}
        height={size}
        alt={t("Icona personalizzata")}
      />
    );
  const Icon = icons[iconKey ?? "tag"] ?? Tag;
  return <Icon size={size} aria-hidden="true" />;
}
export function CategoryBadge({
  value,
  label = false,
}: {
  value: CategoryMetadata;
  label?: boolean;
}) {
  useLanguage();
  const categories = useApi<Category[]>("/categories");
  const category = categories.data?.find((c) => c.id === value.category_id);
  return (
    <span
      className={label ? "category-badge" : "category-symbol"}
      title={category?.display_name ?? category?.name ?? t("Senza categoria")}
    >
      <CategoryIcon iconKey={category?.icon_key} />
      {label && <span>{category?.display_name ?? category?.name ?? t("Senza categoria")}</span>}
    </span>
  );
}
export function IconPicker({
  value,
  onChange,
  allowDefault = true,
}: {
  value: string | null;
  onChange: (key: string | null) => void;
  allowDefault?: boolean;
}) {
  useLanguage();
  const catalog = useApi<IconCatalog>("/icons");
  return (
    <label>{t("Icona")}<select
        aria-label={t("Icona")}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      >
        {allowDefault && <option value="">{t("Icona della categoria")}</option>}
        {Object.entries(iconNames).map(([key, name]) => (
          <option value={key} key={key}>
            {t(name)}
          </option>
        ))}
        {catalog.data?.custom.map((icon) => (
          <option value={icon.icon_key} key={icon.id}>
            {icon.name}
          </option>
        ))}
      </select>
      <ErrorBox error={catalog.error} />
    </label>
  );
}
export function CategoryPicker({
  value,
  onChange,
}: {
  value: CategoryMetadata;
  onChange: (value: CategoryMetadata) => void;
}) {
  useLanguage();
  const categories = useApi<Category[]>("/categories");
  return (
    <div className="category-picker">
      <div>
        <label>{t("Categoria")}<select
            aria-label={t("Categoria")}
            value={value.category_id ?? ""}
            onChange={(e) =>
              onChange({
                category_id: e.target.value ? Number(e.target.value) : null,
              })
            }
          >
            <option value="">{t("Senza categoria")}</option>
            {categories.data?.map((c) => (
              <option value={c.id} key={c.id}>
                {c.display_name ?? c.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="category-preview">
        <CategoryBadge value={value} label />
        <span className="muted">{t("Icona automatica dalla categoria")}</span>
      </div>
      <ErrorBox error={categories.error} />
    </div>
  );
}
export function CategoryEditor({
  value,
  path,
}: {
  value: CategoryMetadata;
  path: string;
}) {
  useLanguage();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<CategoryMetadata>({
    category_id: value.category_id ?? null,
  });
  const save = useAction(() => send(path + "/category", "PATCH", draft));
  return (
    <div className="card form-card">
      <div className="category-preview">
        <CategoryBadge value={value} label />
        <Button
          variant="secondary"
          onClick={() => {
            setDraft({
              category_id: value.category_id ?? null,
            });
            setOpen(!open);
          }}
        >
          {open ? t("Annulla") : t("Modifica categoria")}
        </Button>
      </div>
      {open && (
        <>
          <CategoryPicker value={draft} onChange={setDraft} />
          <p className="muted">{t("La categoria non modifica importi, quote o dati originali.")}</p>
          <ErrorBox error={save.error} />
          <Button
            disabled={save.isPending}
            onClick={async () => {
              try {
                await save.mutateAsync(undefined);
                setOpen(false);
              } catch {
                /* rendered */
              }
            }}
          >{t("Salva categoria")}</Button>
        </>
      )}
    </div>
  );
}
