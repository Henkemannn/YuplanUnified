from __future__ import annotations

from datetime import date

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

from .db import get_session
from .models import User

bp = Blueprint("demo", __name__)

BASE_HTML = """
<!doctype html>
<html lang='sv'>
  <head>
    <meta charset='utf-8'/>
    <title>Unified Demo</title>
    <style>
      body{font-family: system-ui, Arial; margin:2rem;}
      form{margin-bottom:1rem;}
      table{border-collapse:collapse;}
      td,th{border:1px solid #999;padding:4px 6px;}
      .error{color:#b00;}
      .ok{color:#060;}
      nav a{margin-right:1rem;}
    </style>
  </head>
  <body>
    <nav>
      {% if session.user_id %}
        Inloggad som {{ session.role }} | <a href='{{ url_for("auth.logout") }}' onclick="event.preventDefault(); document.getElementById('logoutForm').submit();">Logga ut</a>
        <form id='logoutForm' method='post' action='{{ url_for("auth.logout") }}' style='display:none'></form>
      {% endif %}
    </nav>
    <h1>Unified Plattform Demo</h1>
    <div id='content'>{{ content|safe }}</div>
  </body>
</html>
"""


@bp.route("/")
def index():
    if not session.get("user_id"):
        return redirect(url_for("demo.login"))
    today = date.today()
    week = int(today.strftime("%W")) or 1
    year = today.year
    tenant_id = session.get("tenant_id")
    svc = current_app.menu_service  # type: ignore[attr-defined]
    week_view = svc.get_week_view(tenant_id, week, year)
    inner = """
    <p>Vecka {{ week }} / {{ year }} (tenant {{ tenant_id }})</p>
    {% if week_view.menu_id %}
      <table>
        <tr><th>Dag</th><th>Måltid</th><th>Varianter</th></tr>
        {% for day, meals in week_view.days.items() %}
          {% for meal, variants in meals.items() %}
            <tr>
              <td>{{ day }}</td>
              <td>{{ meal }}</td>
              <td>
                {% for vtype, info in variants.items() %}
                  <div><strong>{{ vtype }}</strong>: {{ info.dish_name or '—' }}</div>
                {% endfor %}
              </td>
            </tr>
          {% endfor %}
        {% endfor %}
      </table>
    {% else %}
      <p>Ingen meny importerad än för denna vecka.</p>
    {% endif %}
    <hr/>
    <h3>Importera menyfil</h3>
    <form method='post' action='{{ url_for("import_api.import_menu") }}' enctype='multipart/form-data'>
      <input type='hidden' name='tenant_id' value='{{ tenant_id }}'/>
      <input type='file' name='file' required />
      <button>Importera</button>
    </form>
    <p><small>Stöder DOCX (kommun) och XLSX (offshore) prototyp.</small></p>
    """
    return render_template_string(BASE_HTML, content=inner, week=week, year=year, tenant_id=tenant_id, week_view=week_view)


@bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not email or not password:
            error = "Fyll i båda fälten."
        else:
            # Direkt DB-kontroll (enkel demo, ingen rate limiting etc.)
            db = get_session()
            try:
                user = db.query(User).filter(User.email == email).first()
                from werkzeug.security import check_password_hash
                if not user or not check_password_hash(user.password_hash, password):
                    error = "Fel inloggning"
                else:
                    session["user_id"] = user.id
                    session["role"] = user.role
                    session["tenant_id"] = user.tenant_id
                    session["unit_id"] = user.unit_id
                    return redirect(url_for("demo.index"))
            finally:
                db.close()
        inner = """
          <p class='error'>{{ error }}</p>
          <a href='{{ url_for("demo.login") }}'>Försök igen</a>
        """
        return render_template_string(BASE_HTML, content=inner, error=error)
    inner = """
      <h2>Logga in</h2>
      <form method='post'>
        <label>E-post <input name='email' type='email' required></label><br/>
        <label>Lösenord <input name='password' type='password' required></label><br/>
        <button>Logga in</button>
      </form>
      <p><small>Använd bootstrap superuser eller manuellt skapad användare.</small></p>
    """
    return render_template_string(BASE_HTML, content=inner)
