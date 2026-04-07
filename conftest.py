# pytest configuration - adds sdk/python/ to path as llm_sdk package
import sys
import os

# Get project root and add sdk/python for imports
project_root = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.join(project_root, "sdk", "python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)
