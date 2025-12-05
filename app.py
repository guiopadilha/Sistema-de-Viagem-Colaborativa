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

    # Buscar viagens do usuário
    cursor.execute("SELECT * FROM viagens WHERE id_criador = %s", (user_id,))
    viagens = fetchall_dict(cursor)

    # Buscar destinos das viagens
    cursor.execute("""
        SELECT d.* FROM destinos d
        JOIN viagens v ON d.id_destino = v.id_destino
        WHERE v.id_criador = %s
    """, (user_id,))
    destinos = fetchall_dict(cursor)

    # Buscar salas do usuário
    cursor.execute("SELECT room_id FROM user_rooms WHERE user_id = %s", (user_id,))
    salas_user = [row[0] for row in cursor.fetchall()]

    tarefas_pendentes_count = 0
    enquetes_abertas_count = 0
    total_gastos = 0

    if salas_user:
        placeholders = ",".join(["%s"] * len(salas_user))

        # Tarefas pendentes
        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM tarefas
            WHERE status = 'pendente'
            AND room_id IN ({placeholders})
        """, salas_user)
        result = cursor.fetchone()
        tarefas_pendentes_count = int(result[0]) if result and result[0] is not None else 0

        # Enquetes abertas
        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM enquetes
            WHERE status = 'aberta'
            AND room_id IN ({placeholders})
        """, salas_user)
        result = cursor.fetchone()
        enquetes_abertas_count = int(result[0]) if result and result[0] is not None else 0

        # Total de gastos
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

# Criar sala
@app.route("/criar_sala", methods=["POST"])
@login_required
def criar_sala():
    nome = request.form.get("nome")
    destino = request.form.get("destino")
    data_inicio = request.form.get("data_inicio")
    data_fim = request.form.get("data_fim")
    budget = request.form.get("budget")
    descricao = request.form.get("descricao")

    # Gerar código único da sala
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO rooms (id_criador, name, destination, start_date, end_date, budget, description, code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (session["user_id"], nome, destino, data_inicio, data_fim, budget, descricao, code))

        room_id = cursor.fetchone()[0]

        # Criador entra automaticamente
        cursor.execute("""
            INSERT INTO user_rooms (user_id, room_id)
            VALUES (%s, %s)
        """, (session["user_id"], room_id))

        conn.commit()

        flash(f"Sala criada com sucesso! Código: {code}", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        conn.rollback()
        print("Erro ao criar sala:", e)
        flash("Erro ao criar sala.", "error")
        return redirect(url_for("dashboard"))

    finally:
        cursor.close()
        conn.close()

# API para carregar salas do usuário no dashboard
@app.route("/get_rooms")
@login_required
def get_rooms():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Buscar IDs das salas onde o usuário participa
        cursor.execute("SELECT room_id FROM user_rooms WHERE user_id = %s", (session["user_id"],))
        salas_ids = [row[0] for row in cursor.fetchall()]

        if not salas_ids:
            return jsonify({"success": True, "rooms": []})

        placeholders = ",".join(["%s"] * len(salas_ids))

        # Buscar detalhes das salas
        cursor.execute(f"""
            SELECT id, name, destination, start_date, end_date, budget, description, code
            FROM rooms
            WHERE id IN ({placeholders})
        """, salas_ids)

        salas = fetchall_dict(cursor)

        cursor.close()
        conn.close()

        return jsonify({"success": True, "rooms": salas})

    except Exception as e:
        print("ERRO /get_rooms:", e)
        return jsonify({"success": False, "error": "Erro ao carregar salas do servidor"})


# Entrar em sala via código
@app.route("/entrar_sala", methods=["POST"])
@login_required
def entrar_sala():
    codigo = request.form.get("codigo")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar se o código existe
        cursor.execute("SELECT id FROM rooms WHERE code = %s", (codigo,))
        sala = cursor.fetchone()

        if not sala:
            flash("Código não encontrado!", "error")
            return redirect(url_for("dashboard"))

        room_id = sala[0]

        # Verificar se o usuário já está na sala
        cursor.execute("""
            SELECT 1 FROM user_rooms
            WHERE user_id = %s AND room_id = %s
        """, (session["user_id"], room_id))

        if cursor.fetchone():
            flash("Você já está nesta sala!", "info")
            return redirect(url_for("dashboard"))

        # Inserir usuário
        cursor.execute("""
            INSERT INTO user_rooms (user_id, room_id)
            VALUES (%s, %s)
        """, (session["user_id"], room_id))

        conn.commit()
        flash("Você entrou na sala com sucesso!", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        conn.rollback()
        print("Erro ao entrar na sala:", e)
        flash("Erro ao entrar na sala.", "error")
        return redirect(url_for("dashboard"))

    finally:
        cursor.close()
        conn.close()

# 🔥 Rodar localmente
if __name__ == "__main__":
    app.run(debug=True)

