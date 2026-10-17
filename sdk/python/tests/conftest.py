import sys
from pathlib import Path

# Add sdk/python root to sys.path so unclone_kyc can be imported directly in tests
sdk_root = Path(__file__).resolve().parent.parent
if str(sdk_root) not in sys.path:
    sys.path.insert(0, str(sdk_root))
