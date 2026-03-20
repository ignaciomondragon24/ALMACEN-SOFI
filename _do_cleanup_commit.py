import subprocess, os

os.chdir(r'c:\Users\nacho\Desktop\CHE GOLOSO\che goloso')

# 1. Delete file
target = '_delete_old_templates.py'
if os.path.exists(target):
    os.remove(target)
    print(f'DELETED: {target}')
else:
    print(f'ALREADY GONE: {target}')

# 2. git add -A
r = subprocess.run(['git', 'add', '-A'], capture_output=True, text=True)
print(f'git add -A: RC={r.returncode}')

# 3. git commit
r = subprocess.run(['git', 'commit', '-m', 'chore: remove temporary cleanup script'], capture_output=True, text=True)
print(f'git commit: RC={r.returncode}')
print(r.stdout.strip())
if r.stderr.strip():
    print('STDERR:', r.stderr.strip())

# 4. git push
r = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
print(f'git push: RC={r.returncode}')
print(r.stdout.strip() if r.stdout.strip() else '')
print(r.stderr.strip() if r.stderr.strip() else '')

# 5. Show commit hash
r = subprocess.run(['git', 'log', '--oneline', '-1'], capture_output=True, text=True)
print(f'LATEST COMMIT: {r.stdout.strip()}')
