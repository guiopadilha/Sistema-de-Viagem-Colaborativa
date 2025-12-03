from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import os
# Importação para PostgreSQL
import psycopg2 
from urllib.parse import urlparse
import random
import string
import json
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Define o caminho absoluto da pasta atual
base_dir = os.path.abspath(os.path.dirname(__file__))

# Cria o app apontando templates e static para a mesma pasta
app = Flask(
    __name__,
    template_folder=base_dir,  # templates na mesma pasta
    static_folder=base_dir     # static também na mesma pasta
)
# A chave secreta deve ser lida de uma variável de ambiente em produção
app.secret_key = os.environ.get("SECRET_KEY", "sua_chave_secreta_default")

# --- CONFIGURAÇÃO DO BANCO DE DADOS POSTGRES ---
# A função agora lê as variáveis de ambiente (HOST, USER, PASSWORD, etc.) 
# que você configurou no Render ou tenta usar a DATABASE_URL.
def get_db_connection():
    # Use a DATABASE_URL do Render se estiver disponível
    db_url = os.environ.get("EXTERNAL_DATABASE_URL") or os.environ.get("INTERNAL_DATABASE_URL")

    if db_url:
        result = urlparse(db_url)
        # Conexão usando a URL formatada
        return psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
    else:
        # Fallback para configurações separadas (se DATABASE_URL não for usada)
        return psycopg2.connect(
            host=os.environ.get("Host", "localhost"), # Lembre-se de atualizar o Host/User/Pass no Render!
            database=os.environ.get("Database"),
            user=os.environ.get("User"),
            password=os.environ.get("Password"),
            port=os.environ.get("Port", 5432)
        )

# Função auxiliar para pegar dados como dicionário
def fetchone_dict(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))

def fetchall_dict(cursor):
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# Middleware para proteger rotas
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
        # PostgreSQL usa %s como placeholder, igual ao MySQL, mas a exceção muda
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, telefone) VALUES (%s, %s, %s, %s)",
            (nome, email, senha_hash, telefone)
        )
        conn.commit()
        flash("Cadastro realizado com sucesso!", "success")
    except psycopg2.errors.UniqueViolation: # Exceção específica do PostgreSQL para violação de chave única
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
    # No psycopg2, é mais simples usar fetchone_dict para pegar o resultado com nomes
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

    # Viagens criadas pelo usuário
    cursor.execute("SELECT * FROM viagens WHERE id_criador = %s", (user_id,))
    viagens = fetchall_dict(cursor)

    # Destinos das viagens
    cursor.execute("""
        SELECT d.* FROM destinos d
        JOIN viagens v ON d.id_destino = v.id_destino
        WHERE v.id_criador = %s
    """, (user_id,))
    destinos = fetchall_dict(cursor)

    # Salas em que o usuário participa
    cursor.execute("SELECT room_id FROM user_rooms WHERE user_id = %s", (user_id,))
    salas_user = [row[0] for row in cursor.fetchall()] # Pega apenas o room_id

    tarefas_pendentes_count = 0
    enquetes_abertas_count = 0
    total_gastos = 0

    if salas_user:
        # Usa %s na query e passa a lista salas_user no execute. Psycopg2 trata a lista.
        placeholders = ",".join(["%s"] * len(salas_user)) 

        # Contar tarefas pendentes
        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM tarefas
            WHERE status = 'pendente'
            AND room_id IN ({placeholders})
        """, salas_user)
        tarefas_pendentes_count = cursor.fetchone()[0]

        # Contar enquetes abertas
        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM enquetes
            WHERE status = 'aberta'
            AND room_id IN ({placeholders})
        """, salas_user)
        enquetes_abertas_count = cursor.fetchone()[0]

        # Somar total de gastos das salas do usuário
        cursor.execute(f"""
            SELECT SUM(valor) AS total
            FROM gastos
            WHERE room_id IN ({placeholders})
        """, salas_user)

        result = cursor.fetchone()
        # COALESCE é mais seguro no SQL para retornar 0, mas garantimos aqui também.
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
        # insere na tabela rooms, RETURNING id é a forma do Postgres de pegar o ID inserido
        cursor.execute("""
            INSERT INTO rooms (id_criador, name, destination, start_date, end_date, budget, description, code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (user_id, name, destination, start_date, end_date, budget, description, code))
        room_id = cursor.fetchone()[0] # Pega o ID retornado

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
    cursor = conn.cursor()
    cursor.execute("SELECT id, code FROM rooms WHERE code = %s", (code,))
    room = fetchone_dict(cursor)

    if not room:
        cursor.close()
        conn.close()
        flash("Código de sala inválido!", "error")
        return redirect(url_for("dashboard"))

    room_id = room["id"]

    # 🔹 Verifica se o usuário já entrou na sala
    cursor.execute("SELECT 1 FROM user_rooms WHERE user_id = %s AND room_id = %s", (user_id, room_id))
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
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rooms WHERE code = %s", (room_code,))
    room = fetchone_dict(cursor)
    cursor.close()
    conn.close()

    if not room:
        flash("Sala não encontrada!", "error")
        return redirect(url_for("dashboard"))

    return render_template("sala.html", room=room)


@app.route('/get_rooms')
def get_rooms():
    user_id = session.get('user_id') 
    if not user_id:
        return jsonify([])

    conn = get_db_connection()
    cursor = conn.cursor()

    # Seleciona todas as salas que o usuário criou
    query_criadas = "SELECT *, id AS room_id FROM rooms WHERE id_criador = %s"
    cursor.execute(query_criadas, (user_id,))
    salas_criadas = fetchall_dict(cursor)

    # Seleciona todas as salas que o usuário entrou via código
    query_user_rooms = """
        SELECT r.*, ur.id AS user_room_id, r.id AS room_id
        FROM user_rooms ur
        JOIN rooms r ON ur.room_id = r.id
        WHERE ur.user_id = %s
    """
    cursor.execute(query_user_rooms, (user_id,))
    salas_entradas = fetchall_dict(cursor)

    # Junta as duas listas sem duplicar
    todas_salas = {room['room_id']: room for room in salas_criadas + salas_entradas}
    rooms_list = list(todas_salas.values())

    cursor.close()
    conn.close()
    return jsonify(rooms_list)

@app.route('/delete_room', methods=['POST'])
def delete_room():
    user_id = session.get('user_id') 
    data = request.get_json()
    code = data.get('code')

    if not user_id:
        return jsonify({'success': False, 'error': 'Usuário não logado.'})

    conn = get_db_connection()
    cursor = conn.cursor()

    # Verifica se o usuário é criador da sala
    cursor.execute("SELECT id, id_criador FROM rooms WHERE code = %s", (code,))
    room = fetchone_dict(cursor)

    if not room:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Sala não encontrada.'})

    try:
        if room['id_criador'] == user_id:
            # Usuário é criador → pode excluir completamente
            cursor.execute("DELETE FROM user_rooms WHERE room_id = %s", (room['id'],))
            cursor.execute("DELETE FROM rooms WHERE id = %s", (room['id'],))
            conn.commit()
            return jsonify({'success': True})
        else:
            # Usuário não é criador → apenas remove da user_rooms
            cursor.execute("DELETE FROM user_rooms WHERE room_id = %s AND user_id = %s", (room['id'], user_id))
            conn.commit()
            return jsonify({'success': True, 'message': 'Você saiu da sala, mas não pode apagar pois não é criador.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route("/get_room_by_code", methods=["GET"])
def get_room_by_code():
    code = request.args.get("code", "").upper()
    user_id = session.get("user_id") 

    if not user_id:
        return jsonify({"success": False, "error": "Usuário não logado."})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Busca a sala pelo código
        cursor.execute("SELECT * FROM rooms WHERE code = %s", (code,))
        room = fetchone_dict(cursor)
        if not room:
            return jsonify({"success": False, "error": "Sala não encontrada."})

        # Verifica se já existe na tabela user_rooms
        cursor.execute(
            "SELECT 1 FROM user_rooms WHERE user_id = %s AND room_id = %s",
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
            # PostgreSQL trata datas/horários de forma diferente; converta para string se necessário
            "startDate": str(room["start_date"]), 
            "endDate": str(room["end_date"]),
            # COALESCE no SQL é melhor, mas garantindo a conversão aqui
            "budget": float(room["budget"]) if room["budget"] else 0, 
            "description": room["description"],
            "code": room["code"]
        }})

    except Exception as e:
        print("Erro:", e)
        conn.rollback()
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
    cursor = conn.cursor()

    # Buscar dados da sala
    cursor.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
    sala = fetchone_dict(cursor)

    # Buscar participantes da sala
    cursor.execute("""
        SELECT u.nome
        FROM user_rooms ur
        JOIN usuarios u ON u.id_usuario = ur.user_id
        WHERE ur.room_id = %s
    """, (room_id,))
    participantes = fetchall_dict(cursor)

    # Buscar roteiros da sala
    cursor.execute("""
        SELECT * FROM roteiros
        WHERE room_id = %s
        ORDER BY dia, horario_inicio
    """, (room_id,))
    roteiros = fetchall_dict(cursor)

    conn.close()

    if not sala:
        return "Sala não encontrada", 404

    return render_template(
        'sala.html',
        sala=sala,
        participantes=participantes,
        roteiros=roteiros,
        room_id=room_id  
    )

# 🟢 Rota de adicionar roteiro corrigida para usar get_db_connection()
@app.route('/adicionar_roteiro', methods=['POST'])
def adicionar_roteiro():
    room_id = request.form.get('room_id')
    dia = request.form.get('dia')
    descricao = request.form.get('descricao')
    horario_inicio = request.form.get('horario_inicio')
    horario_fim = request.form.get('horario_fim')

    if not room_id or not dia or not descricao:
        return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO roteiros (room_id, dia, descricao, horario_inicio, horario_fim)
            VALUES (%s, %s, %s, %s, %s)
        """, (room_id, dia, descricao, horario_inicio, horario_fim))

        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        print("Erro ao adicionar roteiro:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 🟢 Rota de editar roteiro corrigida para usar get_db_connection()
@app.route('/editar_roteiro/<int:roteiro_id>', methods=['POST'])
def editar_roteiro(roteiro_id):
    data = request.get_json()
    dia = data.get('dia')
    descricao = data.get('descricao')
    horario_inicio = data.get('inicio')
    horario_fim = data.get('fim')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE roteiros
            SET dia = %s, descricao = %s, horario_inicio = %s, horario_fim = %s
            WHERE id = %s
        """, (dia, descricao, horario_inicio, horario_fim, roteiro_id))

        conn.commit()
        return jsonify({'success': True, 'message': 'Roteiro atualizado com sucesso!'})
    except Exception as e:
        conn.rollback()
        print("Erro ao editar roteiro:", e)
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 🟢 Rota de excluir roteiro corrigida para usar get_db_connection()
@app.route('/excluir_roteiro', methods=['POST'])
def excluir_roteiro():
    id = request.form.get('id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM roteiros WHERE id = %s", (id,))
        conn.commit()
        return jsonify({'message': 'Roteiro excluído com sucesso!'})
    except Exception as e:
        conn.rollback()
        print("Erro ao excluir roteiro:", e)
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/sala/<int:room_id>")
def sala_view(room_id):
    return render_template("sala.html", currentRoomId=room_id)

# ➕ Criar tarefa
@app.route("/add_tarefa", methods=["POST"])
def add_tarefa():
    data = request.get_json()
    room_id = data.get("room_id")
    titulo = data.get("titulo")
    responsavel = data.get("responsavel", "")
    descricao = data.get("descricao", "")
    prazo = data.get("prazo")
    status = data.get("status", "pendente")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO tarefas (room_id, titulo, descricao, responsavel, prazo, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (room_id, titulo, descricao, responsavel, prazo, status))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        print("Erro ao adicionar tarefa:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route("/get_tarefas/<int:room_id>")
def get_tarefas(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM tarefas
        WHERE room_id = %s
        ORDER BY prazo ASC, criado_em DESC
    """, (room_id,))
    tarefas = fetchall_dict(cursor)
    cursor.close()
    conn.close()
    return jsonify(tarefas)

# 🔄 Atualizar status da tarefa
@app.route("/atualizar_tarefa_status/<int:id>", methods=["PUT"])
def atualizar_tarefa_status(id):
    data = request.get_json()
    status = data.get("status")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE tarefas SET status=%s WHERE id=%s", (status, id))
        conn.commit()
        return jsonify({"success": True, "message": "Status atualizado com sucesso!"})
    except Exception as e:
        conn.rollback()
        print("Erro ao atualizar status:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/delete_tarefa/<int:id>", methods=["DELETE"])
def delete_tarefa(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM tarefas WHERE id = %s", (id,))
        conn.commit()
        return jsonify({"success": True, "message": "Tarefa removida com sucesso!"})
    except Exception as e:
        conn.rollback()
        print("Erro ao excluir tarefa:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Rota duplicada (tarefa_status), mantendo a lógica de sucesso
@app.route("/tarefa_status/<int:tarefa_id>", methods=["POST"])
def tarefa_status(tarefa_id):
    try:
        novo_status = request.form.get("status")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tarefas SET status = %s WHERE id = %s",
            (novo_status, tarefa_id)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"success": True, "status": novo_status})
    except Exception as e:
        print("❌ Erro ao atualizar status:", e)
        return jsonify({"success": False, "error": str(e)}), 500

# Rota duplicada (update_tarefa_status), corrigida para usar get_db_connection()
@app.route("/update_tarefa_status/<int:id>", methods=["PUT"])
def update_tarefa_status(id):
    data = request.get_json()
    novo_status = data.get("status")

    try:
        conn = get_db_connection() # Correção: usar a função correta
        cursor = conn.cursor()
        cursor.execute("UPDATE tarefas SET status = %s WHERE id = %s", (novo_status, id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print("Erro ao atualizar status:", e)
        return jsonify({"success": False}), 500

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

    if not room_id or not descricao or not valor or not data_gasto:
        return jsonify({"status": "error", "message": "Preencha todos os campos obrigatórios."}), 400

    try:
        room_id = int(room_id)
        valor = float(valor)
    except ValueError:
        return jsonify({"status": "error", "message": "Valores inválidos para room_id ou valor."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO gastos (room_id, descricao, valor, data_gasto, categoria, pago_por)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (room_id, descricao, valor, data_gasto, categoria, pago_por))
        conn.commit()
        return jsonify({"status": "success", "message": "Gasto adicionado com sucesso!"})
    except Exception as e:
        conn.rollback()
        print("Erro ao adicionar gasto:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 📤 Listar gastos
@app.route("/get_gastos/<int:room_id>")
def get_gastos(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM gastos
        WHERE room_id = %s
        ORDER BY data_gasto DESC
    """, (room_id,))
    gastos = fetchall_dict(cursor)
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
    try:
        cursor.execute("DELETE FROM gastos WHERE id = %s", (gasto_id,))
        conn.commit()
        return jsonify({"status": "success", "message": "Gasto excluído com sucesso!"})
    except Exception as e:
        conn.rollback()
        print("Erro ao excluir gasto:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/tempo_real")
def tempo_real():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Conta o total de roteiros
    cursor.execute("SELECT COUNT(*) AS total FROM roteiros")
    total_roteiros = cursor.fetchone()[0] or 0

    # Soma o total de gastos (Usando COALESCE para garantir 0 se não houver registros)
    cursor.execute("SELECT COALESCE(SUM(valor), 0) AS total FROM gastos")
    total_gastos = float(cursor.fetchone()[0])

    cursor.close()
    conn.close()

    return render_template(
        "tempo_real.html",
        total_roteiros=total_roteiros,
        total_gastos=total_gastos
    )
    
@app.route("/criar_enquete", methods=["POST"])
def criar_enquete():
    data = request.get_json()
    # ... (lógica de coleta de dados e validação)
    room_id = data.get("room_id")
    titulo = data.get("titulo")
    descricao = data.get("descricao") or ""
    opcoes = data.get("opcoes", [])
    status = data.get("status", "aberta")

    if not room_id or not titulo or not opcoes:
        return jsonify({"success": False, "message": "Preencha todos os campos obrigatórios."}), 400

    try:
        room_id = int(room_id)
    except ValueError:
        return jsonify({"success": False, "message": "room_id inválido."}), 400

    opcoes_json = json.dumps([opcao.strip() for opcao in opcoes if opcao.strip() != ""])

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO enquetes (room_id, titulo, descricao, opcoes, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (room_id, titulo, descricao, opcoes_json, status))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": "Erro ao salvar enquete.", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify({"success": True, "message": "Enquete criada com sucesso!"})


@app.route("/enquetes/<int:room_id>")
def listar_enquetes(room_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor() # Usamos cursor simples para o fetchone/fetchall

        # busca as enquetes
        cursor.execute("SELECT * FROM enquetes WHERE room_id = %s ORDER BY criado_em DESC", (room_id,))
        enquetes = fetchall_dict(cursor)

        # para cada enquete, buscar votos agrupados
        for e in enquetes:
            enquete_id = e["id"]
            opcoes = json.loads(e["opcoes"])

            cursor_votos = conn.cursor()
            cursor_votos.execute("""
                SELECT opcao_idx, COUNT(*) 
                FROM votos 
                WHERE enquete_id = %s 
                GROUP BY opcao_idx
            """, (enquete_id,))
            votos_db = cursor_votos.fetchall()
            cursor_votos.close()

            # cria vetor de votos do tamanho das opções
            votos = [0] * len(opcoes)
            for row in votos_db:
                idx, count = row
                votos[idx] = count

            # adiciona ao objeto que vai pro front
            e["opcoes"] = opcoes
            e["votos"] = votos

        cursor.close()
        conn.close()

        return jsonify({"success": True, "enquetes": enquetes})

    except Exception as e:
        print("Erro ao buscar enquetes:", e)
        return jsonify({"success": False, "message": "Erro ao buscar enquetes"})

@app.route("/votar_enquete/<int:enquete_id>", methods=["POST"])
def votar_enquete(enquete_id):
    data = request.get_json()
    opcao_idx = data.get("opcao_idx")

    if opcao_idx is None:
        return jsonify({"success": False, "message": "Índice da opção não enviado"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO votos (enquete_id, opcao_idx)
            VALUES (%s, %s)
        """, (enquete_id, opcao_idx))

        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/excluir_enquete/<int:enquete_id>", methods=["DELETE"])
def excluir_enquete(enquete_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Exclui votos relacionados
        cursor.execute("DELETE FROM votos WHERE enquete_id = %s", (enquete_id,))

        # Exclui a enquete
        cursor.execute("DELETE FROM enquetes WHERE id = %s", (enquete_id,))

        conn.commit()
        return jsonify({"success": True, "message": "Enquete excluída com sucesso!"})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": "Erro ao excluir enquete", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
    
@app.route("/get_dashboard_totals/<int:room_id>")
def get_dashboard_totals(room_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔹 Total de roteiros
    cursor.execute("SELECT COUNT(*) FROM roteiros WHERE room_id = %s", (room_id,))
    total_roteiros = cursor.fetchone()[0]

    # 🔹 Total de tarefas pendentes
    cursor.execute("SELECT COUNT(*) FROM tarefas WHERE room_id = %s AND status = 'pendente'", (room_id,))
    total_pendentes = cursor.fetchone()[0]

    # 🔹 Total de enquetes abertas
    cursor.execute("SELECT COUNT(*) FROM enquetes WHERE room_id = %s AND status = 'aberta'", (room_id,))
    total_enquetes = cursor.fetchone()[0]

    # 🔹 Total de gastos (Usando COALESCE no SQL para garantir 0 se não houver registros)
    cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM gastos WHERE room_id = %s", (room_id,))
    total_gastos = float(cursor.fetchone()[0])

    cursor.close()
    conn.close()

    return jsonify({
        "total_roteiros": total_roteiros,
        "total_pendentes": total_pendentes,
        "total_enquetes": total_enquetes,
        "total_gastos": total_gastos
    })


if __name__ == "__main__":
    app.run(debug=True)
