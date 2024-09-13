import sys
from pathlib import Path

velib_python_path = Path(__file__).resolve().parent.parent / 'ext' / 'velib_python'
sys.path.insert(1, str(velib_python_path))
del velib_python_path

__version__ = "0.0.1"