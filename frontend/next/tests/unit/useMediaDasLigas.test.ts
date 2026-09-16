import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useMediaDasLigas } from "@/hooks/useMediaDasLigas";

afterEach(() => vi.unstubAllGlobals());

describe("useMediaDasLigas (#256)", () => {
  it("calcula acertos/resolvidos do agregado da temporada", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      status: 200,
      json: () => Promise.resolve({ ok: true, periodo: "temporada", acerto: { picks: 100, acertos: 59, jogos: 90, resolvidos: 100 } }),
    }));
    const { result } = renderHook(() => useMediaDasLigas());
    await waitFor(() => expect(result.current).toBe(0.59));
  });
  it("resolvidos = 0: null, nunca divide por zero", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      status: 200,
      json: () => Promise.resolve({ ok: true, periodo: "temporada", acerto: { picks: 10, acertos: 0, jogos: 0, resolvidos: 0 } }),
    }));
    const { result } = renderHook(() => useMediaDasLigas());
    await waitFor(() => expect(result.current).toBeNull());
  });
  it("falha ou sem picks: null, nunca 0 ou NaN", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const { result } = renderHook(() => useMediaDasLigas());
    await waitFor(() => expect(result.current).toBeNull());
  });
});
