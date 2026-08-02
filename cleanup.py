"""Cross-platform cleanup: remove __pycache__ dirs and .pyc files."""
import os, sys
root = os.path.abspath(os.path.dirname(__file__))
if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
    for dirpath, dirnames, filenames in os.walk(root):
        if '__pycache__' in dirnames:
            print('Would remove:', os.path.join(dirpath, '__pycache__'))
        for f in filenames:
            if f.endswith('.pyc'):
                print('Would delete:', os.path.join(dirpath, f))
    sys.exit(0)

for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirnames:
        path = os.path.join(dirpath, '__pycache__')
        try:
            import shutil
            shutil.rmtree(path)
            print('Removed', path)
        except Exception as e:
            print('Failed to remove', path, e)
    for f in filenames:
        if f.endswith('.pyc'):
            p = os.path.join(dirpath, f)
            try:
                os.remove(p)
                print('Deleted', p)
            except Exception as e:
                print('Failed to delete', p, e)
print('Cleanup finished.')
