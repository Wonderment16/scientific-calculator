#!/usr/bin/env python3
"""
Entry point for the Calculator application.

Place this file next to the GUI file (gui.py) and your backend
(backend/engine.py). Run:

    python main.py

If your GUI file has a different name, change the import below.
"""
import sys
from pathlib import Path

# Optional: ensure current repo root is on sys.path so relative imports work
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import the GUI application class you saved earlier.
# Update the module name if you used a different filename.
try:
    from frontend.gui import CalculatorGUI
except Exception as e:
    print("Failed to import CalculatorGUI from calculator_gui_commented.py:", e)
    print("Make sure the GUI file is named calculator_gui_commented.py and is in the same directory.")
    raise

def main():
    # If you want the GUI to create its own backend engine, simply instantiate and run:
    app = CalculatorGUI()
    app.mainloop()

if __name__ == "__main__":
    main()