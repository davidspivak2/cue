/**
 * Bundled at build time from repo root. Updating TERMS.md, PRIVACY.md, LICENSE,
 * or THIRD_PARTY_NOTICES.md updates what the in-app legal dialogs show after rebuild.
 */
import licenseText from "../../../LICENSE?raw";
import privacyMarkdown from "../../../PRIVACY.md?raw";
import termsMarkdown from "../../../TERMS.md?raw";
import thirdPartyNoticesMarkdown from "../../../THIRD_PARTY_NOTICES.md?raw";

export type LegalDocKey = "terms" | "privacy" | "license" | "thirdPartyNotices";

export const LEGAL_DOC_TITLES: Record<LegalDocKey, string> = {
  terms: "Terms",
  privacy: "Privacy",
  license: "License",
  thirdPartyNotices: "Third-party notices"
};

export const LEGAL_DOC_BODY: Record<LegalDocKey, string> = {
  terms: termsMarkdown,
  privacy: privacyMarkdown,
  license: licenseText,
  thirdPartyNotices: thirdPartyNoticesMarkdown
};
