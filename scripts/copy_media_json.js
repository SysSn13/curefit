// copy_media_json.js
// A tiny helper to ensure the React app always has access to the latest
// media index. Run this **before** starting Vite (predev / prebuild).
// It simply copies data/media_by_section.json ➜ frontend/public/media_by_section.json.
// If the destination folder does not exist it is created.

const fs = require('fs').promises;
const path = require('path');

async function main() {
  const root = __dirname;
  // paths
  const SRC = path.resolve(root, '..', 'data', 'media_by_section.json');
  const DEST_DIR = path.resolve(root, '..', 'frontend', 'public');
  const DEST = path.join(DEST_DIR, 'media_by_section.json');

  try {
    await fs.access(SRC);
  } catch {
    console.error(`❌ Source file not found: ${SRC}`);
    process.exit(1);
  }

  await fs.mkdir(DEST_DIR, { recursive: true });
  await fs.copyFile(SRC, DEST);

  console.log(`✅ Copied media_by_section.json ⇒ ${path.relative(root, DEST)}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
}); 