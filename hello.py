import sys
from datetime import datetime

name = sys.argv[1] if len(sys.argv) > 1 else "Unknown"

print(f"Hello, {name}!")
print(f"Current time: {datetime.now()}")
