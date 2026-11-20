"""PyInstaller entry point for CrossMouse.

Importing ``crossmouse.main`` (rather than executing that file as a script)
gives its package-relative imports a parent package.
"""

from crossmouse.main import main

if __name__ == "__main__":
    raise SystemExit(main())
