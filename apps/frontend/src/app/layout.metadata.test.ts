import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

describe("root layout metadata", () => {
  it("uses VOXEL MCC global title branding", () => {
    const layoutPath = path.resolve(process.cwd(), "src/app/layout.tsx");
    const source = readFileSync(layoutPath, "utf8");
    expect(source).toContain('title: "VOXEL MCC"');
  });
});
