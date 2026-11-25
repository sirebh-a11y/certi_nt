const FOUR_HOURS_MS = 4 * 60 * 60 * 1000;
const DAILY_START_GRACE_MS = 5 * 60 * 1000;

export function ddtSyncWarning(sync, now) {
  const syncFailed = sync?.last_attempt?.status === "error";
  if (!sync?.enabled) return { syncFailed, neverSucceeded: false, stale: false };
  const finishedAt = sync.last_success?.finished_at;
  const successTime = finishedAt ? Date.parse(finishedAt) : NaN;
  const scheduledAt = Date.parse(sync.last_scheduled_at);
  if (!Number.isFinite(scheduledAt) && Number.isFinite(Date.parse(sync.next_scheduled_at))) {
    return { syncFailed, neverSucceeded: false, stale: false }; // First planned read still ahead.
  }
  if (Number.isFinite(scheduledAt)) {
    const successStartedAt = Date.parse(sync.last_success?.started_at ?? finishedAt);
    const missed = !sync.in_progress && now >= scheduledAt + DAILY_START_GRACE_MS;
    return {
      syncFailed,
      neverSucceeded: missed && !Number.isFinite(successTime),
      stale: missed && Number.isFinite(successTime) && successStartedAt < scheduledAt,
    };
  }
  // Kept for compatibility while the UI and API are updated together.
  return {
    syncFailed,
    neverSucceeded: !Number.isFinite(successTime),
    stale: Number.isFinite(successTime) && now - successTime >= FOUR_HOURS_MS,
  };
}

export function ddtSyncHasNewSuccess(previous, current) {
  if (!previous || !current?.enabled) return false;
  const last = Date.parse(current.last_success?.finished_at);
  const older = Date.parse(previous.last_success?.finished_at);
  return Number.isFinite(last) && (!Number.isFinite(older) || last > older);
}

export function ddtSyncShouldReloadQueue(previous, current) {
  if (ddtSyncHasNewSuccess(previous, current)) return true;
  if (!previous?.enabled || !current?.enabled || previous.in_progress !== true
      || current.in_progress !== false || current.last_attempt?.status !== "success") return false;

  // A successful read is saved before the job finishes preparing its Word copies.
  const slot = Date.parse(previous.last_scheduled_at ?? current.last_scheduled_at);
  const started = Date.parse(current.last_success?.started_at ?? current.last_success?.finished_at);
  return Number.isFinite(slot) && started >= slot;
}

export function ddtSyncRecovered(previous, current, now) {
  if (!previous?.enabled || !current?.enabled || current.last_attempt?.status !== "success") return false;
  const warning = ddtSyncWarning(previous, now);
  return (warning.syncFailed || warning.neverSucceeded || warning.stale)
    && ddtSyncHasNewSuccess(previous, current);
}
