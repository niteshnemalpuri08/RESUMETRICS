import os
import sys
import urllib.parse

# Ensure repository root is on sys.path so modules and templates are resolved
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from werkzeug.middleware.proxy_fix import ProxyFix
from app import app as flask_app

class VercelRoutingMiddleware:
    """
    Guarantees seamless route resolution on Vercel.
    Extracts the rewritten __route__ parameter, HTTP_X_MATCHED_PATH, or PATH_INFO.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        parsed = urllib.parse.parse_qs(qs, keep_blank_values=True)
        if '__route__' in parsed:
            route = parsed.pop('__route__')[0]
            clean_qs = urllib.parse.urlencode([(k, v) for k, vals in parsed.items() for v in vals])
            environ['QUERY_STRING'] = clean_qs
            clean_route = '/' + route.lstrip('/')
            environ['PATH_INFO'] = clean_route
        elif environ.get('HTTP_X_MATCHED_PATH'):
            raw = environ['HTTP_X_MATCHED_PATH'].split('?')[0]
            if not raw.startswith('/'):
                raw = '/' + raw
            environ['PATH_INFO'] = raw
        else:
            path = environ.get('PATH_INFO', '')
            for prefix in ('/api/index.py', '/api/index'):
                if path.startswith(prefix):
                    rem = path[len(prefix):]
                    environ['PATH_INFO'] = rem if rem.startswith('/') else ('/' + rem if rem else '/')
                    break

        return self.wsgi_app(environ, start_response)

flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
flask_app.wsgi_app = VercelRoutingMiddleware(flask_app.wsgi_app)
app = flask_app
