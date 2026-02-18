/**
 * Generates 32x32 PNG icons from public/light.svg and public/dark.svg
 * into src-tauri/icons/ for theme-aware native window icon.
 * Run: node scripts/generate-theme-icons.cjs
 */
const sharp = require("sharp");
const path = require("path");
const fs = require("fs");

const ROOT = path.resolve(__dirname, "..");
const PUBLIC = path.join(ROOT, "public");
const PUBLIC_ICONS = path.join(PUBLIC, "icons");
const TAURI_ICONS = path.join(ROOT, "src-tauri", "icons");

async function main() {
  fs.mkdirSync(PUBLIC_ICONS, { recursive: true });
  fs.mkdirSync(TAURI_ICONS, { recursive: true });
  for (const name of ["light", "dark"]) {
    const src = path.join(PUBLIC, `${name}.svg`);
    const buf = await sharp(src).resize(32, 32).png().toBuffer();
    const publicDest = path.join(PUBLIC_ICONS, `${name}-32.png`);
    const tauriDest = path.join(TAURI_ICONS, `${name}-32.png`);
    fs.writeFileSync(publicDest, buf);
    fs.writeFileSync(tauriDest, buf);
    console.log(`Wrote ${publicDest} and ${tauriDest}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
