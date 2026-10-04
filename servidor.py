import os
import sqlite3
from functools import wraps

from flask import Flask, Response, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "tareas.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            contraseña TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            completada INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
        """
    )
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM usuarios WHERE usuario = ?",
        (username,),
    ).fetchone()
    conn.close()
    if user is None:
        return None
    return dict(user)


def get_user_id_by_username(username):
    user = get_user_by_username(username)
    return user["id"] if user else None


def require_basic_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth:
            return Response(
                "Se requiere autenticación básica.",
                401,
                {"WWW-Authenticate": "Basic realm='Tareas'"},
            )

        user = get_user_by_username(auth.username)
        if not user or not check_password_hash(user["contraseña"], auth.password):
            return Response(
                "Credenciales inválidas.",
                401,
                {"WWW-Authenticate": "Basic realm='Tareas'"},
            )

        return func(*args, **kwargs)

    return wrapper


@app.route("/", methods=["GET"])
def index():
    return "<h1>API de Gestión de Tareas</h1><p>Usá /registro, /login y /tareas.</p>"


@app.route("/registro", methods=["POST"])
def registro_usuario():
    data = request.get_json(silent=True) or {}
    usuario = (data.get("usuario") or "").strip()
    contraseña = data.get("contraseña") or ""

    if not usuario or not contraseña:
        return jsonify({"error": "Debe enviar 'usuario' y 'contraseña'."}), 400

    password_hashed = generate_password_hash(contraseña)
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO usuarios (usuario, contraseña) VALUES (?, ?)",
            (usuario, password_hashed),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "El usuario ya existe."}), 409

    conn.close()
    return jsonify({"mensaje": "Usuario registrado correctamente.", "usuario": usuario}), 201


@app.route("/login", methods=["POST"])
def login_usuario():
    data = request.get_json(silent=True) or {}
    usuario = (data.get("usuario") or "").strip()
    contraseña = data.get("contraseña") or ""

    user = get_user_by_username(usuario)
    if user is None or not check_password_hash(user["contraseña"], contraseña):
        return jsonify({"error": "Credenciales inválidas."}), 401

    return jsonify({"mensaje": "Login correcto.", "usuario": usuario}), 200


@app.route("/tareas", methods=["GET", "POST"])
@require_basic_auth
def tareas():
    username = request.authorization.username

    if request.method == "GET":
        conn = get_db_connection()
        tareas_db = conn.execute(
            """
            SELECT t.id, t.titulo, t.descripcion, t.completada, t.created_at
            FROM tareas t
            INNER JOIN usuarios u ON u.id = t.usuario_id
            WHERE u.usuario = ?
            ORDER BY t.id DESC
            """,
            (username,),
        ).fetchall()
        conn.close()

        html = f"""
        <html>
        <head>
            <title>Listado de tareas</title>
        </head>
        <body>
            <h1>Bienvenido, {username}</h1>
            <h2>Lista de tareas</h2>
        """

        if tareas_db:
            html += "<ul>"
            for tarea in tareas_db:
                estado = "✅" if tarea["completada"] else "❌"
                html += (
                    f"<li><strong>{tarea['titulo']}</strong> - {estado}<br>"
                    f"{tarea['descripcion']}</li>"
                )
            html += "</ul>"
        else:
            html += "<p>No tenés tareas todavía.</p>"

        html += "<p>Podés usar el cliente de consola para agregar más tareas.</p>"
        html += "</body></html>"
        return Response(html, mimetype="text/html")

    data = request.get_json(silent=True) or {}
    titulo = (data.get("titulo") or "").strip()
    descripcion = data.get("descripcion") or ""

    if not titulo:
        return jsonify({"error": "Debe indicar un título para la tarea."}), 400

    user_id = get_user_id_by_username(username)
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO tareas (usuario_id, titulo, descripcion, completada) VALUES (?, ?, ?, ?)",
        (user_id, titulo, descripcion, 0),
    )
    conn.commit()
    tarea_id = cursor.lastrowid
    conn.close()

    return (
        jsonify(
            {
                "mensaje": "Tarea creada correctamente.",
                "id": tarea_id,
                "titulo": titulo,
                "descripcion": descripcion,
                "completada": False,
            }
        ),
        201,
    )


@app.route("/tareas/<int:tarea_id>", methods=["PUT", "DELETE"])
@require_basic_auth
def tarea_detalle(tarea_id):
    username = request.authorization.username
    user_id = get_user_id_by_username(username)
    conn = get_db_connection()
    tarea = conn.execute(
        "SELECT * FROM tareas WHERE id = ? AND usuario_id = ?",
        (tarea_id, user_id),
    ).fetchone()

    if tarea is None:
        conn.close()
        return jsonify({"error": "Tarea no encontrada."}), 404

    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        if "titulo" in data:
            titulo = (data.get("titulo") or "").strip()
            if not titulo:
                conn.close()
                return jsonify({"error": "El título no puede quedar vacío."}), 400
            conn.execute("UPDATE tareas SET titulo = ? WHERE id = ?", (titulo, tarea_id))

        if "descripcion" in data:
            conn.execute(
                "UPDATE tareas SET descripcion = ? WHERE id = ?",
                (data.get("descripcion") or "", tarea_id),
            )

        if "completada" in data:
            conn.execute(
                "UPDATE tareas SET completada = ? WHERE id = ?",
                (1 if bool(data.get("completada")) else 0, tarea_id),
            )

        conn.commit()
        conn.close()
        return jsonify({"mensaje": "Tarea actualizada correctamente."}), 200

    conn.execute("DELETE FROM tareas WHERE id = ?", (tarea_id,))
    conn.commit()
    conn.close()
    return jsonify({"mensaje": "Tarea eliminada correctamente."}), 200


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
