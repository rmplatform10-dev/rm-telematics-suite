Upgrade notes (automated edits performed):

- Replaced hard-coded py -3.12 invocation in Start_Dashboard.bat with a portable fallback (py -3 || python).
- Added .gitignore to ignore __pycache__, *.pyc, node_modules and common temp files.
- Added cleanup.bat and cleanup.py to remove __pycache__ and .pyc files safely.
- Added deploy.bat as a one-click helper to run cleanup, start gateway (if present), and launch the dashboard.
- Injected a small runtime config into dashboard/index.html to set window.RM_CONFIG.apiBase based on hostname.

Next recommended steps:
1. Run cleanup.bat (dry-run first: cleanup.bat /n) to verify deletions.
2. Test deploy.bat on a Windows machine with Python installed.
3. Rebuild front-end assets so the SPA can read window.RM_CONFIG (if the bundle is designed to use it). If not, plan a small front-end patch to prefer window.RM_CONFIG.apiBase when present.

