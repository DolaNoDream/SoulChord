import sys
import os

print("Current working directory:", os.getcwd())
print("Script file:", __file__)
print("Absolute path:", os.path.abspath(__file__))

dir1 = os.path.dirname(os.path.abspath(__file__))
print("Level 1 dir:", dir1)

dir2 = os.path.dirname(dir1)
print("Level 2 dir:", dir2)

dir3 = os.path.dirname(dir2)
print("Level 3 dir:", dir3)

sys.path.insert(0, dir3)
print("sys.path[0]:", sys.path[0])

print("\nTrying to import backend.main...")
try:
    from backend.main import app
    print("SUCCESS: Imported backend.main")
except Exception as e:
    print(f"FAILED: {e}")