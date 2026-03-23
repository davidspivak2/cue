/**
 * Generates themed PNG icons from public/light.svg and public/dark.svg
 * into src-tauri/icons/ and public/icons/ for native Windows taskbar icons.
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
    for (const size of [32, 256]) {
      const buf = await sharp(src).resize(size, size).png().toBuffer();
      const publicDest = path.join(PUBLIC_ICONS, `${name}-${size}.png`);
      const tauriDest = path.join(TAURI_ICONS, `${name}-${size}.png`);
      fs.writeFileSync(publicDest, buf);
      fs.writeFileSync(tauriDest, buf);
      console.log(`Wrote ${publicDest} and ${tauriDest}`);
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
