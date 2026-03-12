import alefUrl from "../../app/fonts/Alef-Regular.ttf";
import arimoUrl from "../../app/fonts/Arimo-Variable.ttf";
import assistantUrl from "../../app/fonts/Assistant-Variable.ttf";
import frankRuhlLibreUrl from "../../app/fonts/FrankRuhlLibre-Variable.ttf";
import heeboUrl from "../../app/fonts/Heebo-Variable.ttf";
import ibmPlexSansHebrewUrl from "../../app/fonts/IBMPlexSansHebrew-Regular.ttf";
import notoSansHebrewUrl from "../../app/fonts/NotoSansHebrew-Variable.ttf";
import rubikUrl from "../../app/fonts/Rubik-Variable.ttf";
import secularOneUrl from "../../app/fonts/SecularOne-Regular.ttf";
import suezOneUrl from "../../app/fonts/SuezOne-Regular.ttf";

type SubtitleFontFace = {
  family: string;
  sourceUrl: string;
  fontWeight: string;
};

const SUBTITLE_FONT_FACES: SubtitleFontFace[] = [
  { family: "Alef", sourceUrl: alefUrl, fontWeight: "400" },
  { family: "Arimo", sourceUrl: arimoUrl, fontWeight: "400 700" },
  { family: "Assistant", sourceUrl: assistantUrl, fontWeight: "200 800" },
  { family: "Frank Ruhl Libre", sourceUrl: frankRuhlLibreUrl, fontWeight: "300 900" },
  { family: "Heebo", sourceUrl: heeboUrl, fontWeight: "100 900" },
  { family: "IBM Plex Sans Hebrew", sourceUrl: ibmPlexSansHebrewUrl, fontWeight: "400" },
  { family: "Noto Sans Hebrew", sourceUrl: notoSansHebrewUrl, fontWeight: "100 900" },
  { family: "Rubik", sourceUrl: rubikUrl, fontWeight: "300 900" },
  { family: "Secular One", sourceUrl: secularOneUrl, fontWeight: "400" },
  { family: "Suez One", sourceUrl: suezOneUrl, fontWeight: "400" }
];

let subtitleFontFacesInstalled = false;

export function installSubtitleFontFaces(): void {
  if (subtitleFontFacesInstalled || typeof document === "undefined") {
    return;
  }
  subtitleFontFacesInstalled = true;
  const styleTag = document.createElement("style");
  styleTag.setAttribute("data-subtitle-font-faces", "true");
  styleTag.textContent = SUBTITLE_FONT_FACES.map(
    ({ family, sourceUrl, fontWeight }) => `@font-face {
  font-family: "${family}";
  src: local("${family}"), url("${sourceUrl}") format("truetype");
  font-style: normal;
  font-weight: ${fontWeight};
  font-display: swap;
}`
  ).join("\n");
  document.head.appendChild(styleTag);
}
