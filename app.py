from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import os
import psycopg2
from urllib.parse import urlparse
import random
import string
import json
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import urllib.parse as urlparse

# 🔥 IMPORTANTE: SEM ISSO O FLASK NÃO FUNCIONA
app = Flask(__name__, template_folder=".")
app.secret_key = "uma_chave_secreta_qualquer"

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL não configurada no Render!")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    url = urlparse.urlparse(database_url)

    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )

    return conn

def fetchone_dict(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))

def fetchall_dict(cursor):
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# Middleware login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para acessar essa página.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

# Página inicial
@app.route("/")
def index():
    return render_template("index.html")

# Cadastro
@app.route("/signup", methods=["POST"])
def signup():
    nome = request.form.get("signup-name")
    email = request.form.get("signup-email")
    telefone = request.form.get("signup-phone")
    senha = request.form.get("signup-password")
    confirma_senha = request.form.get("signup-confirm-password")

    if senha != confirma_senha:
        flash("As senhas não coincidem!", "error")
        return redirect(url_for("index"))

    senha_hash = generate_password_hash(senha)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, telefone) VALUES (%s, %s, %s, %s)",
            (nome, email, senha_hash, telefone)
        )
        conn.commit()
        flash("Cadastro realizado com sucesso!", "success")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        flash("Email já cadastrado!", "error")
    except Exception as e:
        if conn: conn.rollback()
        print(f"Erro no cadastro: {e}")
        flash("Erro interno no servidor ao cadastrar.", "error")
    finally:
        if conn:
            cursor.close()
            conn.close()

    return redirect(url_for("index"))

# Login
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("login-email")
    senha = request.form.get("login-password")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nome, senha FROM usuarios WHERE email = %s", (email,))
    usuario = fetchone_dict(cursor)
    cursor.close()
    conn.close()

    if usuario and check_password_hash(usuario["senha"], senha):
        session["user_id"] = usuario["id_usuario"]
        session["user_name"] = usuario["nome"]
        flash(f"Bem-vindo, {usuario['nome']}!", "success")
        return redirect(url_for("dashboard"))
    else:
        flash("Email ou senha incorretos!", "error")
        return redirect(url_for("index"))

# Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM viagens WHERE id_criador = %s", (user_id,))
    viagens = fetchall_dict(cursor)

    cursor.execute("""
        SELECT d.* FROM destinos d
        JOIN viagens v ON d.id_destino = v.id_destino
        WHERE v.id_criador = %s
    """, (user_id,))
    destinos = fetchall_dict(cursor)

    cursor.execute("SELECT room_id FROM user_rooms WHERE user_id = %s", (user_id,))
    salas_user = [row[0] for row in cursor.fetchall()]

    tarefas_pendentes_count = 0
    enquetes_abertas_count = 0
    total_gastos = 0

    if salas_user:
        placeholders = ",".join(["%s"] * len(salas_user))

        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM tarefas
            WHERE status = 'pendente'
            AND room_id IN ({placeholders})
        """, salas_user)
        tarefas_pendentes_count = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM enquetes
            WHERE status = 'aberta'
            AND room_id IN ({placeholders})
        """, salas_user)
        enquetes_abertas_count = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT SUM(valor) AS total
            FROM gastos
            WHERE room_id IN ({placeholders})
        """, salas_user)

        result = cursor.fetchone()
        total_gastos = float(result[0]) if result and result[0] is not None else 0

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        viagens=viagens,
        destinos=destinos,
        tarefas_pendentes=tarefas_pendentes_count,
        enquetes_abertas=enquetes_abertas_count,
        total_gastos=total_gastos
    )

# 🔥 Rodar localmente
if __name__ == "__main__":
    app.run(debug=True)
