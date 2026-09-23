import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { EsqueletoCard } from "@/components/feed/EsqueletoCard";
describe("EsqueletoCard (#262, spec §3)", () => {
  it("e decorativo, usa a superficie sb-card e quatro blocos", () => {
    const { container } = render(<EsqueletoCard />);
    const raiz = container.firstElementChild!;
    expect(raiz).toHaveAttribute("aria-hidden", "true");
    expect(raiz.className).toContain("sb-card");
    expect(raiz.querySelectorAll(".sb-esqueleto")).toHaveLength(4);
  });
});
