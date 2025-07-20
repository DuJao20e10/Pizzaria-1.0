from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
import sqlite3
import hashlib
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import urllib.parse
import os

app = Flask(__name__)
app.secret_key = 'pizzasystem_secret_key_2025'

# Configuração do banco de dados
DATABASE = 'pizzaria.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # Tabela de configurações
    conn.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_sistema TEXT DEFAULT 'PizzaSystem Pro',
            endereco TEXT,
            telefone_whatsapp TEXT,
            logo_sistema TEXT
        )
    ''')
    
    # Tabela de usuários
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('admin', 'garcom', 'atendente')),
            ativo BOOLEAN DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de categorias
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            ativo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabela de produtos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            categoria_id INTEGER,
            preco_p REAL,
            preco_m REAL,
            preco_g REAL,
            preco_familia REAL,
            foto TEXT,
            ativo BOOLEAN DEFAULT 1,
            permite_meio_meio BOOLEAN DEFAULT 0,
            FOREIGN KEY (categoria_id) REFERENCES categorias (id)
        )
    ''')
    
    # Tabela de mesas
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mesas (
            id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'livre' CHECK (status IN ('livre', 'ocupada')),
            total REAL DEFAULT 0,
            observacoes TEXT,
            data_abertura TIMESTAMP,
            tem_solicitacao BOOLEAN DEFAULT 0,
            cliente_nome TEXT,
            cliente_telefone TEXT
        )
    ''')
    
    # Tabela de pedidos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nome TEXT,
            cliente_telefone TEXT,
            total REAL DEFAULT 0,
            data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'aberto' CHECK (status IN ('aberto', 'preparando', 'pronto', 'finalizado')),
            tipo TEXT DEFAULT 'retirada' CHECK (tipo IN ('mesa', 'retirada')),
            mesa_id INTEGER,
            observacoes TEXT,
            FOREIGN KEY (mesa_id) REFERENCES mesas (id)
        )
    ''')
    
    # Tabela de itens do pedido
    conn.execute('''
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            produto_nome TEXT,
            tamanho TEXT,
            quantidade INTEGER,
            preco_unitario REAL,
            preco_total REAL,
            observacoes TEXT,
            sabor_1 TEXT,
            sabor_2 TEXT,
            meio_meio BOOLEAN DEFAULT 0,
            FOREIGN KEY (pedido_id) REFERENCES pedidos (id)
        )
    ''')
    
    # Tabela de solicitações de conta
    conn.execute('''
        CREATE TABLE IF NOT EXISTS solicitacoes_conta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesa_id INTEGER,
            observacoes TEXT,
            data_solicitacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pendente' CHECK (status IN ('pendente', 'atendida')),
            atendido_por TEXT,
            data_atendimento TIMESTAMP,
            FOREIGN KEY (mesa_id) REFERENCES mesas (id)
        )
    ''')
    
    # Inserir configuração padrão
    conn.execute('''
        INSERT OR IGNORE INTO configuracoes (id, nome_sistema, endereco, telefone_whatsapp)
        VALUES (1, 'PizzaSystem Pro', 'Rua das Pizzas, 123 - Centro', '5511999999999')
    ''')
    
    # Inserir usuários padrão
    admin_password = hashlib.md5('admin123'.encode()).hexdigest()
    garcom_password = hashlib.md5('garcom123'.encode()).hexdigest()
    
    conn.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, tipo)
        VALUES ('admin', ?, 'admin')
    ''', (admin_password,))
    
    conn.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, tipo)
        VALUES ('garcom', ?, 'garcom')
    ''', (garcom_password,))
    
    # Inserir categorias padrão
    categorias_padrao = ['Pizzas Tradicionais', 'Pizzas Especiais', 'Pizzas Doces', 'Bebidas', 'Porções', 'Sobremesas']
    for categoria in categorias_padrao:
        conn.execute('INSERT OR IGNORE INTO categorias (nome) VALUES (?)', (categoria,))
    
    # Inserir produtos padrão
    produtos_padrao = [
        ('Pizza Margherita', 'Molho de tomate, mussarela, manjericão e orégano', 1, 25.00, 35.00, 45.00, 55.00, 'https://images.pexels.com/photos/315755/pexels-photo-315755.jpeg', 1, 1),
        ('Pizza Calabresa', 'Molho de tomate, mussarela, calabresa e cebola', 1, 28.00, 38.00, 48.00, 58.00, 'https://images.pexels.com/photos/708587/pexels-photo-708587.jpeg', 1, 1),
        ('Pizza Portuguesa', 'Molho de tomate, mussarela, presunto, ovos, cebola e azeitona', 1, 32.00, 42.00, 52.00, 62.00, 'https://images.pexels.com/photos/1146760/pexels-photo-1146760.jpeg', 1, 1),
        ('Pizza Quatro Queijos', 'Molho de tomate, mussarela, gorgonzola, parmesão e catupiry', 2, 35.00, 45.00, 55.00, 65.00, 'https://images.pexels.com/photos/2147491/pexels-photo-2147491.jpeg', 1, 1),
        ('Pizza Frango com Catupiry', 'Molho de tomate, mussarela, frango desfiado e catupiry', 2, 30.00, 40.00, 50.00, 60.00, 'https://images.pexels.com/photos/1653877/pexels-photo-1653877.jpeg', 1, 1),
        ('Pizza Chocolate', 'Chocolate ao leite, granulado e leite condensado', 3, 25.00, 35.00, 45.00, 55.00, 'https://images.pexels.com/photos/291528/pexels-photo-291528.jpeg', 1, 0),
        ('Coca-Cola 2L', 'Refrigerante Coca-Cola 2 litros', 4, None, None, None, 8.00, 'https://images.pexels.com/photos/50593/coca-cola-cold-drink-soft-drink-coke-50593.jpeg', 1, 0),
        ('Água Mineral 500ml', 'Água mineral natural 500ml', 4, None, None, None, 3.00, 'https://images.pexels.com/photos/416528/pexels-photo-416528.jpeg', 1, 0),
        ('Porção de Batata Frita', 'Batata frita crocante com temperos especiais', 5, None, 15.00, 25.00, None, 'https://images.pexels.com/photos/1583884/pexels-photo-1583884.jpeg', 1, 0),
        ('Pudim de Leite', 'Pudim de leite condensado com calda de caramelo', 6, None, None, None, 8.00, 'https://images.pexels.com/photos/1126359/pexels-photo-1126359.jpeg', 1, 0)
    ]
    
    for produto in produtos_padrao:
        conn.execute('''
            INSERT OR IGNORE INTO produtos 
            (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto, ativo, permite_meio_meio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', produto)
    
    # Criar mesas (1 a 15)
    for i in range(1, 16):
        conn.execute('INSERT OR IGNORE INTO mesas (id) VALUES (?)', (i,))
    
    conn.commit()
    conn.close()

def get_config():
    conn = get_db_connection()
    config = conn.execute('SELECT * FROM configuracoes WHERE id = 1').fetchone()
    conn.close()
    return config

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_tipo') != 'admin':
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    config = get_config()
    
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.md5(request.form['password'].encode()).hexdigest()
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM usuarios WHERE username = ? AND password = ? AND ativo = 1',
            (username, password)
        ).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_tipo'] = user['tipo']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos!', 'error')
    
    return render_template('login.html', config=config)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    config = get_config()
    conn = get_db_connection()
    
    # Estatísticas do dashboard
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    pedidos_hoje = conn.execute(
        'SELECT COUNT(*) as count FROM pedidos WHERE DATE(data_pedido) = ?',
        (hoje,)
    ).fetchone()['count']
    
    vendas_hoje = conn.execute(
        'SELECT COALESCE(SUM(total), 0) as total FROM pedidos WHERE DATE(data_pedido) = ? AND status = "finalizado"',
        (hoje,)
    ).fetchone()['total']
    
    mesas_ocupadas = conn.execute(
        'SELECT COUNT(*) as count FROM mesas WHERE status = "ocupada"'
    ).fetchone()['count']
    
    total_produtos = conn.execute(
        'SELECT COUNT(*) as count FROM produtos WHERE ativo = 1'
    ).fetchone()['count']
    
    solicitacoes_pendentes = conn.execute(
        'SELECT COUNT(*) as count FROM solicitacoes_conta WHERE status = "pendente"'
    ).fetchone()['count']
    
    # Produtos mais vendidos
    produtos_populares = conn.execute('''
        SELECT produto_nome, SUM(quantidade) as total_vendido
        FROM itens_pedido ip
        JOIN pedidos p ON ip.pedido_id = p.id
        WHERE DATE(p.data_pedido) >= DATE('now', '-7 days')
        GROUP BY produto_nome
        ORDER BY total_vendido DESC
        LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    return render_template('dashboard.html',
                         config=config,
                         pedidos_hoje=pedidos_hoje,
                         vendas_hoje=vendas_hoje,
                         mesas_ocupadas=mesas_ocupadas,
                         total_produtos=total_produtos,
                         solicitacoes_pendentes=solicitacoes_pendentes,
                         produtos_populares=produtos_populares)

@app.route('/mesas')
@login_required
def mesas():
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_config()
    conn = get_db_connection()
    
    mesas = conn.execute('''
        SELECT m.*, 
               CASE WHEN s.mesa_id IS NOT NULL THEN 1 ELSE 0 END as tem_solicitacao
        FROM mesas m
        LEFT JOIN solicitacoes_conta s ON m.id = s.mesa_id AND s.status = 'pendente'
        ORDER BY m.id
    ''').fetchall()
    
    conn.close()
    
    return render_template('mesas.html', config=config, mesas=mesas)

@app.route('/abrir_mesa/<int:mesa_id>')
@login_required
def abrir_mesa_form(mesa_id):
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_config()
    return render_template('abrir_mesa.html', config=config, mesa_id=mesa_id)

@app.route('/abrir_mesa/<int:mesa_id>', methods=['POST'])
@login_required
def abrir_mesa(mesa_id):
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    cliente_nome = request.form['cliente_nome']
    cliente_telefone = request.form.get('cliente_telefone', '')
    
    conn = get_db_connection()
    
    # Verificar se a mesa está livre
    mesa = conn.execute('SELECT * FROM mesas WHERE id = ?', (mesa_id,)).fetchone()
    if mesa['status'] == 'ocupada':
        flash('Mesa já está ocupada!', 'error')
        conn.close()
        return redirect(url_for('mesas'))
    
    # Abrir a mesa
    conn.execute('''
        UPDATE mesas 
        SET status = 'ocupada', 
            data_abertura = CURRENT_TIMESTAMP,
            cliente_nome = ?,
            cliente_telefone = ?,
            total = 0
        WHERE id = ?
    ''', (cliente_nome, cliente_telefone, mesa_id))
    
    # Criar pedido para a mesa
    conn.execute('''
        INSERT INTO pedidos (cliente_nome, cliente_telefone, tipo, mesa_id, status)
        VALUES (?, ?, 'mesa', ?, 'aberto')
    ''', (cliente_nome, cliente_telefone, mesa_id))
    
    conn.commit()
    conn.close()
    
    flash(f'Mesa {mesa_id} aberta para {cliente_nome}!', 'success')
    return redirect(url_for('mesas'))

@app.route('/pedido_mesa/<int:mesa_id>')
@login_required
def pedido_mesa(mesa_id):
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_config()
    conn = get_db_connection()
    
    # Verificar se a mesa está ocupada
    mesa = conn.execute('SELECT * FROM mesas WHERE id = ?', (mesa_id,)).fetchone()
    if mesa['status'] != 'ocupada':
        flash('Mesa não está ocupada!', 'error')
        conn.close()
        return redirect(url_for('mesas'))
    
    # Buscar produtos e categorias
    produtos = conn.execute('''
        SELECT p.*, c.nome as categoria_nome
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''').fetchall()
    
    categorias = conn.execute(
        'SELECT * FROM categorias WHERE ativo = 1 ORDER BY nome'
    ).fetchall()
    
    conn.close()
    
    return render_template('pedido_mesa.html',
                         config=config,
                         mesa_id=mesa_id,
                         produtos=produtos,
                         categorias=categorias)

@app.route('/adicionar_item_mesa/<int:mesa_id>', methods=['POST'])
@login_required
def adicionar_item_mesa(mesa_id):
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    produto_id = request.form['produto_id']
    tamanho = request.form.get('tamanho')
    quantidade = int(request.form['quantidade'])
    observacoes = request.form.get('observacoes', '')
    meio_meio = request.form.get('meio_meio') == 'on'
    sabor_1 = request.form.get('sabor_1', '')
    sabor_2 = request.form.get('sabor_2', '')
    
    conn = get_db_connection()
    
    # Buscar produto
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (produto_id,)).fetchone()
    
    # Determinar preço baseado no tamanho
    if tamanho == 'P':
        preco_unitario = produto['preco_p']
    elif tamanho == 'M':
        preco_unitario = produto['preco_m']
    elif tamanho == 'G':
        preco_unitario = produto['preco_g']
    elif tamanho == 'Família':
        preco_unitario = produto['preco_familia']
    else:
        preco_unitario = produto['preco_p'] or produto['preco_m'] or produto['preco_g'] or produto['preco_familia']
    
    preco_total = preco_unitario * quantidade
    
    # Buscar pedido da mesa
    pedido = conn.execute(
        'SELECT * FROM pedidos WHERE mesa_id = ? AND status = "aberto" AND tipo = "mesa"',
        (mesa_id,)
    ).fetchone()
    
    if not pedido:
        flash('Pedido não encontrado!', 'error')
        conn.close()
        return redirect(url_for('mesas'))
    
    # Preparar nome do produto com sabores
    produto_nome = produto['nome']
    if meio_meio and sabor_1 and sabor_2:
        produto_nome = f"{produto['nome']} (Meio a Meio: {sabor_1} / {sabor_2})"
        observacoes = f"Meio a Meio: {sabor_1} / {sabor_2}. {observacoes}".strip()
    
    # Adicionar item ao pedido
    conn.execute('''
        INSERT INTO itens_pedido 
        (pedido_id, produto_nome, tamanho, quantidade, preco_unitario, preco_total, observacoes, sabor_1, sabor_2, meio_meio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pedido['id'], produto_nome, tamanho, quantidade, preco_unitario, preco_total, observacoes, sabor_1, sabor_2, meio_meio))
    
    # Atualizar total do pedido
    novo_total = conn.execute(
        'SELECT SUM(preco_total) as total FROM itens_pedido WHERE pedido_id = ?',
        (pedido['id'],)
    ).fetchone()['total']
    
    conn.execute(
        'UPDATE pedidos SET total = ? WHERE id = ?',
        (novo_total, pedido['id'])
    )
    
    # Atualizar total da mesa
    conn.execute(
        'UPDATE mesas SET total = ? WHERE id = ?',
        (novo_total, mesa_id)
    )
    
    conn.commit()
    conn.close()
    
    flash('Item adicionado ao pedido!', 'success')
    return redirect(url_for('pedido_mesa', mesa_id=mesa_id))

@app.route('/ver_pedido_mesa/<int:mesa_id>')
@login_required
def ver_pedido_mesa(mesa_id):
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_config()
    conn = get_db_connection()
    
    # Buscar pedido da mesa
    pedido = conn.execute('''
        SELECT p.id, p.total, p.data_pedido, p.observacoes
        FROM pedidos p
        WHERE p.mesa_id = ? AND p.status = "aberto" AND p.tipo = "mesa"
    ''', (mesa_id,)).fetchone()
    
    if not pedido:
        flash('Pedido não encontrado!', 'error')
        conn.close()
        return redirect(url_for('mesas'))
    
    # Buscar itens do pedido
    itens = conn.execute('''
        SELECT * FROM itens_pedido
        WHERE pedido_id = ?
        ORDER BY id
    ''', (pedido['id'],)).fetchall()
    
    conn.close()
    
    return render_template('ver_pedido_mesa.html',
                         config=config,
                         mesa_id=mesa_id,
                         pedido=pedido,
                         itens=itens)

@app.route('/fechar_mesa/<int:mesa_id>')
@login_required
def fechar_mesa(mesa_id):
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_config()
    conn = get_db_connection()
    
    # Buscar dados da mesa
    mesa = conn.execute('SELECT * FROM mesas WHERE id = ?', (mesa_id,)).fetchone()
    
    if mesa['status'] != 'ocupada':
        flash('Mesa não está ocupada!', 'error')
        conn.close()
        return redirect(url_for('mesas'))
    
    # Buscar pedido da mesa
    pedido = conn.execute('''
        SELECT * FROM pedidos
        WHERE mesa_id = ? AND status = "aberto" AND tipo = "mesa"
    ''', (mesa_id,)).fetchone()
    
    # Buscar itens do pedido
    itens = conn.execute('''
        SELECT * FROM itens_pedido
        WHERE pedido_id = ?
        ORDER BY id
    ''', (pedido['id'],)).fetchall()
    
    # Finalizar pedido
    conn.execute(
        'UPDATE pedidos SET status = "finalizado" WHERE id = ?',
        (pedido['id'],)
    )
    
    # Liberar mesa
    conn.execute('''
        UPDATE mesas 
        SET status = 'livre', 
            total = 0, 
            observacoes = NULL, 
            data_abertura = NULL,
            tem_solicitacao = 0,
            cliente_nome = NULL,
            cliente_telefone = NULL
        WHERE id = ?
    ''', (mesa_id,))
    
    # Remover solicitações pendentes
    conn.execute(
        'DELETE FROM solicitacoes_conta WHERE mesa_id = ? AND status = "pendente"',
        (mesa_id,)
    )
    
    conn.commit()
    
    # Gerar relatório para WhatsApp
    relatorio = gerar_relatorio_mesa(mesa, pedido, itens, config)
    
    # Preparar URL do WhatsApp
    whatsapp_url = ""
    if mesa['cliente_telefone']:
        mensagem = f"🍕 *{config['nome_sistema']}*\n\n{relatorio}"
        whatsapp_url = f"https://wa.me/{mesa['cliente_telefone']}?text={urllib.parse.quote(mensagem)}"
    
    conn.close()
    
    return render_template('fechar_mesa.html',
                         config=config,
                         mesa_id=mesa_id,
                         cliente_nome=mesa['cliente_nome'],
                         cliente_telefone=mesa['cliente_telefone'],
                         total=mesa['total'],
                         relatorio=relatorio,
                         whatsapp_url=whatsapp_url)

def gerar_relatorio_mesa(mesa, pedido, itens, config):
    relatorio = f"""📋 RELATÓRIO DA MESA {mesa['id']}

👤 Cliente: {mesa['cliente_nome']}
📞 Telefone: {mesa['cliente_telefone'] or 'Não informado'}
🕐 Abertura: {mesa['data_abertura']}
🕐 Fechamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}

📝 ITENS CONSUMIDOS:
"""
    
    for item in itens:
        relatorio += f"\n• {item['produto_nome']}"
        if item['tamanho']:
            relatorio += f" ({item['tamanho']})"
        relatorio += f"\n  Qtd: {item['quantidade']} x R$ {item['preco_unitario']:.2f} = R$ {item['preco_total']:.2f}"
        if item['observacoes']:
            relatorio += f"\n  Obs: {item['observacoes']}"
        relatorio += "\n"
    
    relatorio += f"""
💰 TOTAL: R$ {mesa['total']:.2f}

🍕 {config['nome_sistema']}
📍 {config['endereco'] or 'Endereço não informado'}

Obrigado pela preferência! 😊"""
    
    return relatorio

@app.route('/qrcode_mesa/<int:mesa_id>')
@login_required
def qrcode_mesa(mesa_id):
    # Gerar QR Code para a mesa
    url = url_for('cliente_mesa', mesa_id=mesa_id, _external=True)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Converter para base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    response.headers['Content-Disposition'] = f'inline; filename=mesa_{mesa_id}_qrcode.png'
    
    return response

@app.route('/cliente/mesa/<int:mesa_id>')
def cliente_mesa(mesa_id):
    config = get_config()
    
    try:
        conn = get_db_connection()
        
        # Verificar se a mesa existe
        mesa = conn.execute('SELECT * FROM mesas WHERE id = ?', (mesa_id,)).fetchone()
        if not mesa:
            conn.close()
            return render_template('cliente_erro.html', 
                                 config=config, 
                                 erro="Mesa não encontrada!")
        
        # Buscar produtos e categorias
        produtos = conn.execute('''
            SELECT p.*, c.nome as categoria_nome
            FROM produtos p
            JOIN categorias c ON p.categoria_id = c.id
            WHERE p.ativo = 1
            ORDER BY c.nome, p.nome
        ''').fetchall()
        
        categorias = conn.execute(
            'SELECT * FROM categorias WHERE ativo = 1 ORDER BY nome'
        ).fetchall()
        
        conn.close()
        
        return render_template('cliente_mesa.html',
                             config=config,
                             mesa_id=mesa_id,
                             produtos=produtos,
                             categorias=categorias)
    
    except Exception as e:
        return render_template('cliente_erro.html', 
                             config=config, 
                             erro="Erro interno do sistema!")

@app.route('/solicitar_conta/<int:mesa_id>', methods=['POST'])
def solicitar_conta(mesa_id):
    observacoes = request.form.get('observacoes', '')
    
    conn = get_db_connection()
    
    # Verificar se já existe solicitação pendente
    solicitacao_existente = conn.execute(
        'SELECT * FROM solicitacoes_conta WHERE mesa_id = ? AND status = "pendente"',
        (mesa_id,)
    ).fetchone()
    
    if solicitacao_existente:
        conn.close()
        flash('Já existe uma solicitação pendente para esta mesa!', 'warning')
        return redirect(url_for('cliente_mesa', mesa_id=mesa_id))
    
    # Criar nova solicitação
    conn.execute('''
        INSERT INTO solicitacoes_conta (mesa_id, observacoes)
        VALUES (?, ?)
    ''', (mesa_id, observacoes))
    
    # Marcar mesa com solicitação
    conn.execute(
        'UPDATE mesas SET tem_solicitacao = 1 WHERE id = ?',
        (mesa_id,)
    )
    
    conn.commit()
    conn.close()
    
    flash('Solicitação de conta enviada com sucesso! Um garçom irá atendê-lo em breve.', 'success')
    return redirect(url_for('cliente_mesa', mesa_id=mesa_id))

@app.route('/solicitacoes')
@login_required
def solicitacoes():
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    config = get_config()
    conn = get_db_connection()
    
    solicitacoes = conn.execute('''
        SELECT s.*, m.cliente_nome
        FROM solicitacoes_conta s
        JOIN mesas m ON s.mesa_id = m.id
        ORDER BY s.data_solicitacao DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('solicitacoes.html', config=config, solicitacoes=solicitacoes)

@app.route('/atender_solicitacao/<int:solicitacao_id>')
@login_required
def atender_solicitacao(solicitacao_id):
    if session.get('user_tipo') not in ['admin', 'garcom']:
        flash('Acesso negado!', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    
    # Buscar solicitação
    solicitacao = conn.execute(
        'SELECT * FROM solicitacoes_conta WHERE id = ?',
        (solicitacao_id,)
    ).fetchone()
    
    if not solicitacao:
        flash('Solicitação não encontrada!', 'error')
        conn.close()
        return redirect(url_for('solicitacoes'))
    
    # Marcar como atendida
    conn.execute('''
        UPDATE solicitacoes_conta 
        SET status = 'atendida', 
            atendido_por = ?, 
            data_atendimento = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session['username'], solicitacao_id))
    
    # Remover marcação da mesa
    conn.execute(
        'UPDATE mesas SET tem_solicitacao = 0 WHERE id = ?',
        (solicitacao['mesa_id'],)
    )
    
    conn.commit()
    conn.close()
    
    flash('Solicitação atendida com sucesso!', 'success')
    return redirect(url_for('fechar_mesa', mesa_id=solicitacao['mesa_id']))

@app.route('/retirada')
@login_required
def retirada():
    config = get_config()
    conn = get_db_connection()
    
    # Buscar pedidos de retirada em andamento
    pedidos_retirada = conn.execute('''
        SELECT * FROM pedidos
        WHERE tipo = 'retirada' AND status != 'finalizado'
        ORDER BY data_pedido DESC
    ''').fetchall()
    
    # Buscar produtos e categorias para o cardápio rápido
    produtos = conn.execute('''
        SELECT p.*, c.nome as categoria_nome
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''').fetchall()
    
    categorias = conn.execute(
        'SELECT * FROM categorias WHERE ativo = 1 ORDER BY nome'
    ).fetchall()
    
    conn.close()
    
    return render_template('retirada.html',
                         config=config,
                         pedidos_retirada=pedidos_retirada,
                         produtos=produtos,
                         categorias=categorias)

@app.route('/novo_pedido_retirada', methods=['POST'])
@login_required
def novo_pedido_retirada():
    cliente_nome = request.form.get('cliente_nome', 'Cliente Balcão')
    cliente_telefone = request.form.get('cliente_telefone', '')
    
    conn = get_db_connection()
    
    cursor = conn.execute('''
        INSERT INTO pedidos (cliente_nome, cliente_telefone, tipo, status)
        VALUES (?, ?, 'retirada', 'aberto')
    ''', (cliente_nome, cliente_telefone))
    
    pedido_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    flash('Novo pedido criado!', 'success')
    return redirect(url_for('editar_pedido_retirada', pedido_id=pedido_id))

@app.route('/editar_pedido_retirada/<int:pedido_id>')
@login_required
def editar_pedido_retirada(pedido_id):
    config = get_config()
    conn = get_db_connection()
    
    # Buscar pedido
    pedido = conn.execute('SELECT * FROM pedidos WHERE id = ?', (pedido_id,)).fetchone()
    
    if not pedido:
        flash('Pedido não encontrado!', 'error')
        conn.close()
        return redirect(url_for('retirada'))
    
    # Buscar itens do pedido
    itens = conn.execute('''
        SELECT * FROM itens_pedido
        WHERE pedido_id = ?
        ORDER BY id
    ''', (pedido_id,)).fetchall()
    
    # Buscar produtos e categorias
    produtos = conn.execute('''
        SELECT p.*, c.nome as categoria_nome
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''').fetchall()
    
    categorias = conn.execute(
        'SELECT * FROM categorias WHERE ativo = 1 ORDER BY nome'
    ).fetchall()
    
    conn.close()
    
    return render_template('editar_pedido_retirada.html',
                         config=config,
                         pedido=pedido,
                         itens=itens,
                         produtos=produtos,
                         categorias=categorias)

@app.route('/adicionar_item_retirada/<int:pedido_id>', methods=['POST'])
@login_required
def adicionar_item_retirada(pedido_id):
    produto_id = request.form['produto_id']
    tamanho = request.form.get('tamanho')
    quantidade = int(request.form['quantidade'])
    observacoes = request.form.get('observacoes', '')
    meio_meio = request.form.get('meio_meio') == 'on'
    sabor_1 = request.form.get('sabor_1', '')
    sabor_2 = request.form.get('sabor_2', '')
    
    conn = get_db_connection()
    
    # Buscar produto
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (produto_id,)).fetchone()
    
    # Determinar preço baseado no tamanho
    if tamanho == 'P':
        preco_unitario = produto['preco_p']
    elif tamanho == 'M':
        preco_unitario = produto['preco_m']
    elif tamanho == 'G':
        preco_unitario = produto['preco_g']
    elif tamanho == 'Família':
        preco_unitario = produto['preco_familia']
    else:
        preco_unitario = produto['preco_p'] or produto['preco_m'] or produto['preco_g'] or produto['preco_familia']
    
    preco_total = preco_unitario * quantidade
    
    # Preparar nome do produto com sabores
    produto_nome = produto['nome']
    if meio_meio and sabor_1 and sabor_2:
        produto_nome = f"{produto['nome']} (Meio a Meio: {sabor_1} / {sabor_2})"
        observacoes = f"Meio a Meio: {sabor_1} / {sabor_2}. {observacoes}".strip()
    
    # Adicionar item ao pedido
    conn.execute('''
        INSERT INTO itens_pedido 
        (pedido_id, produto_nome, tamanho, quantidade, preco_unitario, preco_total, observacoes, sabor_1, sabor_2, meio_meio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pedido_id, produto_nome, tamanho, quantidade, preco_unitario, preco_total, observacoes, sabor_1, sabor_2, meio_meio))
    
    # Atualizar total do pedido
    novo_total = conn.execute(
        'SELECT SUM(preco_total) as total FROM itens_pedido WHERE pedido_id = ?',
        (pedido_id,)
    ).fetchone()['total']
    
    conn.execute(
        'UPDATE pedidos SET total = ? WHERE id = ?',
        (novo_total, pedido_id)
    )
    
    conn.commit()
    conn.close()
    
    flash('Item adicionado ao pedido!', 'success')
    return redirect(url_for('editar_pedido_retirada', pedido_id=pedido_id))

@app.route('/remover_item_pedido/<int:item_id>')
@login_required
def remover_item_pedido(item_id):
    conn = get_db_connection()
    
    # Buscar item
    item = conn.execute('SELECT * FROM itens_pedido WHERE id = ?', (item_id,)).fetchone()
    
    if not item:
        flash('Item não encontrado!', 'error')
        conn.close()
        return redirect(url_for('retirada'))
    
    pedido_id = item['pedido_id']
    
    # Remover item
    conn.execute('DELETE FROM itens_pedido WHERE id = ?', (item_id,))
    
    # Atualizar total do pedido
    novo_total = conn.execute(
        'SELECT COALESCE(SUM(preco_total), 0) as total FROM itens_pedido WHERE pedido_id = ?',
        (pedido_id,)
    ).fetchone()['total']
    
    conn.execute(
        'UPDATE pedidos SET total = ? WHERE id = ?',
        (novo_total, pedido_id)
    )
    
    # Verificar se é pedido de mesa e atualizar total da mesa
    pedido = conn.execute('SELECT * FROM pedidos WHERE id = ?', (pedido_id,)).fetchone()
    if pedido['tipo'] == 'mesa' and pedido['mesa_id']:
        conn.execute(
            'UPDATE mesas SET total = ? WHERE id = ?',
            (novo_total, pedido['mesa_id'])
        )
    
    conn.commit()
    conn.close()
    
    flash('Item removido do pedido!', 'success')
    
    # Redirecionar baseado no tipo de pedido
    if pedido['tipo'] == 'mesa':
        return redirect(url_for('ver_pedido_mesa', mesa_id=pedido['mesa_id']))
    else:
        return redirect(url_for('editar_pedido_retirada', pedido_id=pedido_id))

@app.route('/alterar_status_pedido/<int:pedido_id>/<status>')
@login_required
def alterar_status_pedido(pedido_id, status):
    conn = get_db_connection()
    
    conn.execute(
        'UPDATE pedidos SET status = ? WHERE id = ?',
        (status, pedido_id)
    )
    
    conn.commit()
    conn.close()
    
    flash(f'Status do pedido alterado para {status}!', 'success')
    return redirect(url_for('retirada'))

@app.route('/finalizar_pedido_retirada/<int:pedido_id>')
@login_required
def finalizar_pedido_retirada(pedido_id):
    conn = get_db_connection()
    
    conn.execute(
        'UPDATE pedidos SET status = "finalizado" WHERE id = ?',
        (pedido_id,)
    )
    
    conn.commit()
    conn.close()
    
    flash('Pedido finalizado com sucesso!', 'success')
    return redirect(url_for('retirada'))

@app.route('/produtos')
@login_required
@admin_required
def produtos():
    config = get_config()
    conn = get_db_connection()
    
    produtos = conn.execute('''
        SELECT p.*, c.nome as categoria_nome
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        ORDER BY c.nome, p.nome
    ''').fetchall()
    
    categorias = conn.execute(
        'SELECT * FROM categorias WHERE ativo = 1 ORDER BY nome'
    ).fetchall()
    
    conn.close()
    
    return render_template('produtos.html',
                         config=config,
                         produtos=produtos,
                         categorias=categorias)

@app.route('/adicionar_produto', methods=['POST'])
@login_required
@admin_required
def adicionar_produto():
    nome = request.form['nome']
    descricao = request.form.get('descricao', '')
    categoria_id = request.form['categoria_id']
    preco_p = request.form.get('preco_p') or None
    preco_m = request.form.get('preco_m') or None
    preco_g = request.form.get('preco_g') or None
    preco_familia = request.form.get('preco_familia') or None
    foto = request.form.get('foto', '')
    permite_meio_meio = 1 if request.form.get('permite_meio_meio') else 0
    
    conn = get_db_connection()
    
    conn.execute('''
        INSERT INTO produtos 
        (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto, permite_meio_meio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto, permite_meio_meio))
    
    conn.commit()
    conn.close()
    
    flash('Produto adicionado com sucesso!', 'success')
    return redirect(url_for('produtos'))

@app.route('/editar_produto/<int:produto_id>')
@login_required
@admin_required
def editar_produto(produto_id):
    config = get_config()
    conn = get_db_connection()
    
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (produto_id,)).fetchone()
    
    if not produto:
        flash('Produto não encontrado!', 'error')
        conn.close()
        return redirect(url_for('produtos'))
    
    categorias = conn.execute(
        'SELECT * FROM categorias WHERE ativo = 1 ORDER BY nome'
    ).fetchall()
    
    conn.close()
    
    return render_template('editar_produto.html',
                         config=config,
                         produto=produto,
                         categorias=categorias)

@app.route('/salvar_edicao_produto/<int:produto_id>', methods=['POST'])
@login_required
@admin_required
def salvar_edicao_produto(produto_id):
    nome = request.form['nome']
    descricao = request.form.get('descricao', '')
    categoria_id = request.form['categoria_id']
    preco_p = request.form.get('preco_p') or None
    preco_m = request.form.get('preco_m') or None
    preco_g = request.form.get('preco_g') or None
    preco_familia = request.form.get('preco_familia') or None
    foto = request.form.get('foto', '')
    permite_meio_meio = 1 if request.form.get('permite_meio_meio') else 0
    
    conn = get_db_connection()
    
    conn.execute('''
        UPDATE produtos 
        SET nome = ?, descricao = ?, categoria_id = ?, preco_p = ?, preco_m = ?, 
            preco_g = ?, preco_familia = ?, foto = ?, permite_meio_meio = ?
        WHERE id = ?
    ''', (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto, permite_meio_meio, produto_id))
    
    conn.commit()
    conn.close()
    
    flash('Produto atualizado com sucesso!', 'success')
    return redirect(url_for('produtos'))

@app.route('/toggle_produto/<int:produto_id>')
@login_required
@admin_required
def toggle_produto(produto_id):
    conn = get_db_connection()
    
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (produto_id,)).fetchone()
    novo_status = 0 if produto['ativo'] else 1
    
    conn.execute(
        'UPDATE produtos SET ativo = ? WHERE id = ?',
        (novo_status, produto_id)
    )
    
    conn.commit()
    conn.close()
    
    status_texto = 'ativado' if novo_status else 'desativado'
    flash(f'Produto {status_texto} com sucesso!', 'success')
    return redirect(url_for('produtos'))

@app.route('/usuarios')
@login_required
@admin_required
def usuarios():
    config = get_config()
    conn = get_db_connection()
    
    usuarios = conn.execute(
        'SELECT * FROM usuarios ORDER BY tipo, username'
    ).fetchall()
    
    conn.close()
    
    return render_template('usuarios.html', config=config, usuarios=usuarios)

@app.route('/adicionar_usuario')
@login_required
@admin_required
def adicionar_usuario():
    config = get_config()
    return render_template('adicionar_usuario.html', config=config)

@app.route('/salvar_usuario', methods=['POST'])
@login_required
@admin_required
def salvar_usuario():
    username = request.form['username']
    password = hashlib.md5(request.form['password'].encode()).hexdigest()
    tipo = request.form['tipo']
    
    conn = get_db_connection()
    
    try:
        conn.execute('''
            INSERT INTO usuarios (username, password, tipo)
            VALUES (?, ?, ?)
        ''', (username, password, tipo))
        
        conn.commit()
        flash('Usuário criado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash('Nome de usuário já existe!', 'error')
    
    conn.close()
    return redirect(url_for('usuarios'))

@app.route('/editar_usuario/<int:usuario_id>')
@login_required
@admin_required
def editar_usuario(usuario_id):
    config = get_config()
    conn = get_db_connection()
    
    usuario = conn.execute('SELECT * FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    
    if not usuario:
        flash('Usuário não encontrado!', 'error')
        conn.close()
        return redirect(url_for('usuarios'))
    
    conn.close()
    
    return render_template('editar_usuario.html', config=config, usuario=usuario)

@app.route('/salvar_edicao_usuario/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def salvar_edicao_usuario(usuario_id):
    username = request.form['username']
    password = request.form.get('password')
    tipo = request.form['tipo']
    
    conn = get_db_connection()
    
    try:
        if password:
            password_hash = hashlib.md5(password.encode()).hexdigest()
            conn.execute('''
                UPDATE usuarios 
                SET username = ?, password = ?, tipo = ?
                WHERE id = ?
            ''', (username, password_hash, tipo, usuario_id))
        else:
            conn.execute('''
                UPDATE usuarios 
                SET username = ?, tipo = ?
                WHERE id = ?
            ''', (username, tipo, usuario_id))
        
        conn.commit()
        flash('Usuário atualizado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash('Nome de usuário já existe!', 'error')
    
    conn.close()
    return redirect(url_for('usuarios'))

@app.route('/toggle_usuario/<int:usuario_id>')
@login_required
@admin_required
def toggle_usuario(usuario_id):
    if usuario_id == session['user_id']:
        flash('Você não pode desativar seu próprio usuário!', 'error')
        return redirect(url_for('usuarios'))
    
    conn = get_db_connection()
    
    usuario = conn.execute('SELECT * FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    novo_status = 0 if usuario['ativo'] else 1
    
    conn.execute(
        'UPDATE usuarios SET ativo = ? WHERE id = ?',
        (novo_status, usuario_id)
    )
    
    conn.commit()
    conn.close()
    
    status_texto = 'ativado' if novo_status else 'desativado'
    flash(f'Usuário {status_texto} com sucesso!', 'success')
    return redirect(url_for('usuarios'))

@app.route('/configuracoes')
@login_required
@admin_required
def configuracoes():
    config = get_config()
    return render_template('configuracoes.html', config=config)

@app.route('/salvar_configuracoes', methods=['POST'])
@login_required
@admin_required
def salvar_configuracoes():
    nome_sistema = request.form['nome_sistema']
    endereco = request.form.get('endereco', '')
    telefone_whatsapp = request.form.get('telefone_whatsapp', '')
    logo_sistema = request.form.get('logo_sistema', '')
    
    conn = get_db_connection()
    
    conn.execute('''
        UPDATE configuracoes 
        SET nome_sistema = ?, endereco = ?, telefone_whatsapp = ?, logo_sistema = ?
        WHERE id = 1
    ''', (nome_sistema, endereco, telefone_whatsapp, logo_sistema))
    
    conn.commit()
    conn.close()
    
    flash('Configurações salvas com sucesso!', 'success')
    return redirect(url_for('configuracoes'))

@app.route('/relatorios')
@login_required
@admin_required
def relatorios():
    config = get_config()
    return render_template('relatorios.html', config=config)

@app.route('/api/notifications')
@login_required
def api_notifications():
    if session.get('user_tipo') not in ['admin', 'garcom']:
        return jsonify({'count': 0})
    
    conn = get_db_connection()
    count = conn.execute(
        'SELECT COUNT(*) as count FROM solicitacoes_conta WHERE status = "pendente"'
    ).fetchone()['count']
    conn.close()
    
    return jsonify({'count': count})

@app.route('/buscar_sabores')
@login_required
def buscar_sabores():
    categoria_id = request.args.get('categoria_id')
    
    conn = get_db_connection()
    sabores = conn.execute('''
        SELECT nome FROM produtos 
        WHERE categoria_id = ? AND ativo = 1 AND permite_meio_meio = 1
        ORDER BY nome
    ''', (categoria_id,)).fetchall()
    conn.close()
    
    return jsonify([sabor['nome'] for sabor in sabores])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)