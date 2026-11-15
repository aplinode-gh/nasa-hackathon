import subprocess, os, sys

base = r'D:\Desktop\Nasa Hackathon\nasa-hackathon'
os.chdir(base)

# Get deleted files in 5778620
r = subprocess.run(['git','--no-pager','diff','--name-status','--diff-filter=D','5778620^','5778620'], capture_output=True, text=True)
restored = []
failed = []
for line in r.stdout.splitlines():
    parts = line.split('\t')
    if len(parts) != 2:
        continue
    status, path = parts
    if status != 'D':
        continue
    keep = (
        '/detect/' in path or '/pest/' in path or '/profit-loss/' in path or
        path.startswith('apps/frontend/src/components/pest/') or
        path.startswith('apps/frontend/src/components/profit-loss/') or
        path.startswith('apps/frontend/src/lib/calculations/profit-loss') or
        path.startswith('apps/frontend/src/lib/detect/') or
        path.startswith('apps/frontend/src/lib/validation/detect') or
        path.startswith('apps/frontend/src/lib/validation/pest') or
        path.startswith('apps/frontend/src/lib/validation/profit-loss')
    )
    if not keep:
        continue
    dest = os.path.join(base, path.replace('/', os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    s = subprocess.run(['git','--no-pager','show', f'5778620^:{path}'], capture_output=True)
    if s.returncode == 0:
        with open(dest, 'wb') as f:
            f.write(s.stdout)
        restored.append(path)
    else:
        failed.append((path, s.stderr.decode('utf-8', 'ignore')))

# Also export reference versions of modified files from pre-removal commit
ref_files = [
 'apps/frontend/src/lib/i18n/server.ts',
 'apps/frontend/src/components/shell/app-sidebar.tsx',
 'apps/frontend/src/components/shell/bottom-tab-bar.tsx',
 'apps/frontend/src/components/shell/shell-bundle.ts',
 'apps/frontend/src/app/(farmer)/(dashboard)/dashboard/dashboard-bundle.ts',
 'apps/frontend/src/app/(farmer)/(dashboard)/dashboard/dashboard-view.tsx',
 'apps/frontend/src/app/(farmer)/(dashboard)/dashboard/page.tsx',
 'apps/frontend/src/app/(farmer)/(dashboard)/more/page.tsx',
 'apps/frontend/src/app/(farmer)/(dashboard)/notifications/page.tsx',
 'apps/frontend/src/app/(farmer)/(dashboard)/notifications/notifications-bundle.ts',
 'apps/frontend/src/app/(farmer)/(dashboard)/notifications/notifications-list.tsx',
]
for path in ref_files:
    out = os.path.join(base, '_ref_' + os.path.basename(path))
    s = subprocess.run(['git','--no-pager','show', f'5778620^:{path}'], capture_output=True)
    if s.returncode == 0:
        with open(out, 'wb') as f:
            f.write(s.stdout)
        restored.append('REF:' + out)
    else:
        failed.append((path, s.stderr.decode('utf-8','ignore')))

print('RESTORED', len(restored))
for p in restored:
    print('  +', p)
print('FAILED', len(failed))
for p,e in failed:
    print('  -', p, e[:100])
