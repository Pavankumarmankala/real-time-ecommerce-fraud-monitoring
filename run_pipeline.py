"""Run the full project: python run_pipeline.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from pipeline import run
from dashboard import build

if __name__ == "__main__":
    run()
    build()
