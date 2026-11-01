import { useState, type FormEvent } from "react";
import {
  Upload,
  Check,
  ArrowRight,
  Undo2,
  FileJson,
  ArrowLeft,
  AlertCircle,
} from "lucide-react";
import { useApi, useAction, api, send } from "../api/client";
import type { Batch, Preview, Mapping } from "../api/types";
import { useData, useSession } from "../components/context";
import {
  PageHead,
  Section,
  State,
  Empty,
  Button,
  ErrorBox,
  Busy,
  Money,
} from "../components/ui";
import { dateLabel } from "../utils/money";
const statusLabel = (status: string) =>
  (
    ({
      ANALYZED: "Analizzato",
      MAPPED: "Mappato",
      COMPLETED: "Completato",
      ROLLED_BACK: "Annullato",
    }) as Record<string, string>
  )[status] ?? status;
const recordKind = (kind: string) =>
  (
    ({
      EXPENSE: "Spesa",
      SETTLEMENT: "Pagamento",
      LEGACY: "Movimento storico",
    }) as Record<string, string>
  )[kind] ?? kind;
interface MapUser {
  selection: string;
  username: string;
  display_name: string;
  password: string;
}
export default function Imports() {
  const { session } = useSession();
  const { users, groups } = useData();
  const batches = useApi<Batch[]>("/imports", session.user.is_admin);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [step, setStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [userMap, setUserMap] = useState<Record<string, MapUser>>({});
  const [groupMap, setGroupMap] = useState<
    Record<string, { selection: string; name: string }>
  >({});
  const analyze = useAction(async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Batch>("/imports/splitwise/analyze", {
      method: "POST",
      body: form,
    });
  });
  const mapping = useAction(async (body: Mapping) =>
    send("/imports/splitwise/" + batch!.id + "/mapping", "POST", body),
  );
  const commit = useAction(async () =>
    send("/imports/splitwise/" + batch!.id + "/commit", "POST"),
  );
  const rollback = useAction(async (id: number) =>
    send("/imports/" + id + "?confirm=true", "DELETE"),
  );
  const open = (value: Batch) => {
    setBatch(value);
    setPreview(null);
    setError("");
    setUserMap(
      Object.fromEntries(
        (value.people ?? []).map((person) => {
          const mapped = value.mapping?.users?.[person];
          const match = users.find(
            (u) =>
              u.display_name.toLowerCase() === person.toLowerCase() ||
              u.username.toLowerCase() === person.toLowerCase(),
          );
          return [
            person,
            {
              selection:
                typeof mapped === "number"
                  ? String(mapped)
                  : mapped === null
                    ? "skip"
                    : mapped && typeof mapped === "object"
                      ? "new"
                      : match
                        ? String(match.id)
                        : "new",
              username:
                mapped && typeof mapped === "object"
                  ? mapped.username
                  : person
                      .toLowerCase()
                      .normalize("NFKD")
                      .replace(/[\u0300-\u036f]/g, "")
                      .replace(/[^a-z0-9_.-]/g, "_"),
              display_name:
                mapped && typeof mapped === "object"
                  ? mapped.display_name
                  : person,
              password: "",
            },
          ];
        }),
      ),
    );
    setGroupMap(
      Object.fromEntries(
        (value.groups ?? []).map((name) => {
          const mapped = value.mapping?.groups?.[name];
          const match = groups.find(
            (g) => g.name.toLowerCase() === name.toLowerCase(),
          );
          return [
            name,
            {
              selection:
                typeof mapped === "number"
                  ? String(mapped)
                  : match
                    ? String(match.id)
                    : "new",
              name: mapped && typeof mapped === "object" ? mapped.name : name,
            },
          ];
        }),
      ),
    );
    setStep(1);
  };
  const upload = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!file) {
      setError("Scegli un file CSV o JSON.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Il file supera il limite di 10 MB.");
      return;
    }
    try {
      const value = (await analyze.mutateAsync(file)) as Batch;
      open(value);
    } catch {
      /* rendered */
    }
  };
  const map = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const body: Mapping = { users: {}, groups: {} };
    for (const [name, value] of Object.entries(userMap)) {
      body.users[name] =
        value.selection === "skip"
          ? null
          : value.selection === "new"
            ? {
                username: value.username.trim(),
                display_name: value.display_name.trim(),
                password: value.password,
              }
            : Number(value.selection);
    }
    for (const [name, value] of Object.entries(groupMap)) {
      body.groups[name] =
        value.selection === "new"
          ? { name: value.name.trim() }
          : Number(value.selection);
    }
    try {
      await mapping.mutateAsync(body);
      const value = await api<Preview>(
        "/imports/splitwise/" + batch!.id + "/preview",
      );
      setPreview(value);
      setStep(2);
    } catch {
      /* rendered */
    }
  };
  if (!session.user.is_admin)
    return <ErrorBox error="Questa pagina è riservata agli amministratori." />;
  return (
    <>
      <PageHead
        eyebrow="AMMINISTRAZIONE"
        title="Un nuovo inizio, con tutto lo storico."
        description="Porta le vostre spese da Splitwise, senza perdere i conti."
        back="/profile"
      />
      <div className="import-steps">
        {["File", "Persone", "Anteprima", "Fatto"].map((label, index) => (
          <div
            key={label}
            className={step === index ? "current" : step > index ? "done" : ""}
          >
            <span>{step > index ? <Check size={15} /> : index + 1}</span>
            <strong>{label}</strong>
          </div>
        ))}
      </div>
      <ErrorBox
        error={
          error ||
          analyze.error ||
          mapping.error ||
          commit.error ||
          rollback.error
        }
      />
      {step === 0 && (
        <form className="card import-upload form-card" onSubmit={upload}>
          <div className="upload-illustration">
            <FileJson size={42} />
            <span>
              <Upload size={19} />
            </span>
          </div>
          <h2>Il passato viene con voi.</h2>
          <p className="muted">
            Carica l’esportazione CSV o JSON di Splitwise. Prima di salvare
            vedrai un’anteprima completa.
          </p>
          <label className="file-label">
            Scegli il file
            <input
              type="file"
              accept=".csv,.json,text/csv,application/json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>
          <small className="muted">CSV / JSON · Fino a 10 MB</small>
          <Busy busy={analyze.isPending} label="Analizza file" />
        </form>
      )}
      {step === 1 && batch && (
        <form onSubmit={map}>
          <div className="notice">
            <FileJson size={19} />
            <div>
              <strong>{batch.original_filename}</strong>
              <p>
                {batch.records_total} record trovati. Associa ogni persona e
                gruppo all’installazione locale.
              </p>
            </div>
          </div>
          <Messages errors={batch.errors} warnings={batch.warnings} />
          <Section title="Chi sono le persone?">
            <div className="mapping-cards">
              {Object.entries(userMap).map(([external, value]) => (
                <div className="card form-card" key={external}>
                  <h3>{external}</h3>
                  <label>
                    Associa a
                    <select
                      value={value.selection}
                      onChange={(e) =>
                        setUserMap({
                          ...userMap,
                          [external]: { ...value, selection: e.target.value },
                        })
                      }
                    >
                      <option value="new">Crea nuovo utente</option>
                      <option value="skip">
                        Ignora solo se quota e saldo sono zero
                      </option>
                      {users.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.display_name} · @{u.username}
                        </option>
                      ))}
                    </select>
                  </label>
                  {value.selection === "new" && (
                    <>
                      <div className="two-fields">
                        <label>
                          Username
                          <input
                            required
                            pattern="[a-zA-Z0-9_.-]+"
                            value={value.username}
                            onChange={(e) =>
                              setUserMap({
                                ...userMap,
                                [external]: {
                                  ...value,
                                  username: e.target.value,
                                },
                              })
                            }
                          />
                        </label>
                        <label>
                          Nome
                          <input
                            required
                            value={value.display_name}
                            onChange={(e) =>
                              setUserMap({
                                ...userMap,
                                [external]: {
                                  ...value,
                                  display_name: e.target.value,
                                },
                              })
                            }
                          />
                        </label>
                      </div>
                      <label>
                        Password iniziale
                        <input
                          type="password"
                          autoComplete="new-password"
                          required
                          minLength={10}
                          value={value.password}
                          onChange={(e) =>
                            setUserMap({
                              ...userMap,
                              [external]: {
                                ...value,
                                password: e.target.value,
                              },
                            })
                          }
                        />
                      </label>
                    </>
                  )}
                </div>
              ))}
            </div>
          </Section>
          <Section title="Dove vanno i gruppi?">
            <div className="mapping-cards">
              {Object.entries(groupMap).map(([external, value]) => (
                <div className="card form-card" key={external}>
                  <h3>{external}</h3>
                  <label>
                    Associa a
                    <select
                      value={value.selection}
                      onChange={(e) =>
                        setGroupMap({
                          ...groupMap,
                          [external]: { ...value, selection: e.target.value },
                        })
                      }
                    >
                      <option value="new">Crea nuovo gruppo</option>
                      {groups.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {value.selection === "new" && (
                    <label>
                      Nome del gruppo
                      <input
                        required
                        value={value.name}
                        onChange={(e) =>
                          setGroupMap({
                            ...groupMap,
                            [external]: { ...value, name: e.target.value },
                          })
                        }
                      />
                    </label>
                  )}
                </div>
              ))}
            </div>
          </Section>
          <div className="form-footer">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setStep(0)}
            >
              <ArrowLeft size={16} /> Cambia file
            </Button>
            <Busy busy={mapping.isPending} label="Controlla anteprima" />
          </div>
        </form>
      )}
      {step === 2 && preview && batch && (
        <>
          <div className="import-stats">
            <div className="card">
              <strong>{preview.importable}</strong>
              <span>Importabili</span>
            </div>
            <div className="card">
              <strong>{preview.duplicates}</strong>
              <span>Duplicati saltati</span>
            </div>
            <div className="card">
              <strong>{preview.errors?.length ?? 0}</strong>
              <span>Segnalazioni</span>
            </div>
          </div>
          <Messages errors={preview.errors} warnings={preview.warnings} />
          <Section title="Effetto sui saldi">
            <div className="card">
              {preview.balance_deltas?.length ? (
                preview.balance_deltas.map((delta, index) => (
                  <div key={index} className="list-row">
                    <div className="row-main">
                      <strong>{delta.user}</strong>
                      <span>{delta.group}</span>
                    </div>
                    <Money
                      value={delta.amount_cents}
                      currency={delta.currency}
                      signed
                    />
                  </div>
                ))
              ) : (
                <Empty title="Nessuna variazione dei saldi" />
              )}
            </div>
          </Section>
          <Section title="Movimenti da importare">
            <div className="card">
              {preview.records?.map((record, index) => (
                <details className="preview-record" key={index}>
                  <summary>
                    <div>
                      <strong>{record.description}</strong>
                      <span>
                        {record.group} · {dateLabel(record.date)} ·{" "}
                        {recordKind(record.kind)}
                      </span>
                    </div>
                    <Money
                      value={record.amount_cents}
                      currency={record.currency}
                    />
                  </summary>
                  <div className="preview-deltas">
                    {Object.entries(record.deltas ?? {}).map(
                      ([person, amount]) => (
                        <div key={person}>
                          <span>{person}</span>
                          <Money
                            value={amount}
                            currency={record.currency}
                            signed
                          />
                        </div>
                      ),
                    )}
                  </div>
                </details>
              ))}
            </div>
          </Section>
          <p className="notice">
            Solo la conferma salva i movimenti. I duplicati vengono esclusi. Gli
            eventuali record non importabili sono elencati nelle segnalazioni.
          </p>
          <div className="form-footer">
            <Button variant="secondary" onClick={() => setStep(1)}>
              <ArrowLeft size={16} /> Modifica mappatura
            </Button>
            <Button
              disabled={commit.isPending || preview.importable <= 0}
              onClick={async () => {
                try {
                  const result = (await commit.mutateAsync(undefined)) as Batch;
                  setBatch(result);
                  setStep(3);
                } catch {
                  /* rendered */
                }
              }}
            >
              {commit.isPending ? "Importazione…" : "Conferma importazione"}{" "}
              <ArrowRight size={16} />
            </Button>
          </div>
        </>
      )}
      {step === 3 && batch && (
        <div className="card import-success">
          <span className="success-icon">
            <Check size={32} />
          </span>
          <h2>Lo storico è a casa.</h2>
          <p>
            {batch.records_imported} record importati · {batch.records_skipped}{" "}
            saltati · {batch.records_failed} non importati
          </p>
          <Messages errors={batch.errors} warnings={batch.warnings} />
          <Button
            onClick={() => {
              setStep(0);
              setBatch(null);
              setPreview(null);
              setFile(null);
            }}
          >
            Importa un altro file
          </Button>
        </div>
      )}
      <Section title="Importazioni precedenti">
        <State pending={batches.isPending} error={batches.error}>
          <div className="card">
            {batches.data?.length ? (
              batches.data.map((item) => (
                <div className="import-history-row" key={item.id}>
                  <div className="row-main">
                    <strong>{item.original_filename}</strong>
                    <span>
                      {dateLabel(item.created_at.slice(0, 10))} ·{" "}
                      {statusLabel(item.status)}
                    </span>
                    <small>
                      {item.records_imported} importati / {item.records_total}{" "}
                      totali · {item.records_skipped} saltati ·{" "}
                      {item.records_failed} errori
                    </small>
                  </div>
                  <div className="row-actions">
                    {![
                      "completed",
                      "committed",
                      "rolled_back",
                      "imported",
                    ].includes(item.status.toLowerCase()) && (
                      <Button variant="secondary" onClick={() => open(item)}>
                        Riprendi
                      </Button>
                    )}
                    {["completed", "committed", "imported"].includes(
                      item.status.toLowerCase(),
                    ) && (
                      <Button
                        variant="danger"
                        disabled={rollback.isPending}
                        onClick={() => {
                          if (
                            confirm(
                              `Annullare l’importazione «${item.original_filename}»? Verranno rimossi solo i movimenti di questo import e i saldi saranno ricalcolati.`,
                            )
                          )
                            rollback.mutate(item.id, {
                              onSuccess: () => {
                                if (batch?.id === item.id) {
                                  setStep(0);
                                  setBatch(null);
                                }
                              },
                            });
                        }}
                      >
                        <Undo2 size={16} /> Annulla import
                      </Button>
                    )}
                  </div>
                  {item.errors?.length > 0 && (
                    <details>
                      <summary>Segnalazioni</summary>
                      <Messages errors={item.errors} warnings={item.warnings} />
                    </details>
                  )}
                </div>
              ))
            ) : (
              <Empty title="Nessuna importazione precedente" />
            )}
          </div>
        </State>
      </Section>
    </>
  );
}
function Messages({
  errors = [],
  warnings = [],
}: {
  errors?: string[];
  warnings?: string[];
}) {
  return (
    <>
      {errors.length > 0 && (
        <div className="notice error">
          <AlertCircle size={18} />
          <div>
            <strong>Controlla queste segnalazioni</strong>
            <ul>
              {errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {warnings.length > 0 && (
        <div className="notice warning">
          <div>
            <strong>Da sapere prima di proseguire</strong>
            <ul>
              {warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
