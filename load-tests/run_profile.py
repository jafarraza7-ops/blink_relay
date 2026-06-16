#!/usr/bin/env python3
"""Convenience script to run predefined load test profiles"""
import subprocess
import sys
import yaml
from pathlib import Path

def load_config():
    with open(Path(__file__).parent / "config.yaml") as f:
        return yaml.safe_load(f)

def get_profile(config, profile_name):
    if profile_name not in config["profiles"]:
        available = ", ".join(config["profiles"].keys())
        print(f"❌ Unknown profile: {profile_name}")
        print(f"Available profiles: {available}")
        return None
    return config["profiles"][profile_name]

def run_profile(profile_name: str):
    config = load_config()
    profile = get_profile(config, profile_name)
    if not profile:
        sys.exit(1)

    users = profile["total_users"]
    spawn_rate = profile["spawn_rate"]
    duration = profile["duration_minutes"]
    description = profile["description"]
    host = config["api_host"]

    print("\n" + "="*70)
    print(f"🚀 Running '{profile_name}' Load Profile")
    print("="*70)
    print(f"📊 Description: {description}")
    print(f"👥 Users: {users} concurrent")
    print(f"⏱️  Spawn Rate: {spawn_rate} users/second")
    print(f"⏰ Duration: {duration} minutes")
    print(f"🔗 Host: {host}")
    print("="*70 + "\n")

    cmd = [
        "locust", "-f", "locustfile.py",
        f"--host={host}",
        f"-u", str(users),
        f"-r", str(spawn_rate),
        f"-t", f"{duration}m",
        "--headless",
        f"--csv=results/{profile_name}",
    ]

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\n⏹️  Load test interrupted by user")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ locust not found. Install with: pip install -r requirements.txt")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_profile.py <profile_name>")
        config = load_config()
        print("\n📋 Available profiles:")
        for name in config["profiles"].keys():
            print(f"  - {name}")
        sys.exit(1)
    run_profile(sys.argv[1])
