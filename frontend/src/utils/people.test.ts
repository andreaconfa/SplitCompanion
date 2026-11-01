import { afterEach, describe, expect, it, vi } from "vitest";
import { avatarFileError, avatarURL, choosePeopleDisplay, initials, PEOPLE_DISPLAY_KEY, peopleDisplay } from "./people";
afterEach(() => vi.unstubAllGlobals());
describe("people presentation", () => {
  it("uses readable initials when a photo is absent", () => {
    expect(initials("  Alex   Demo ")).toBe("AD");
    expect(initials("Élodie")).toBe("É");
    expect(initials(" ")).toBe("?");
  });
  it("fetches photos only for accounts with a version and busts stale images", () => {
    expect(avatarURL(1, null)).toBeNull();
    expect(avatarURL(2, "2026-10-31T12:00+01:00")).toBe("/api/users/2/avatar?v=2026-10-31T12%3A00%2B01%3A00");
  });
  it("persists each mode locally and notifies existing views", () => {
    const saved = new Map<string, string>();
    const events = new EventTarget(); const changed = vi.fn();
    events.addEventListener("people-display-change", changed);
    vi.stubGlobal("window", events);
    vi.stubGlobal("localStorage", { getItem: (key: string) => saved.get(key) ?? null, setItem: (key: string, value: string) => saved.set(key, value) });
    expect(peopleDisplay()).toBe("both");
    for (const mode of ["photo", "name", "both"] as const) { choosePeopleDisplay(mode); expect(peopleDisplay()).toBe(mode); expect(saved.get(PEOPLE_DISPLAY_KEY)).toBe(mode); }
    expect(changed).toHaveBeenCalledTimes(3);
    saved.set(PEOPLE_DISPLAY_KEY, "bad-value"); expect(peopleDisplay()).toBe("both");
  });
  it("keeps working when local storage is unavailable", () => {
    vi.stubGlobal("window", new EventTarget());
    vi.stubGlobal("localStorage", { getItem: () => { throw Error(); }, setItem: () => { throw Error(); } });
    choosePeopleDisplay("name"); expect(peopleDisplay()).toBe("name");
  });
  it("rejects unsupported, empty and oversized files before upload", () => {
    expect(avatarFileError({ type: "image/svg+xml", size: 100 })).not.toBe("");
    expect(avatarFileError({ type: "image/png", size: 0 })).not.toBe("");
    expect(avatarFileError({ type: "image/jpeg", size: 2 * 1024 * 1024 + 1 })).not.toBe("");
    expect(avatarFileError({ type: "image/webp", size: 2 * 1024 * 1024 })).toBe("");
  });
});
