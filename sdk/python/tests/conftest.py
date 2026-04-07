# Add sdk/python to path for local package imports
import sys
import os

# Go up from sdk/python/tests to sdk/, then add sdk/python/ as llm_sdk package
sdk_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
python_dir = os.path.join(sdk_root, "python")

# Add sdk root first, then python directory
if sdk_root not in sys.path:
    sys.path.insert(0, sdk_root)
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)
