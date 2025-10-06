from flask import Flask, render_template, request, redirect, url_for,jsonify, flash, session
import os
import mysql.connector
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash

# Define o caminho absoluto da pasta atual
base_dir = os.path.abspath(os.path.dirname(__file__))

# Cria o app apontando templates e static para a mesma pasta
app = Flask(
    __name__,
    template_folder=base_dir,  # templates na mesma pasta
    static_folder=base_dir      # static também na mesma pasta
)
app.secret_key = "sua_chave_secreta"

# Configuração do banco de dados
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
    from functools import wraps
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

# Dashboard
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

    cursor.close()
    conn.close()

    return render_template("dashboard.html", viagens=viagens, destinos=destinos)
@app.route("/check_email", methods=["POST"])
def check_email():
    email = request.form.get("email")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE email = %s", (email,))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    if count > 0:
        return "EXISTS"
    else:
        return "OK"

# Logout
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "success")
    return redirect(url_for("index"))


@app.route("/create_room", methods=["POST"])
@login_required
def create_room():
    data = request.get_json()  # pega os dados enviados pelo fetch
    user_id = session["user_id"]
    name = data.get("name")
    destination = data.get("destination")
    start_date = data.get("startDate")
    end_date = data.get("endDate")
    budget = data.get("budget")
    description = data.get("description")

    # Gera um código de 6 caracteres
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO rooms (id_criador, name, destination, start_date, end_date, budget, description, code)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (user_id, name, destination, start_date, end_date, budget, description, code))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True, "code": code})


# ---------------------- ENTRAR NA SALA ----------------------
@app.route("/enter_room", methods=["POST"])
@login_required
def enter_room():
    code = request.form.get("code", "").strip().upper()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rooms WHERE code = %s", (code,))
    room = cursor.fetchone()
    cursor.close()
    conn.close()

    if room:
        return redirect(url_for("sala", room_code=room["code"]))
    else:
        flash("Código de sala inválido!", "error")
        return redirect(url_for("dashboard"))

# ---------------------- PÁGINA DA SALA ----------------------
@app.route("/sala/<room_code>")
@login_required
def sala(room_code):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rooms WHERE code = %s", (room_code,))
    room = cursor.fetchone()
    cursor.close()
    conn.close()

    if not room:
        flash("Sala não encontrada!", "error")
        return redirect(url_for("dashboard"))

    return render_template("sala.html", room=room)

@app.route("/get_rooms")
@login_required
def get_rooms():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rooms WHERE id_criador = %s", (user_id,))
    rooms = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rooms)

if __name__ == "__main__":
    app.run(debug=True)

