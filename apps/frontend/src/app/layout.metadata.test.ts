import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

describe("root layout metadata", () => {
  it("uses OMAROSA MCC global title branding", () => {
    const layoutPath = path.resolve(process.cwd(), "src/app/layout.tsx");
    const source = readFileSync(layoutPath, "utf8");
    expect(source).toContain('title: "OMAROSA MCC"');
  });

  it("mounts GlobalAgencyFavicon in root layout so landing and interior share the same favicon logic", () => {
    const layoutPath = path.resolve(process.cwd(), "src/app/layout.tsx");
    const source = readFileSync(layoutPath, "utf8");
    expect(source).toContain("<GlobalAgencyFavicon />");
  });
});
