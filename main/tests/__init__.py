import os
import sys
from pathlib import Path

sys.pycache_prefix = str(Path(__file__).resolve().parents[2] / ".shellcache")

os.environ["LEECH_CONFIG"] = ""
