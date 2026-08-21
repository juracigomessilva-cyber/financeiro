import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

app.secret_key = 'chave_secreta_financeiro_segura'

# DEFINA A SUA SENHA AQUI
SENHA_CORRETA = "kadu2304@"  # Substitua pela sua senha

def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(db_url)
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logado'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Não autorizado"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id SERIAL PRIMARY KEY,
            data DATE NOT NULL,
            tipo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            valor NUMERIC NOT NULL,
            forma_pagamento TEXT NOT NULL
        );
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id SERIAL PRIMARY KEY,
            nome TEXT UNIQUE NOT NULL,
            tipo TEXT NOT NULL
        );
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM categorias;")
    if cursor.fetchone()[0] == 0:
        categorias_padrao = [
            ('Vendas / Serviços', 'Receita'),
            ('Salário / Proventos', 'Receita'),
            ('Outras Receitas', 'Receita'),
            ('Alimentação', 'Despesa'),
            ('Moradia / Aluguel', 'Despesa'),
            ('Transporte / Combustível', 'Despesa'),
            ('Contas Fixas (Água/Luz/Internet)', 'Despesa'),
            ('Lazer / Pessoal', 'Despesa'),
            ('Outras Despesas', 'Despesa')
        ]
        for nome, tipo in categorias_padrao:
            cursor.execute("INSERT INTO categorias (nome, tipo) VALUES (%s, %s);", (nome, tipo))

    conn.commit()
    cursor.close()
    conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        senha_digitada = request.form.get('senha')
        if senha_digitada == SENHA_CORRETA:
            session['logado'] = True
            return redirect(url_for('index'))
        else:
            erro = "Senha incorreta!"
    return render_template('login.html', erro=erro)

@app.route('/logout')
def logout():
    session.pop('logado', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

@app.route('/api/categorias', methods=['GET'])
@login_required
def listar_categorias():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM categorias ORDER BY tipo, nome;')
    categorias = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(categorias)

@app.route('/api/transacoes', methods=['POST'])
@login_required
def salvar_transacao():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transacoes (data, tipo, descricao, categoria, valor, forma_pagamento)
        VALUES (%s, %s, %s, %s, %s, %s);
    ''', (data['data'], data['tipo'], data['descricao'], data['categoria'], float(data['valor']), data['forma_pagamento']))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "sucesso"})

@app.route('/api/transacoes/<int:transacao_id>', methods=['DELETE'])
@login_required
def excluir_transacao(transacao_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM transacoes WHERE id = %s;', (transacao_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "sucesso"})

@app.route('/api/relatorio', methods=['GET'])
@login_required
def relatorio_financeiro():
    periodo = request.args.get('periodo', 'dia')
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    if periodo == 'dia':
        query_agrupado = '''
            SELECT 
                TO_CHAR(data, 'YYYY-MM-DD') as grupo,
                SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) as total_receita,
                SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) as total_despesa
            FROM transacoes
            GROUP BY data
            ORDER BY data DESC;
        '''
    elif periodo == 'semana':
        query_agrupado = '''
            SELECT 
                TO_CHAR(data, 'IYYY-"W"IW') as grupo,
                SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) as total_receita,
                SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) as total_despesa
            FROM transacoes
            GROUP BY grupo
            ORDER BY grupo DESC;
        '''
    else:  # mes
        query_agrupado = '''
            SELECT 
                TO_CHAR(data, 'YYYY-MM') as grupo,
                SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) as total_receita,
                SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) as total_despesa
            FROM transacoes
            GROUP BY grupo
            ORDER BY grupo DESC;
        '''

    cursor.execute(query_agrupado)
    agrupado = cursor.fetchall()

    cursor.execute("SELECT id, TO_CHAR(data, 'YYYY-MM-DD') as data, tipo, descricao, categoria, valor, forma_pagamento FROM transacoes ORDER BY data DESC, id DESC LIMIT 100;")
    detalhado = cursor.fetchall()

    cursor.close()
    conn.close()
    return jsonify({'agrupado': agrupado, 'detalhado': detalhado})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
