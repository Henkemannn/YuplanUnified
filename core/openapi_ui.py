from __future__ import annotations

from flask import Blueprint, Response, abort

bp = Blueprint("openapi_ui", __name__, url_prefix="/docs")

HTML = """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\">
    <title>Yuplan API Docs</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\">
    <style>body { margin:0;} .topbar { display:none; }</style>
  </head>
  <body>
    <div id=\"swagger\"></div>
    <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
      });
    </script>
  </body>
</html>"""

@bp.get("/")
def docs_index():  # pragma: no cover simple UI
    # Optional feature flag gate: openapi_ui
    # If feature flag disabled, show 404 (silent disable)
    # We reuse feature_enabled context processor if available.
  try:
    from flask import current_app
    feature_fn = current_app.jinja_env.globals.get("feature_enabled")
    if feature_fn and callable(feature_fn) and not feature_fn("openapi_ui"):
      abort(404)
  except Exception:  # pragma: no cover - defensive
    pass
  return Response(HTML, mimetype="text/html")
