import sys
import tkinter as tk
from gui import ModernFishingGUI

def main():
    root = tk.Tk()
    app = ModernFishingGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
