import { BLOCKED_DOMAINS, defaultAllowedDomains } from "./domainPresets";

export interface DomainMatchOptions {
  allowedDomains?: string[];
  userAllowedDomains?: string[];
  blockedDomains?: string[];
}

export function isCaptureAllowedForUrl(
  url: string,
  options: DomainMatchOptions = {}
): boolean {
  const hostname = hostnameFromUrl(url);
  if (!hostname) {
    return false;
  }

  const blockedDomains = options.blockedDomains ?? BLOCKED_DOMAINS;
  if (matchesAnyDomain(hostname, blockedDomains)) {
    return false;
  }

  const allowedDomains = [
    ...(options.allowedDomains ?? defaultAllowedDomains()),
    ...(options.userAllowedDomains ?? [])
  ];
  return matchesAnyDomain(hostname, allowedDomains);
}

export function hostnameFromUrl(url: string): string | null {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
}

export function matchesDomain(hostname: string, domain: string): boolean {
  const normalizedHost = normalizeDomain(hostname);
  const normalizedDomain = normalizeDomain(domain);
  return (
    normalizedHost === normalizedDomain ||
    normalizedHost.endsWith(`.${normalizedDomain}`)
  );
}

export function matchesAnyDomain(hostname: string, domains: string[]): boolean {
  return domains.some((domain) => matchesDomain(hostname, domain));
}

function normalizeDomain(domain: string): string {
  return domain.trim().toLowerCase().replace(/^\*\./, "");
}
