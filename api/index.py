import os
import sys

# Ensure repository root is on sys.path so modules and templates are resolved
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from werkzeug.middleware.proxy_fix import ProxyFix
from app import app as flask_app

class VercelPathFixMiddleware:
    """
    Ensure PATH_INFO reflects the actual user-requested URL on Vercel.
    When Vercel rewrites routes to /api/index.py, it stores the original
    requested path in HTTP_X_MATCHED_PATH (or HTTP_X_NOW_ROUTE_MATCHES).
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        raw_path = environ.get('HTTP_X_MATCHED_PATH') or environ.get('HTTP_X_NOW_ROUTE_MATCHES')
        if raw_path:
            parts = raw_path.split('?', 1)
            clean_path = parts[0]
            if len(parts) > 1 and not environ.get('QUERY_STRING'):
                environ['QUERY_STRING'] = parts[1]
            if not clean_path.startswith('/'):
                clean_path = '/' + clean_path
            # If the matched path itself starts with /api/index.py or /api/index, strip it
            for prefix in ('/api/index.py', '/api/index'):
                if clean_path.startswith(prefix):
                    clean_path = clean_path[len(prefix):]
                    if not clean_path.startswith('/'):
                        clean_path = '/' + clean_path
                    break
            environ['PATH_INFO'] = clean_path
        else:
            path = environ.get('PATH_INFO', '')
            for prefix in ('/api/index.py', '/api/index'):
                if path.startswith(prefix):
                    remainder = path[len(prefix):]
                    environ['PATH_INFO'] = remainder if remainder.startswith('/') else ('/' + remainder if remainder else '/')
                    break
        return self.wsgi_app(environ, start_response)

flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
flask_app.wsgi_app = VercelPathFixMiddleware(flask_app.wsgi_app)
app = flask_app
