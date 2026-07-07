import subprocess
result = subprocess.run(['node', '-c', 'static/js/app.js'], capture_output=True, text=True)
if result.returncode != 0:
    print("Syntax Error:")
    print(result.stderr)
else:
    print("Syntax OK")
