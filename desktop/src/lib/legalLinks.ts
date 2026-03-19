/** Canonical GitHub URLs (e.g. store listings). In-app Settings legal dialogs use bundled repo files via `legalDocSources.ts`. */
export const CUE_REPO_BASE_URL = "https://github.com/davidspivak2/cue/blob/main/";

export const CUE_CREATOR_NAME = "David Spivak";
export const CUE_CONTACT_EMAIL = "davidspivak2@gmail.com";

export const CUE_LEGAL_LINKS = {
  terms: `${CUE_REPO_BASE_URL}TERMS.md`,
  privacy: `${CUE_REPO_BASE_URL}PRIVACY.md`,
  license: `${CUE_REPO_BASE_URL}LICENSE`,
  thirdPartyNotices: `${CUE_REPO_BASE_URL}THIRD_PARTY_NOTICES.md`,
} as const;
