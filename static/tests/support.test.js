import { beforeEach, describe, expect, it, vi } from "vitest";
import fs from "node:fs";

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, "utf8");
  window.eval(`${code}\n//# sourceURL=${relativePath}`);
}

describe("support UI", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = `
      <button id="export" type="button"></button>
      <input id="req">
      <button id="lookup" type="button"></button>
      <div id="meta"></div>
      <table id="events"><tbody></tbody></table>
      <table id="logs"><tbody></tbody></table>
    `;
  });

  it("loads the support endpoint, renders untrusted values as text, and refreshes without duplicates", async () => {
    const payload = {
      service_version: "test",
      deploy_env: "testing",
      now: "2026-01-01T00:00:00Z",
      events: [["<img src=x>", 1]],
      recent_warnings: [{
        ts: 0,
        level: "WARN",
        path: "/<b>path</b>",
        request_id: "id\"><img src=x>",
        msg: "<script>alert(1)</script>",
      }],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(payload),
    });
    globalThis.alert = vi.fn();
    URL.createObjectURL = vi.fn(() => "blob:test");
    URL.revokeObjectURL = vi.fn();

    loadScript("../../static/js/support.js");
    await Promise.resolve();
    await Promise.resolve();

    expect(fetch).toHaveBeenCalledWith("/admin/support/");
    expect(document.querySelectorAll("#events tbody tr")).toHaveLength(1);
    expect(document.querySelectorAll("#logs tbody tr")).toHaveLength(1);
    expect(document.querySelector("#events img")).toBeNull();
    expect(document.querySelector("#logs img")).toBeNull();
    expect(document.querySelector("#logs script")).toBeNull();
    expect(document.querySelector("#logs td:last-child").textContent).toBe(
      "<script>alert(1)</script>",
    );

    await vi.advanceTimersByTimeAsync(15000);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(document.querySelectorAll("#events tbody tr")).toHaveLength(1);
    expect(document.querySelectorAll("#logs tbody tr")).toHaveLength(1);

    document.getElementById("req").value = "synthetic-request-id";
    document.getElementById("lookup").click();
    await Promise.resolve();
    await Promise.resolve();
    expect(fetch).toHaveBeenLastCalledWith(
      "/admin/support/lookup?request_id=synthetic-request-id",
    );

    document.getElementById("export").click();
    await Promise.resolve();
    await Promise.resolve();
    expect(fetch).toHaveBeenLastCalledWith("/admin/support/");
  });
});
