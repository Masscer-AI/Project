/** IANA timezones for organization settings (searchable Select). */
export function getOrganizationTimezoneOptions(): { value: string; label: string }[] {
  try {
    const zones = Intl.supportedValuesOf("timeZone");
    return zones.map((tz) => ({ value: tz, label: tz }));
  } catch {
    return [{ value: "UTC", label: "UTC" }];
  }
}

export const DEFAULT_ORGANIZATION_TIMEZONE = "UTC";
