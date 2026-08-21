import sqlite3
import shutil
import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session

app = Flask(__name__)

# Chave secreta obrigatória para gerenciar a sessão de login
app.secret_key = 'chave_secreta_financeiro_segura'

# DEFINA A SUA SENHA AQUI
SENHA_CORRETA = "admin123"

# --- DECORADOR DE PROTEÇÃO DE ROTAS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logado'):
            # Se for uma requisição de API (AJAX), retorna erro HTTP 401
            if request.path.startswith('/api/'):
                return jsonify({"error": "Não autorizado"}), 401
            # Se for navegação normal, redireciona para a página de login
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    conn = sqlite3.connect('financeiro.db')
    cursor = conn.cursor()
    
    # Tabela de Transações (Entradas e Saídas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data DATE NOT NULL,
            tipo TEXT NOT NULL, -- 'Receita' ou 'Despesa'
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            valor REAL NOT NULL,
            forma_pagamento TEXT NOT NULL
        )
    ''')
    
    # Tabela de Categorias pré-cadastradas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            tipo TEXT NOT NULL
        )
    ''')
    
    # Inserir categorias padrão se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM categorias")
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
        cursor.executemany("INSERT INTO categorias (nome, tipo) VALUES (?, ?)", categorias_padrao)

    conn.commit()
    conn.close()

init_db()

# --- ROTAS DE AUTENTICAÇÃO ---
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

# --- ROTAS DE PÁGINAS PROTEGIDAS ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

# --- APIS DE CATEGORIAS PROTEGIDAS ---
@app.route('/api/categorias', methods=['GET'])
@login_required
def listar_categorias():
    conn = sqlite3.connect('financeiro.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias ORDER BY tipo, nome')
    categorias = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(categorias)

# --- APIS DE TRANSAÇÕES PROTEGIDAS ---
@app.route('/api/transacoes', methods=['POST'])
@login_required
def salvar_transacao():
    data = request.json
    conn = sqlite3.connect('financeiro.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transacoes (data, tipo, descricao, categoria, valor, forma_pagamento)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['data'], data['tipo'], data['descricao'], data['categoria'], float(data['valor']), data['forma_pagamento']))
    conn.commit()
    conn.close()
    return jsonify({"status": "sucesso"})

@app.route('/api/transacoes/<int:transacao_id>', methods=['DELETE'])
@login_required
def excluir_transacao(transacao_id):
    conn = sqlite3.connect('financeiro.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM transacoes WHERE id = ?', (transacao_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "sucesso"})

# --- API DE RELATÓRIOS PROTEGIDA ---
@app.route('/api/relatorio', methods=['GET'])
@login_required
def relatorio_financeiro():
    periodo = request.args.get('periodo', 'dia') # dia, semana, mes
    conn = sqlite3.connect('financeiro.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if periodo == 'dia':
        query_agrupado = '''
            SELECT 
                data as grupo,
                SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) as total_receita,
                SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) as total_despesa
            FROM transacoes
            GROUP BY data
            ORDER BY data DESC
        '''
    elif periodo == 'semana':
        query_agrupado = '''
            SELECT 
                strftime('%Y-W%W', data) as grupo,
                SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) as total_receita,
                SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) as total_despesa
            FROM transacoes
            GROUP BY grupo
            ORDER BY grupo DESC
        '''
    else:  # mes
        query_agrupado = '''
            SELECT 
                strftime('%Y-%m', data) as grupo,
                SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) as total_receita,
                SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) as total_despesa
            FROM transacoes
            GROUP BY grupo
            ORDER BY grupo DESC
        '''

    cursor.execute(query_agrupado)
    agrupado = [dict(row) for row in cursor.fetchall()]

    cursor.execute('SELECT * FROM transacoes ORDER BY data DESC, id DESC LIMIT 100')
    detalhado = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({'agrupado': agrupado, 'detalhado': detalhado})

# --- BACKUP PROTEGIDO ---
@app.route('/api/backup', methods=['GET'])
@login_required
def fazer_backup():
    if not os.path.exists('backups'):
        os.makedirs('backups')
    data_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    nome_backup = f'backups/backup_financeiro_{data_str}.db'
    shutil.copyfile('financeiro.db', nome_backup)
    return send_file(nome_backup, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
