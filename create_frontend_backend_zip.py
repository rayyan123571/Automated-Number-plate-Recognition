#!/usr/bin/env python3
import os
import zipfile
import fnmatch

base = os.getcwd()
outname = os.path.join(base, "frontend_backend_code.zip")
dirs = ["frontend", "backend"]
exclude_dirs = {"node_modules", "venv", ".venv", ".git", "__pycache__", ".next", "dist", "build"}
exclude_patterns = ["*.pyc", "*.pyo", "*.tmp", "*.log", "*.zip"]
max_size = 50 * 1024 * 1024  # skip files larger than 50 MB

added = []
skipped_large = []
missing = []
with zipfile.ZipFile(outname, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for d in dirs:
        dpath = os.path.join(base, d)
        if not os.path.exists(dpath):
            missing.append(d)
            continue
        for root, subdirs, files in os.walk(dpath):
            subdirs[:] = [sd for sd in subdirs if sd not in exclude_dirs and not sd.startswith('.')]
            for f in files:
                if f.startswith('.'):
                    continue
                if any(fnmatch.fnmatch(f, pat) for pat in exclude_patterns):
                    continue
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    continue
                if size > max_size:
                    skipped_large.append((os.path.relpath(fp, base), size))
                    continue
                rel = os.path.relpath(fp, base)
                zf.write(fp, rel)
                added.append(rel)

print(f"Archive: {outname}")
print(f"Directories requested: {dirs}")
if missing:
    print("Missing (skipped):", missing)
print(f"Files added: {len(added)}")
if skipped_large:
    print(f"Skipped large files (> {max_size//(1024*1024)}MB): {len(skipped_large)}")
    for p, s in skipped_large[:10]:
        print(f" - {p} ({s/1024/1024:.1f} MB)")

# print sample listing (first 200 entries)
for name in added[:200]:
    print(name)

print("Done.")
