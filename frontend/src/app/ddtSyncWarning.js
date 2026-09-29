const FOUR_HOURS_MS = 4 * 60 * 60 * 1000;

export function ddtSyncWarning(sync, now) {
  const syncFailed = sync?.last_attempt?.status === "error";
  if (!sync?.enabled) return { syncFailed, neverSucceeded: false, stale: false };
  const finishedAt = sync.last_success?.finished_at;
  const successTime = finishedAt ? Date.parse(finishedAt) : NaN;
  return {
    syncFailed,
    neverSucceeded: !Number.isFinite(successTime),
    stale: Number.isFinite(successTime) && now - successTime >= FOUR_HOURS_MS,
  };
}

export function ddtSyncRecovered(previous, current, now) {
  if (!previous?.enabled || !current?.enabled || current.last_attempt?.status !== "success") return false;
  const warning = ddtSyncWarning(previous, now);
  return (warning.syncFailed || warning.neverSucceeded || warning.stale)
    && Boolean(current.last_success?.finished_at)
    && current.last_success.finished_at !== previous.last_success?.finished_at;
}
