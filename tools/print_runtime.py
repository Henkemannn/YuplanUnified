import os, sys
sys.path.insert(0, os.path.abspath('.'))
from core.app_factory import create_app
if __name__ == '__main__':
    app = create_app({"TESTING": False})
    print("App created.")
