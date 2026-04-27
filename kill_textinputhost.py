import os
import subprocess
import time

print("Killing textinputhost.exe...")
try:
    subprocess.run(["taskkill", "/IM", "textinputhost.exe", "/F"], check=False)
    print("✓ Process terminated")
    time.sleep(1)
except Exception as e:
    print(f"Error: {e}")
