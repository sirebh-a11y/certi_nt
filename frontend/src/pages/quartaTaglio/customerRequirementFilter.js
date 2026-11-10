export function normalizeCustomerRequirementFilter(value) {
  return ["all", "with", "without"].includes(value) ? value : "all";
}
