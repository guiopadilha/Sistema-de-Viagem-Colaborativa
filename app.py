from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import os
import psycopg2
from urllib.parse import urlparse
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__, template_folder=".")
app.secret_key = "uma_chave_secreta_qualquer"

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL não configurada no Render!")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    url = urlparse(database_url)
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

# Páginas iniciais
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

# Signup/Login
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

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ======================
# Rotas API para AJAX
# ======================

# Criar sala
@app.route("/create_room", methods=["POST"])
@login_required
def create_room():
    data = request.get_json()
    nome = data.get("name")
    destino = data.get("destination")
    data_inicio = data.get("startDate")
    data_fim = data.get("endDate")
    budget = data.get("budget")
    descricao = data.get("description")

    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rooms (id_criador, name, destination, start_date, end_date, budget, description, code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (session["user_id"], nome, destino, data_inicio, data_fim, budget, descricao, code))
        room_id = cursor.fetchone()[0]

        # Criador entra automaticamente
        cursor.execute("INSERT INTO user_rooms (user_id, room_id) VALUES (%s, %s)", (session["user_id"], room_id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True, code=code)
    except Exception as e:
        print("Erro ao criar sala:", e)
        return jsonify(success=False), 500

# Buscar todas as salas do usuário
@app.route("/get_rooms")
@login_required
def get_rooms():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.name, r.destination, r.start_date, r.end_date, r.budget, r.description, r.code
            FROM rooms r
            JOIN user_rooms ur ON r.id = ur.room_id
            WHERE ur.user_id = %s
        """, (session["user_id"],))
        rooms = fetchall_dict(cursor)
        cursor.close()
        conn.close()
        return jsonify(rooms)
    except Exception as e:
        print("Erro ao buscar salas:", e)
        return jsonify([]), 500

# Buscar sala pelo código
@app.route("/get_room_by_code")
@login_required
def get_room_by_code():
    code = request.args.get("code")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rooms WHERE code = %s", (code,))
        room = fetchone_dict(cursor)
        cursor.close()
        conn.close()
        if room:
            return jsonify(success=True, room=room)
        else:
            return jsonify(success=False, error="Código não encontrado")
    except Exception as e:
        print("Erro get_room_by_code:", e)
        return jsonify(success=False, error="Erro interno"), 500

# Entrar em sala
@app.route("/join_room", methods=["POST"])
@login_required
def join_room():
    data = request.get_json()
    room_id = data.get("room_id")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Verifica se já está na sala
        cursor.execute("SELECT 1 FROM user_rooms WHERE user_id=%s AND room_id=%s", (session["user_id"], room_id))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO user_rooms (user_id, room_id) VALUES (%s, %s)", (session["user_id"], room_id))
            conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        print("Erro join_room:", e)
        return jsonify(success=False, error="Erro ao entrar na sala"), 500

# Deletar sala
@app.route("/delete_room", methods=["POST"])
@login_required
def delete_room():
    data = request.get_json()
    code = data.get("code")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Apaga relacionamento do usuário
        cursor.execute("""
            DELETE FROM user_rooms
            WHERE room_id = (SELECT id FROM rooms WHERE code=%s) AND user_id=%s
        """, (code, session["user_id"]))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        print("Erro delete_room:", e)
        return jsonify(success=False, error="Erro ao deletar sala"), 500

# 🔥 Rodar localmente
if __name__ == "__main__":
    app.run(debug=True)
