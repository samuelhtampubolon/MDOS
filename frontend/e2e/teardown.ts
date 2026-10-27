/* Remove the temporary data folder created for this run, and nothing else. */

import { rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, resolve } from "node:path";

export default function teardown(): void {
  const dir = process.env.MDOS_E2E_DATA;
  if (!dir || process.env.MDOS_E2E_DATA_CREATED !== "1") return;
  const target = resolve(dir);
  if (dirname(target) !== resolve(tmpdir()) || !basename(target).startsWith("mdos-e2e-")) return;
  try {
    rmSync(target, { recursive: true, force: true });
  } catch (err) {
    console.warn(`Could not remove the E2E data folder ${target}: ${String(err)}`);
  }
}
