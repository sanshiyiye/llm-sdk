import sys
import os

# Add the project root to the path so llm_sdk can be imported
sys.path.insert(0, os.getcwd())

# Run pytest programmatically
import pytest

sys.exit(pytest.main(["python/tests/test_sdk.py", "-v"]))
