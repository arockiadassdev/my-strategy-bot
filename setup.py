"""
Setup script for my-strategy-bot.
Creates .env from example and installs dependencies.
"""
import os
import sys
import subprocess

def main():
    print("=" * 50)
    print("my-strategy-bot — Setup")
    print("=" * 50)

    # 1. Create .env if not exists
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    example_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example")
    if not os.path.exists(env_path):
        if os.path.exists(example_path):
            with open(example_path) as f:
                example = f.read()
            with open(env_path, "w") as f:
                f.write(example)
            print(f"✅ Created .env from .env.example")
        else:
            print(f"⚠️  No .env.example found, skipping .env creation")
    else:
        print(f"✅ .env already exists")

    # 2. Install dependencies
    req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    print(f"\n📦 Installing dependencies from {req_path}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_path],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"✅ Dependencies installed")
    else:
        print(f"❌ Failed to install: {result.stderr}")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"Setup complete. Run:")
    print(f"  python main.py --backfill    Backtest + validation")
    print(f"  python main.py --paper       Paper trading")
    print(f"  python main.py --testnet     Bybit testnet")
    print(f"  python main.py --live        Live trading")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()