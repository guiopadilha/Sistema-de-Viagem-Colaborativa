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
def create_room():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Usuário não logado"})

    data = request.json
    name = data.get("name")
    destination = data.get("destination")
    start_date = data.get("startDate")
    end_date = data.get("endDate")
    budget = data.get("budget")
    description = data.get("description")
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # insere na tabela rooms
        cursor.execute("""
            INSERT INTO rooms (id_criador, name, destination, start_date, end_date, budget, description, code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, name, destination, start_date, end_date, budget, description, code))
        room_id = cursor.lastrowid

        # insere na user_rooms para associar ao usuário
        cursor.execute("""
            INSERT INTO user_rooms (user_id, room_id) VALUES (%s, %s)
        """, (user_id, room_id))

        conn.commit()
        return jsonify({"success": True, "code": code})
    except Exception as e:
        conn.rollback()
        print("Erro:", e)
        return jsonify({"success": False, "error": str(e)})
    finally:
        cursor.close()
        conn.close()



# ---------------------- ENTRAR NA SALA ----------------------
@app.route("/enter_room", methods=["POST"])
@login_required
def enter_room():
    code = request.form.get("code", "").strip().upper()
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rooms WHERE code = %s", (code,))
    room = cursor.fetchone()

    if not room:
        cursor.close()
        conn.close()
        flash("Código de sala inválido!", "error")
        return redirect(url_for("dashboard"))

    room_id = room["id"]

    # 🔹 Verifica se o usuário já entrou na sala
    cursor.execute("SELECT * FROM user_rooms WHERE user_id = %s AND room_id = %s", (user_id, room_id))
    already_joined = cursor.fetchone()

    # 🔹 Se ainda não estiver, insere a relação
    if not already_joined:
        cursor.execute("INSERT INTO user_rooms (user_id, room_id) VALUES (%s, %s)", (user_id, room_id))
        conn.commit()

    cursor.close()
    conn.close()

    # Redireciona normalmente para a sala
    return redirect(url_for("sala", room_code=room["code"]))


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




@app.route('/get_rooms')
def get_rooms():
    user_id = session.get('user_id', 1)  # substitua pela lógica real do login

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Seleciona todas as salas que o usuário criou
    query_criadas = "SELECT *, id AS room_id FROM rooms WHERE id_criador = %s"
    cursor.execute(query_criadas, (user_id,))
    salas_criadas = cursor.fetchall()

    # Seleciona todas as salas que o usuário entrou via código
    query_user_rooms = """
        SELECT r.*, ur.id AS user_room_id
        FROM user_rooms ur
        JOIN rooms r ON ur.room_id = r.id
        WHERE ur.user_id = %s
    """
    cursor.execute(query_user_rooms, (user_id,))
    salas_entradas = cursor.fetchall()

    # Junta as duas listas sem duplicar (evita repetir salas que o usuário criou e também entrou)
    todas_salas = {room['id']: room for room in salas_criadas + salas_entradas}
    rooms_list = list(todas_salas.values())

    cursor.close()
    conn.close()
    return jsonify(rooms_list)

@app.route('/delete_room', methods=['POST'])
def delete_room():
    user_id = session.get('user_id', 1)  # ou sua lógica real de login
    data = request.get_json()
    code = data.get('code')

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Verifica se o usuário é criador da sala
    cursor.execute("SELECT id, id_criador FROM rooms WHERE code = %s", (code,))
    room = cursor.fetchone()

    if not room:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Sala não encontrada.'})

    if room['id_criador'] == user_id:
        # Usuário é criador → pode excluir completamente
        cursor.execute("DELETE FROM user_rooms WHERE room_id = %s", (room['id'],))
        cursor.execute("DELETE FROM rooms WHERE id = %s", (room['id'],))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    else:
        # Usuário não é criador → apenas remove da user_rooms
        cursor.execute("DELETE FROM user_rooms WHERE room_id = %s AND user_id = %s", (room['id'], user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Você saiu da sala, mas não pode apagar pois não é criador.'})


@app.route("/get_room_by_code", methods=["GET"])
def get_room_by_code():
    code = request.args.get("code", "").upper()
    user_id = session.get("user_id")  # supondo que você salva o ID do usuário na sessão

    if not user_id:
        return jsonify({"success": False, "error": "Usuário não logado."})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Busca a sala pelo código
        cursor.execute("SELECT * FROM rooms WHERE code = %s", (code,))
        room = cursor.fetchone()
        if not room:
            return jsonify({"success": False, "error": "Sala não encontrada."})

        # Verifica se já existe na tabela user_rooms
        cursor.execute(
            "SELECT * FROM user_rooms WHERE user_id = %s AND room_id = %s",
            (user_id, room['id'])
        )
        exists = cursor.fetchone()

        if not exists:
            # Insere na tabela user_rooms
            cursor.execute(
                "INSERT INTO user_rooms (user_id, room_id) VALUES (%s, %s)",
                (user_id, room['id'])
            )
            conn.commit()

        # Retorna a sala para o frontend
        return jsonify({"success": True, "room": {
            "id": room["id"],
            "name": room["name"],
            "destination": room["destination"],
            "startDate": str(room["start_date"]),
            "endDate": str(room["end_date"]),
            "budget": float(room["budget"]) if room["budget"] else 0,
            "description": room["description"],
            "code": room["code"]
        }})

    except Exception as e:
        print("Erro:", e)
        return jsonify({"success": False, "error": "Erro no servidor."})
    finally:
        cursor.close()
        conn.close()


@app.route('/sala')
def pagina_sala_123():
    return render_template('sala.html')
@app.route('/sala/<int:room_id>')
def pagina_sala_especifica(room_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Buscar dados da sala
    cursor.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
    sala = cursor.fetchone()

    # Buscar participantes da sala
    cursor.execute("""
        SELECT u.nome
        FROM user_rooms ur
        JOIN usuarios u ON u.id_usuario = ur.user_id
        WHERE ur.room_id = %s
    """, (room_id,))
    participantes = cursor.fetchall()

    # Buscar roteiros da sala
    cursor.execute("""
        SELECT * FROM roteiros
        WHERE room_id = %s
        ORDER BY dia, horario_inicio
    """, (room_id,))
    roteiros = cursor.fetchall()

    conn.close()

    if not sala:
        return "Sala não encontrada", 404

    return render_template(
        'sala.html',
        sala=sala,
        participantes=participantes,
        roteiros=roteiros,
        room_id=room_id   # 🔹 adicionando aqui
    )


@app.route('/adicionar_roteiro', methods=['POST'])
def adicionar_roteiro():
    room_id = request.form.get('room_id')
    dia = request.form.get('dia')
    descricao = request.form.get('descricao')
    horario_inicio = request.form.get('horario_inicio')
    horario_fim = request.form.get('horario_fim')

    # validação mínima
    if not room_id or not dia or not descricao:
        return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400

    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='12345678',
        database='viagens_colegas'
    )
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO roteiros (room_id, dia, descricao, horario_inicio, horario_fim)
        VALUES (%s, %s, %s, %s, %s)
    """, (room_id, dia, descricao, horario_inicio, horario_fim))

    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})

@app.route('/editar_roteiro/<int:roteiro_id>', methods=['POST'])
def editar_roteiro(roteiro_id):
    data = request.get_json()
    dia = data.get('dia')
    descricao = data.get('descricao')
    horario_inicio = data.get('inicio')
    horario_fim = data.get('fim')

    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='12345678',
        database='viagens_colegas'
    )
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE roteiros
        SET dia = %s, descricao = %s, horario_inicio = %s, horario_fim = %s
        WHERE id = %s
    """, (dia, descricao, horario_inicio, horario_fim, roteiro_id))

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Roteiro atualizado com sucesso!'})


@app.route('/excluir_roteiro', methods=['POST'])
def excluir_roteiro():
    id = request.form.get('id')

    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='12345678',
        database='viagens_colegas'
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM roteiros WHERE id = %s", (id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Roteiro excluído com sucesso!'})


@app.route("/tarefas/<int:room_id>", methods=["GET"])
@login_required
def listar_tarefas_room(room_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Tarefas da sala
    cursor.execute("""
        SELECT t.id, t.descricao, t.responsavel_id, u.nome AS responsavel_nome, t.status
        FROM tarefas t
        LEFT JOIN usuarios u ON t.responsavel_id = u.id_usuario
        WHERE t.room_id = %s
        ORDER BY t.created_at ASC
    """, (room_id,))
    tarefas = cursor.fetchall()

    # Usuários da sala
    cursor.execute("""
        SELECT u.id_usuario, u.nome
        FROM user_rooms ur
        JOIN usuarios u ON ur.user_id = u.id_usuario
        WHERE ur.room_id = %s
    """, (room_id,))
    usuarios_sala = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({"tarefas": tarefas, "usuarios_sala": usuarios_sala})

# Função de conexão
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='12345678',
        database='viagens_colegas'
    )

# 📥 Adicionar gasto
@app.route("/add_gasto", methods=["POST"])
def add_gasto():
    # Recebe dados via form-data
    room_id = request.form.get("room_id")
    descricao = request.form.get("descricao")
    valor = request.form.get("valor")
    data_gasto = request.form.get("data_gasto")
    categoria = request.form.get("categoria")
    pago_por = request.form.get("pago_por") or ""

    # Validação mínima
    if not room_id or not descricao or not valor or not data_gasto:
        return jsonify({"status": "error", "message": "Preencha todos os campos obrigatórios."}), 400

    try:
        # Conversão de tipos
        room_id = int(room_id)
        valor = float(valor)
    except ValueError:
        return jsonify({"status": "error", "message": "Valores inválidos para room_id ou valor."}), 400

    # Inserção no banco
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gastos (room_id, descricao, valor, data_gasto, categoria, pago_por)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (room_id, descricao, valor, data_gasto, categoria, pago_por))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": "Gasto adicionado com sucesso!"})

# 📤 Listar gastos
@app.route("/get_gastos/<int:room_id>")
def get_gastos(room_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT *
        FROM gastos
        WHERE room_id = %s
        ORDER BY data_gasto DESC
    """, (room_id,))
    gastos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(gastos)

@app.route("/excluir_gasto", methods=["POST"])
def excluir_gasto():
    gasto_id = request.form.get("id")
    
    if not gasto_id:
        return jsonify({"status": "error", "message": "ID do gasto não fornecido"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos WHERE id = %s", (gasto_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": "Gasto excluído com sucesso!"})
@app.route("/tempo_real")
def tempo_real():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Conta o total de roteiros
    cursor.execute("SELECT COUNT(*) AS total FROM roteiros")
    total_roteiros = cursor.fetchone()["total"] or 0

    # Soma o total de gastos
    cursor.execute("SELECT SUM(valor) AS total FROM gastos")
    total_gastos = cursor.fetchone()["total"] or 0

    cursor.close()
    conn.close()

    return render_template(
        "tempo_real.html",
        total_roteiros=total_roteiros,
        total_gastos=total_gastos
    )


if __name__ == "__main__":
    app.run(debug=True)
