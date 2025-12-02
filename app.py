from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import os
import mysql.connector
import random
import string
import json
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ----------------------------------------
# Configurações do Flask
# ----------------------------------------
base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=base_dir,  # templates na mesma pasta
    static_folder=base_dir     # static também na mesma pasta
)
app.secret_key = os.environ.get("SECRET_KEY", "sua_chave_secreta")

# ----------------------------------------
# Configuração do banco de dados via variáveis de ambiente
# ----------------------------------------
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "viagens_colegas")
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ----------------------------------------
# Middleware de login
# ----------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para acessar essa página.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

# ----------------------------------------
# Rotas principais
# ----------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------------- CADASTRO ----------------------
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

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, telefone) VALUES (%s, %s, %s, %s)",
            (nome, email, senha_hash, telefone)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Cadastro realizado com sucesso!", "success")
    except mysql.connector.IntegrityError:
        flash("Email já cadastrado!", "error")
    except Exception as e:
        flash(f"Erro ao cadastrar: {str(e)}", "error")

    return redirect(url_for("index"))

# ---------------------- LOGIN ----------------------
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("login-email")
    senha = request.form.get("login-password")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    usuario = cursor.fetchone()
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

# ---------------------- DASHBOARD ----------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM viagens WHERE id_criador = %s", (user_id,))
    viagens = cursor.fetchall()

    cursor.execute("""
        SELECT d.* FROM destinos d
        JOIN viagens v ON d.id_destino = v.id_destino
        WHERE v.id_criador = %s
    """, (user_id,))
    destinos = cursor.fetchall()

    # Salas do usuário
    cursor.execute("SELECT room_id FROM user_rooms WHERE user_id = %s", (user_id,))
    salas_user = cursor.fetchall()
    room_ids = [s["room_id"] for s in salas_user]

    tarefas_pendentes_count = enquetes_abertas_count = total_gastos = 0

    if room_ids:
        placeholders = ",".join(["%s"] * len(room_ids))

        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM tarefas
            WHERE status = 'pendente'
            AND room_id IN ({placeholders})
        """, room_ids)
        tarefas_pendentes_count = cursor.fetchone()["total"]

        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM enquetes
            WHERE status = 'aberta'
            AND room_id IN ({placeholders})
        """, room_ids)
        enquetes_abertas_count = cursor.fetchone()["total"]

        cursor.execute(f"""
            SELECT SUM(valor) AS total
            FROM gastos
            WHERE room_id IN ({placeholders})
        """, room_ids)
        result = cursor.fetchone()
        total_gastos = result["total"] if result["total"] is not None else 0

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

# ---------------------- LOGOUT ----------------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "success")
    return redirect(url_for("index"))

# ----------------------------------------
# Aqui você pode continuar adicionando todas as outras rotas
# (criação de salas, tarefas, roteiros, gastos, enquetes)
# ----------------------------------------

# ----------------------------------------
# Rodar app
# ----------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
