#!/usr/bin/env python3
"""
Launcher script - starts the AI Computer server and monitors it
"""
import subprocess
import sys
import os
from pathlib import Path

# Change to the script directory
script_dir = Path(__file__).parent
os.chdir(script_dir)

print("=" * 60)
print("AI Computer Server Launcher")
print("=" * 60)
print(f"Working directory: {os.getcwd()}")
print()

# Build the command
cmd = [
    sys.executable,
    "-m", "uvicorn",
    "app.main:app",
    "--host", "127.0.0.1",
    "--port", "8080",
]

print(f"Starting: {' '.join(cmd)}")
print()
print("Server will be available at: http://127.0.0.1:8080")
print("=" * 60)
print()

# Start the server
try:
    subprocess.run(cmd, check=True)
except KeyboardInterrupt:
    print("\nServer stopped by user")
except Exception as e:
    print(f"Error starting server: {e}")
    sys.exit(1)
