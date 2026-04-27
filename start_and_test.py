#!/usr/bin/env python
"""
Automated startup script for AI Computer with testing
Starts the application and optionally runs tests
"""

import subprocess
import time
import os
import sys
from pathlib import Path
import psutil

def get_python_memory_usage():
    """Get current Python process memory usage"""
    try:
        proc = psutil.Process()
        return proc.memory_info().rss / 1024 / 1024  # MB
    except:
        return 0

def start_app():
    """Start the AI Computer application"""
    print("[*] Starting AI Computer Application...")
    print("[*] Command: python -m uvicorn app.main:app --host 127.0.0.1 --port 8080")
    print("[*] Access at: http://localhost:8080")
    print()

    # Start the uvicorn server
    cmd = [
        sys.executable,
        "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8080",
        "--reload"
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    return proc

def monitor_startup(proc, timeout=30):
    """Monitor startup and wait for app to be ready"""
    import socket

    start_time = time.time()
    print("[*] Waiting for application startup...")

    while time.time() - start_time < timeout:
        # Check if port is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 8080))
        sock.close()

        if result == 0:
            elapsed = time.time() - start_time
            print(f"[✓] Application started successfully in {elapsed:.2f}s")
            print(f"[✓] Memory usage: {get_python_memory_usage():.1f} MB")
            return True

        # Print any available output
        try:
            line = proc.stdout.readline()
            if line:
                print(f"[APP] {line.rstrip()}")
        except:
            pass

        time.sleep(0.5)

    print("[✗] Startup timeout")
    return False

def run_tests():
    """Run the multi-file refactoring test"""
    print("\n[*] Running multi-file refactoring test...")
    cmd = [
        sys.executable,
        "-m", "pytest",
        "tests/test_multifile_refactor.py",
        "-v", "-s"
    ]

    result = subprocess.run(cmd)
    return result.returncode == 0

if __name__ == "__main__":
    print("=" * 60)
    print("AI Computer - Startup & Test Script")
    print("=" * 60)
    print()

    # Change to script directory
    os.chdir(Path(__file__).parent)

    # Start the app
    proc = start_app()

    # Monitor startup
    success = monitor_startup(proc)

    if success:
        print()
        print("[✓] Application is running!")
        print("[!] Open http://localhost:8080 in your browser")
        print()

        # Optional: Run tests
        if len(sys.argv) > 1 and sys.argv[1] == "--test":
            print("[*] Running tests...")
            run_tests()
        else:
            print("[!] To run tests, call: python start_and_test.py --test")

        # Keep app running
        try:
            print("[*] Press Ctrl+C to stop the server...")
            proc.wait()
        except KeyboardInterrupt:
            print("\n[*] Shutting down...")
            proc.terminate()
            proc.wait(timeout=5)
    else:
        print("[✗] Failed to start application")
        sys.exit(1)
