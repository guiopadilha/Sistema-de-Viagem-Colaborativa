from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import mysql.connector
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Caminho absoluto da pasta atual
base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=base_dir,  # templates na mesma pasta
    static_folder=base_dir     # static na mesma pasta
)
app.secret_key = "sua_chave_secreta"

# Configuração do banco
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "12345678",
    "database": "viagens_colegas"
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Middleware para proteger rotas
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para acessar essa página.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

# --------------------- ROTAS ---------------------

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

    return redirect(url_for("index"))

# Login
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

# Logout
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "success")
    return redirect(url_for("index"))

# Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Viagens do usuário
    cursor.execute("SELECT * FROM viagens WHERE id_criador = %s", (user_id,))
    viagens = cursor.fetchall()

    # Destinos
    cursor.execute("""
        SELECT d.* FROM destinos d
        JOIN viagens v ON d.id_destino = v.id_destino
        WHERE v.id_criador = %s
    """, (user_id,))
    destinos = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("dashboard.html", viagens=viagens, destinos=destinos)

# Sala específica
@app.route("/sala/<int:room_id>")
@login_required
def sala(room_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Sala
    cursor.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
    sala = cursor.fetchone()

    if not sala:
        cursor.close()
        conn.close()
        flash("Sala não encontrada!", "error")
        return redirect(url_for("dashboard"))

    # Participantes
    cursor.execute("""
        SELECT u.nome
        FROM user_rooms ur
        JOIN usuarios u ON u.id_usuario = ur.user_id
        WHERE ur.room_id = %s
    """, (room_id,))
    participantes = cursor.fetchall()

    # Roteiros
    cursor.execute("""
        SELECT * FROM roteiros
        WHERE room_id = %s
        ORDER BY dia, horario_inicio
    """, (room_id,))
    roteiros = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("sala.html", sala=sala, participantes=participantes, roteiros=roteiros)

# --------------------- RODAS DE UTILITÁRIOS ---------------------

@app.route("/check_email", methods=["POST"])
def check_email():
    email = request.form.get("email")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE email = %s", (email,))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return "EXISTS" if count > 0 else "OK"

# Teste simples de render
@app.route("/teste")
@login_required
def teste():
    return render_template("index.html", message="Se você está vendo isso, funciona no Render!")

# --------------------- EXECUÇÃO ---------------------
if __name__ == "__main__":
    app.run(debug=True)
