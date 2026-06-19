import subprocess
import sys

# Run the django tests command
result = subprocess.run(
    [r"C:\pinokio\bin\miniconda\python.exe", "manage.py", "test"],
    capture_output=True,
    text=True
)

# Write output to file
with open(r"c:\Users\Administrator\agriproject\test_results.txt", "w") as f:
    f.write("--- STDOUT ---\n")
    f.write(result.stdout)
    f.write("\n--- STDERR ---\n")
    f.write(result.stderr)
    f.write(f"\nExit Code: {result.returncode}\n")

print("Test results written to test_results.txt")
