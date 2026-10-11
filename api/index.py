import os
import sys

# Ensure repository root is on sys.path so modules and templates are resolved
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app as flask_app

class PrefixMiddleware:
    """Ensure PATH_INFO is cleanly routed when Vercel or proxies prefix /api/index or /api/index.py"""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        for prefix in ('/api/index.py', '/api/index'):
            if path.startswith(prefix):
                remainder = path[len(prefix):]
                environ['PATH_INFO'] = remainder if remainder.startswith('/') else ('/' + remainder if remainder else '/')
                break
        return self.wsgi_app(environ, start_response)

flask_app.wsgi_app = PrefixMiddleware(flask_app.wsgi_app)
app = flask_app
