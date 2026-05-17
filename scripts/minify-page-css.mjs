import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import CleanCSS from 'clean-css';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const files = [
  ['static/css/src/course-detail.css', 'static/css/course-detail.min.css'],
  ['static/css/src/courses-list.css', 'static/css/courses-list.min.css'],
];

const minifier = new CleanCSS({ level: 2 });

for (const [srcRel, destRel] of files) {
  const src = path.join(root, srcRel);
  const dest = path.join(root, destRel);
  const input = fs.readFileSync(src, 'utf8');
  const out = minifier.minify(input);
  if (out.errors?.length) {
    console.error(`${srcRel}:`, out.errors);
    process.exit(1);
  }
  fs.writeFileSync(dest, out.styles);
  const pct = Math.round((1 - out.styles.length / input.length) * 100);
  console.log(`${path.basename(destRel)}: ${input.length} → ${out.styles.length} bytes (−${pct}%)`);
}
