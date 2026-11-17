import assert from "node:assert/strict";
import test from "node:test";
import { restoreProductionProject } from "../lib/production-history.mjs";

test("restores the latest persisted run and project assets after a page revisit", () => {
  const latest = { id: 42, status: "failed", extractions: [{ description: "Keep the logo visible" }] };
  const older = { id: 41, status: "completed", extractions: [] };
  const asset = { id: 7, filename: "logo.png" };

  assert.deepEqual(restoreProductionProject({ runs: [latest, older], assets: [asset] }), {
    run: latest,
    assets: [asset],
  });
});

test("clears stale run state when the project has no persisted history", () => {
  assert.deepEqual(restoreProductionProject({ runs: [], assets: null }), { run: null, assets: [] });
  assert.deepEqual(restoreProductionProject(undefined), { run: null, assets: [] });
});
