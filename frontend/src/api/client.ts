import { getLanguage, t } from "../i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { configureTimezone } from "../utils/money";
let csrf = "";
export const setCsrf = (value: string) => {
  csrf = value;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (!navigator.onLine)
    throw new ApiError(
      t("Split Companion non è raggiungibile. Controlla la connessione alla rete."),
      0,
    );
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers);
  headers.set("Accept-Language", getLanguage());
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (method !== "GET") headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      ...options,
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      t("Split Companion non è raggiungibile. Controlla la connessione alla rete."),
      0,
    );
  }
  if (!response.ok) {
    let msg = t("Operazione non riuscita. Riprova.");
    try {
      const body = await response.json();
      msg =
        typeof body.detail === "string"
          ? body.detail
          : body.detail?.map((e: { msg: string }) => e.msg).join(". ") || msg;
    } catch {
      /* non JSON */
    }
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      path !== "/auth/me" &&
      path !== "/auth/password" &&
      !["/auth/mfa/setup", "/auth/mfa/confirm", "/auth/mfa/verify", "/auth/mfa/recovery-codes"].includes(path)
    )
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(msg, response.status);
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (["/auth/me", "/auth/login", "/auth/mfa/verify", "/auth/mfa/confirm"].includes(path)) {
    const session = path === "/auth/mfa/confirm" ? data.session : data;
    if (typeof session?.timezone === "string") configureTimezone(session.timezone);
    if (typeof session?.csrf_token === "string") setCsrf(session.csrf_token);
  }
  return data as T;
}
export function useApi<T>(path: string, enabled = true) {
  return useQuery<T>({
    queryKey: [path],
    queryFn: ({ signal }) => api<T>(path, { signal }),
    enabled,
    staleTime: 20_000,
    retry: (attempt, error) =>
      attempt < 1 &&
      !(error instanceof ApiError && [401, 403, 404].includes(error.status)),
    refetchOnWindowFocus: true,
  });
}
export function useAction<T = unknown>(action: (data: T) => Promise<unknown>) {
  const cache = useQueryClient();
  return useMutation({
    networkMode: "always",
    retry: false,
    mutationFn: action,
    onSuccess: () => {
      cache.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== "/auth/me",
      });
    },
  });
}
export const send = (path: string, method: string, body?: unknown) =>
  api(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
export function params(values: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  return search.size ? "?" + search.toString() : "";
}
