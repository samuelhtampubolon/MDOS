/* Guards the interface rules in docs/18-interface-brief.md: depth from borders only, one radius token. */

import { describe, expect, it } from "vitest";

const raw = import.meta.glob(["../**/*.css", "../**/*.tsx"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const sources = Object.entries(raw).map(([file, text]) => ({ file, text: text.replace(/\/\*[\s\S]*?\*\//g, "") }));

describe("interface rules", () => {
  it("reads the style and component sources", () => {
    expect(sources.some(({ file }) => file.endsWith("components.css"))).toBe(true);
  });

  it("uses no shadows, gradients or scale transforms", () => {
    const offenders = sources.filter(({ text }) => /box-shadow|boxShadow|linear-gradient|radial-gradient|scale\(/.test(text));
    expect(offenders.map(({ file }) => file)).toEqual([]);
  });

  it("uses the radius tokens instead of fixed radii on surfaces", () => {
    const css = sources.filter(({ file }) => file.endsWith("components.css"));
    const values = css.flatMap(({ text }) => [...text.matchAll(/border-radius:\s*([^;]+);/g)].map((m) => m[1].trim()));
    const fixed = values.filter((v) => !v.startsWith("var(--radius") && v !== "50%" && v !== "2px"); // circles and 2 px marks
    expect(fixed).toEqual([]);
  });
});
