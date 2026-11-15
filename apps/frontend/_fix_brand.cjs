const fs = require('fs');
const path = require('path');

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['node_modules', '.next', '.git', '.agents', '.claude'].includes(e.name)) continue;
      walk(p, out);
    } else out.push(p);
  }
  return out;
}

const exts = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json', '.css', '.md', '.html', '.svg']);
let changed = 0;
for (const f of walk(__dirname)) {
  const base = path.basename(f);
  if (base === '_fix_brand.cjs') continue;
  if (/_ref_|_restore_removed|temp_|^_tmp/.test(base)) continue;
  if (!exts.has(path.extname(f).toLowerCase())) continue;
  let s;
  try { s = fs.readFileSync(f, 'utf8'); } catch { continue; }
  let n = s;
  n = n.split('whyAgroAI').join('whyAgropioo');
  n = n.split('AgroAI').join('Agropioo');
  n = n.split('agroai').join('agropioo'); // catch remaining lowercase refs in paths/ids
  n = n.split('@/references/Agropioo-logo-with-text.png').join('/agropioo-mark.svg');
  n = n.split('@/references/Agropioo-logo-withoutbg-text.png').join('/agropioo-mark.svg');
  n = n.split('@/references/Agropioo-logo-footer.png').join('/agropioo-mark-light.svg');
  n = n.split('@/references/agropioo-logo-with-text.png').join('/agropioo-mark.svg');
  n = n.split('@/references/agropioo-logo-withoutbg-text.png').join('/agropioo-mark.svg');
  n = n.split('@/references/agropioo-logo-footer.png').join('/agropioo-mark-light.svg');
  n = n.split('src="/agropioo-mark-light.svg"').join('src="/agropioo-mark-light.svg"');
  n = n.split('/hero-farmer.svg').join('/agropioo-hero.svg');
  n = n.split('/logo.png').join('/agropioo-mark.svg');
  n = n.split('hello@agropioo.com').join('hello@agropioo.example');
  // fix any doubled Agropioo from earlier passes? unlikely but safe
  if (n !== s) {
    fs.writeFileSync(f, n, 'utf8');
    changed++;
    process.stdout.write('changed: ' + path.relative(__dirname, f) + '\n');
  }
}
console.log('TOTAL', changed);
