# Add project root to path so we can find the tests directory
import sys
import os

# Go up from python/tests to project root, then add python/ as llm_sdk package
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
python_dir = os.path.join(project_root, "python")

# Add project root first, then python directory
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)
