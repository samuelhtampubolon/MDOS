import { describe, expect, it } from "vitest";
import mainPy from "../../../backend/mdos/main.py?raw";
import { SECURITY_HEADERS, backendOrigin } from "../../scripts/static-host.mjs";

/** Joins the string literals of a module-level Python constant, which may continue over indented lines. */
function pythonConstant(source: string, name: string): string {
  const start = source.indexOf(`\n${name} = `);
  const next = source.slice(start + 1).search(/\n\S/);
  const statement = source.slice(start + 1, start + 1 + next);
  return [...statement.matchAll(/"([^"]*)"/g)].map((m) => m[1]).join("");
}

describe("static hosts in front of the MDOS backend", () => {
  it("send the same Content Security Policy and Permissions-Policy as the server", () => {
    expect(SECURITY_HEADERS["Content-Security-Policy"]).toBe(pythonConstant(mainPy, "APP_CSP"));
    expect(SECURITY_HEADERS["Permissions-Policy"]).toBe(pythonConstant(mainPy, "PERMISSIONS_POLICY"));
  });

  it("only proxy to a plain https origin", () => {
    expect(backendOrigin("https://demo.hf.space")).toBe("https://demo.hf.space");
    for (const bad of ["http://demo.hf.space", "https://u:p@demo.hf.space", "https://demo.hf.space/x", "", undefined]) {
      expect(() => backendOrigin(bad)).toThrow();
    }
  });
});
