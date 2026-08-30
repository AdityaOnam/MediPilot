"""
conftest.py — pytest configuration for backend.
Adds the project root to sys.path so all modules import correctly.
"""
import sys
import pathlib

# Add the backend directory to the path
sys.path.insert(0, str(pathlib.Path(__file__).parent))
