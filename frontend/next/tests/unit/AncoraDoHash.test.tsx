import { afterEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { AncoraDoHash } from "@/components/nav/AncoraDoHash";

vi.mock("next/navigation", () => ({ usePathname: () => "/glossario" }));

describe("AncoraDoHash (#257)", () => {
  afterEach(() => { window.location.hash = ""; document.body.innerHTML = ""; });
  it("rola para o alvo do hash ao montar", () => {
    const alvo = document.createElement("div"); alvo.id = "stake"; document.body.append(alvo);
    alvo.scrollIntoView = vi.fn();
    window.location.hash = "#stake";
    render(<AncoraDoHash />);
    expect(alvo.scrollIntoView).toHaveBeenCalledWith({ block: "start" });
  });
  it("sem hash nao rola; hashchange na mesma rota rola de novo", () => {
    const alvo = document.createElement("div"); alvo.id = "edge"; document.body.append(alvo);
    alvo.scrollIntoView = vi.fn();
    render(<AncoraDoHash />);
    expect(alvo.scrollIntoView).not.toHaveBeenCalled();
    window.location.hash = "#edge";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    expect(alvo.scrollIntoView).toHaveBeenCalledTimes(1);
  });
});
