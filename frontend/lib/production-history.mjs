export function restoreProductionProject(project) {
  return {
    run: project?.runs?.[0] ?? null,
    assets: project?.assets ?? [],
  };
}
