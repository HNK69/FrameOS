export type ProjectHistoryResponse<TRun, TAsset = unknown> = {
  runs?: TRun[] | null;
  assets?: TAsset[] | null;
};

export function restoreProductionProject<TRun, TAsset = unknown>(
  project: ProjectHistoryResponse<TRun, TAsset> | null | undefined,
): { run: TRun | null; assets: TAsset[] };
