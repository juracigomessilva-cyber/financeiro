import sqlite3
import shutil
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

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

# --- ROTAS DE PÁGINAS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/relatorios')
def relatorios():
    return render_template('relatorios.html')

# --- APIS DE CATEGORIAS ---
@app.route('/api/categorias', methods=['GET'])
def listar_categorias():
    conn = sqlite3.connect('financeiro.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias ORDER BY tipo, nome')
    categorias = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(categorias)

# --- APIS DE TRANSAÇÕES ---
@app.route('/api/transacoes', methods=['POST'])
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
def excluir_transacao(transacao_id):
    conn = sqlite3.connect('financeiro.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM transacoes WHERE id = ?', (transacao_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "sucesso"})

# --- API DE RELATÓRIOS (AGRUPADOS POR DIA, SEMANA OU MÊS) ---
@app.route('/api/relatorio', methods=['GET'])
def relatorio_financeiro():
    periodo = request.args.get('periodo', 'dia') # dia, semana, mes
    conn = sqlite3.connect('financeiro.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if periodo == 'dia':
        # Agrupa por dia exato (YYYY-MM-DD)
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
        # Agrupa pelo ano e número da semana (YYYY-Www)
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
        # Agrupa por ano e mês (YYYY-MM)
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

    # Lista de todas as transações recentes
    cursor.execute('SELECT * FROM transacoes ORDER BY data DESC, id DESC LIMIT 100')
    detalhado = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({'agrupado': agrupado, 'detalhado': detalhado})

# --- BACKUP ---
@app.route('/api/backup', methods=['GET'])
def fazer_backup():
    if not os.path.exists('backups'):
        os.makedirs('backups')
    data_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    nome_backup = f'backups/backup_financeiro_{data_str}.db'
    shutil.copyfile('financeiro.db', nome_backup)
    return send_file(nome_backup, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)