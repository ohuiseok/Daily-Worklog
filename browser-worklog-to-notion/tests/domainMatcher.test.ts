import { describe, expect, it } from "vitest";

import { defaultAllowedDomains } from "../src/domainPresets";
import { hostnameFromUrl, isCaptureAllowedForUrl, matchesDomain } from "../src/domainMatcher";

describe("domainMatcher", () => {
  it("allows developer and ai preset domains", () => {
    expect(isCaptureAllowedForUrl("https://github.com/openai/codex")).toBe(true);
    expect(isCaptureAllowedForUrl("https://www.notion.so/page")).toBe(true);
    expect(isCaptureAllowedForUrl("https://app.notion.com/workspace/page")).toBe(true);
    expect(isCaptureAllowedForUrl("https://chatgpt.com/c/123")).toBe(true);
  });

  it("blocks sensitive domains", () => {
    expect(isCaptureAllowedForUrl("https://gmail.com/mail/u/0")).toBe(false);
    expect(isCaptureAllowedForUrl("https://accounts.google.com/signin")).toBe(false);
    expect(isCaptureAllowedForUrl("https://dashboard.stripe.com/test")).toBe(false);
  });

  it("supports user allowed domains", () => {
    expect(
      isCaptureAllowedForUrl("https://internal.example.com/editor", {
        allowedDomains: [],
        userAllowedDomains: ["example.com"],
        blockedDomains: []
      })
    ).toBe(true);
  });

  it("matches subdomains", () => {
    expect(matchesDomain("docs.github.com", "github.com")).toBe(true);
    expect(matchesDomain("github.com", "github.com")).toBe(true);
    expect(matchesDomain("notgithub.com", "github.com")).toBe(false);
  });

  it("returns null for invalid urls", () => {
    expect(hostnameFromUrl("not a url")).toBeNull();
  });

  it("contains the expected default domains", () => {
    expect(defaultAllowedDomains()).toContain("github.com");
    expect(defaultAllowedDomains()).toContain("chatgpt.com");
    expect(defaultAllowedDomains()).toContain("notion.com");
    expect(defaultAllowedDomains()).toContain("notion.so");
  });
});
