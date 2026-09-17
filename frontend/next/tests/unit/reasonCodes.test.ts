import { describe, expect, it } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { motivoRecusa, INFORMATIVOS } from "@/lib/reasonCodes";

describe("reasonCodes (#258)", () => {
  it("bloqueante codes map to two-word motivos", () => {
    expect(motivoRecusa(["BORDERLINE_LINE_MARGIN"])).toBe("linha no limite");
    expect(motivoRecusa(["LINEUP_UNCERTAINTY"])).toBe("escalação incerta");
    expect(motivoRecusa(["VOLATILE_MARKET"])).toBe("mercado volátil");
    expect(motivoRecusa(["ANCHOR_STALE"])).toBe("âncora velha");
    expect(motivoRecusa(["NO_VALUE_REFERENCE"])).toBe("sem referência");
    expect(motivoRecusa(["BASE_RATE_ONLY"])).toBe("só taxa-base");
    expect(motivoRecusa(["MODEL_ONLY"])).toBe("só modelo");
    expect(motivoRecusa(["DIRECTION_NATURAL_NO_EV"])).toBe("sem valor");
  });

  it("first matching code wins (priority order)", () => {
    expect(motivoRecusa(["POSITIVE_EV", "BORDERLINE_LINE_MARGIN"])).toBe(
      "linha no limite"
    );
    expect(motivoRecusa(["HIGH_CALIBRATED_PROB", "STRONG_EDGE", "VOLATILE_MARKET"])).toBe(
      "mercado volátil"
    );
  });

  it("informational-only codes return default 'não vale'", () => {
    expect(motivoRecusa(["POSITIVE_EV"])).toBe("não vale");
    expect(motivoRecusa(["STRONG_EDGE"])).toBe("não vale");
    expect(motivoRecusa(["HIGH_CALIBRATED_PROB"])).toBe("não vale");
    expect(motivoRecusa(["STABLE_MARKET"])).toBe("não vale");
    expect(motivoRecusa(["ANCHOR_MARKET"])).toBe("não vale");
    expect(motivoRecusa(["DIRECTION_NATURAL_MATCH"])).toBe("não vale");
    expect(motivoRecusa(["POSITIVE_EV", "STRONG_EDGE", "HIGH_CALIBRATED_PROB"])).toBe(
      "não vale"
    );
  });

  it("empty list returns default 'não vale'", () => {
    expect(motivoRecusa([])).toBe("não vale");
  });

  it("real data: POSITIVE_EV+STRONG_EDGE+HIGH_CALIBRATED_PROB+BORDERLINE_LINE_MARGIN → 'linha no limite'", () => {
    expect(
      motivoRecusa([
        "POSITIVE_EV",
        "STRONG_EDGE",
        "HIGH_CALIBRATED_PROB",
        "BORDERLINE_LINE_MARGIN",
      ])
    ).toBe("linha no limite");
  });
});

describe("reasonCodes coverage (#258)", () => {
  it("every backend ReasonCode is either in MAPA or explicitly INFORMATIVOS", () => {
    // Read backend enum file (project structure: sportsbankzu-pro/backend and frontend/next)
    // From tests/unit: up to tests, up to next, up to frontend, up to sportsbankzu-pro, then backend
    const backendPath = resolve(__dirname, "../../../../backend/models/market_output.py");
    const content = readFileSync(backendPath, "utf8");

    // Extract ReasonCode class section
    const classMatch = /class ReasonCode\(str, Enum\):([\s\S]*?)(?=^class|\Z)/m.exec(
      content
    );
    if (!classMatch) {
      throw new Error("Could not find ReasonCode class in market_output.py");
    }

    const classContent = classMatch[1];

    // Extract all enum values: "NAME" = "NAME"
    const pattern = /^\s+(\w+)\s*=\s*"(\w+)"/gm;
    const codes = new Set<string>();
    let match;

    while ((match = pattern.exec(classContent)) !== null) {
      if (match[1] === match[2]) {
        // Verify name and value match
        codes.add(match[1]);
      }
    }

    // Verify we found codes
    expect(codes.size).toBeGreaterThan(0);

    // Build comprehensive map: MAPA + INFORMATIVOS
    const mapaSet = new Set(
      Array.from([
        "LOW_DATA_QUALITY",
        "DATA_MISSING",
        "EARLY_SEASON_FALLBACK",
        "NO_ODDS_AVAILABLE",
        "ODDS_TOO_LOW",
        "NEGATIVE_EV",
        "EV_FLOOR_DROP",
        "DIRECTION_NATURAL_NO_EV",
        "INSUFFICIENT_EDGE",
        "HIGH_MARKET_CORRELATION",
        "CORNER_ENGINE_NO_BET",
        "REGIME_BLOCKED",
        "SAFE_CIRCUIT_BREAKER",
        "HIGH_PREDICTION_RISK",
        "SUSPICIOUS_EV",
        "DIRECTION_AGAINST_PROJFT",
        "COVERAGE_INSUFFICIENT",
        "BORDERLINE_LINE_MARGIN",
        "LINEUP_UNCERTAINTY",
        "VOLATILE_MARKET",
        "ANCHOR_STALE",
        "NO_VALUE_REFERENCE",
        "BASE_RATE_ONLY",
        "MODEL_ONLY",
      ])
    );

    // Check coverage
    const missingCodes: string[] = [];
    for (const code of Array.from(codes)) {
      if (!mapaSet.has(code) && !INFORMATIVOS.has(code)) {
        missingCodes.push(code);
      }
    }

    if (missingCodes.length > 0) {
      throw new Error(
        `Unclassified codes (not in MAPA and not in INFORMATIVOS): ${missingCodes.join(", ")}`
      );
    }
    expect(missingCodes).toEqual([]);
  });
});
