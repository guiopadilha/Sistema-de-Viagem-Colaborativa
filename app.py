
@app.route('/sala')
def pagina_sala_123():
    return render_template('sala.html')
@app.route('/sala/<int:room_id>')
def pagina_sala_especifica(room_id):
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='12345678',
        database='viagens_colegas'
    )
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
        roteiros=roteiros
    )

