from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import sqlite3
import hashlib
import os
from datetime import datetime
import urllib.parse
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import base64
import qrcode
from PIL import Image
import urllib.parse

app = Flask(__name__)
app.secret_key = 'pizzaria_secret_key_2024'

# Configuração do banco de dados
def init_db():
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'garcom',
            ativo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')
    
    # Tabela de categorias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    # Tabela de produtos
    cursor.execute('''
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
            ativo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (categoria_id) REFERENCES categorias (id)
        )
    ''')
    
    # Tabela de mesas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mesas (
            id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'livre',
            pedido_aberto INTEGER DEFAULT 0,
            total REAL DEFAULT 0.0,
            qr_code TEXT,
            cliente_solicitou_conta INTEGER DEFAULT 0,
            observacoes_cliente TEXT,
            cliente_nome TEXT,
            cliente_telefone TEXT,
            opened_at TEXT,
            closed_at TEXT
        )
    ''')
    
    # Tabela de pedidos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesa_id INTEGER,
            tipo TEXT NOT NULL,
            status TEXT DEFAULT 'aberto',
            total REAL DEFAULT 0.0,
            usuario_id INTEGER,
            cliente_nome TEXT,
            cliente_telefone TEXT,
            observacoes TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            closed_at TEXT,
            FOREIGN KEY (mesa_id) REFERENCES mesas (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabela de itens do pedido
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            produto_id INTEGER,
            produto_nome TEXT,
            tamanho TEXT,
            quantidade INTEGER DEFAULT 1,
            preco_unitario REAL,
            subtotal REAL,
            sabor2_id INTEGER,
            sabor2_nome TEXT,
            observacoes TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (pedido_id) REFERENCES pedidos (id),
            FOREIGN KEY (produto_id) REFERENCES produtos (id)
        )
    ''')
    
    # Tabela de configurações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY,
            nome_sistema TEXT DEFAULT 'PizzaSystem',
            logo_sistema TEXT,
            telefone_whatsapp TEXT DEFAULT '5511999999999',
            endereco TEXT,
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')
    
    # Tabela de solicitações de conta
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solicitacoes_conta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesa_id INTEGER,
            observacoes TEXT,
            status TEXT DEFAULT 'pendente',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            atendido_por INTEGER,
            atendido_at TEXT,
            FOREIGN KEY (mesa_id) REFERENCES mesas (id),
            FOREIGN KEY (atendido_por) REFERENCES usuarios (id)
        )
    ''')
    
    # Inserir dados iniciais
    # Usuário admin padrão
    admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, tipo) 
        VALUES (?, ?, ?)
    ''', ('admin', admin_password, 'admin'))
    
    # Usuário garçom padrão
    garcom_password = hashlib.sha256('garcom123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (username, password, tipo) 
        VALUES (?, ?, ?)
    ''', ('garcom', garcom_password, 'garcom'))
    
    # Configurações padrão
    cursor.execute('''
        INSERT OR IGNORE INTO configuracoes (id, nome_sistema) 
        VALUES (1, 'PizzaSystem Pro')
    ''')
    
    # Categorias padrão
    categorias = ['Pizzas', 'Refrigerantes', 'Adicionais', 'Sobremesas']
    for categoria in categorias:
        cursor.execute('INSERT OR IGNORE INTO categorias (nome) VALUES (?)', (categoria,))
    
    # Mesas (1 a 15) com QR codes
    for i in range(1, 16):
        cursor.execute('SELECT id FROM mesas WHERE id = ?', (i,))
        if not cursor.fetchone():
            qr_code = gerar_qr_code_mesa(i)
            cursor.execute('INSERT INTO mesas (id, qr_code) VALUES (?, ?)', (i, qr_code))
    
    # Produtos exemplo com fotos
    pizzas = [
        ('Pizza Margherita', 'Molho de tomate, mussarela, manjericão fresco e azeite', 28.00, 38.00, 48.00, 58.00, 'https://images.pexels.com/photos/315755/pexels-photo-315755.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Pizza Calabresa', 'Molho de tomate, mussarela, calabresa fatiada e cebola roxa', 30.00, 40.00, 50.00, 60.00, 'https://images.pexels.com/photos/1049626/pexels-photo-1049626.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Pizza Portuguesa', 'Molho de tomate, mussarela, presunto, ovos, cebola e azeitona', 32.00, 42.00, 52.00, 62.00, 'https://images.pexels.com/photos/2619970/pexels-photo-2619970.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Pizza Frango Catupiry', 'Molho de tomate, mussarela, frango desfiado e catupiry', 34.00, 44.00, 54.00, 64.00, 'https://images.pexels.com/photos/2762942/pexels-photo-2762942.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Pizza Pepperoni', 'Molho de tomate, mussarela e pepperoni', 32.00, 42.00, 52.00, 62.00, 'https://images.pexels.com/photos/1653877/pexels-photo-1653877.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Pizza Quatro Queijos', 'Molho de tomate, mussarela, provolone, parmesão e gorgonzola', 36.00, 46.00, 56.00, 66.00, 'https://images.pexels.com/photos/825661/pexels-photo-825661.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Pizza Vegetariana', 'Molho de tomate, mussarela, tomate, pimentão, cebola e azeitona', 30.00, 40.00, 50.00, 60.00, 'https://images.pexels.com/photos/1146760/pexels-photo-1146760.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Pizza Bacon', 'Molho de tomate, mussarela, bacon crocante e cebola', 33.00, 43.00, 53.00, 63.00, 'https://images.pexels.com/photos/365459/pexels-photo-365459.jpeg?auto=compress&cs=tinysrgb&w=800')
    ]
    
    for pizza in pizzas:
        cursor.execute('''
            INSERT OR IGNORE INTO produtos (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?)
        ''', pizza)
    
    # Refrigerantes
    refrigerantes = [
        ('Coca-Cola 350ml', 'Refrigerante Coca-Cola lata 350ml gelada', 6.00, None, None, None, 'https://images.pexels.com/photos/50593/coca-cola-cold-drink-soft-drink-coke-50593.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Guaraná 350ml', 'Refrigerante Guaraná Antártica lata 350ml', 6.00, None, None, None, 'https://images.pexels.com/photos/1292294/pexels-photo-1292294.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Fanta Laranja 350ml', 'Refrigerante Fanta Laranja lata 350ml', 6.00, None, None, None, 'https://images.pexels.com/photos/1292294/pexels-photo-1292294.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Água Mineral 500ml', 'Água mineral natural 500ml', 3.00, None, None, None, 'https://images.pexels.com/photos/416528/pexels-photo-416528.jpeg?auto=compress&cs=tinysrgb&w=800')
    ]
    
    for refri in refrigerantes:
        cursor.execute('''
            INSERT OR IGNORE INTO produtos (nome, descricao, categoria_id, preco_p, foto)
            VALUES (?, ?, 2, ?, ?)
        ''', (refri[0], refri[1], refri[2], refri[5]))
    
    # Adicionais
    adicionais = [
        ('Borda Catupiry', 'Borda recheada com catupiry cremoso', 8.00, None, None, None, 'https://images.pexels.com/photos/708587/pexels-photo-708587.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Borda Cheddar', 'Borda recheada com queijo cheddar', 8.00, None, None, None, 'https://images.pexels.com/photos/708587/pexels-photo-708587.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Batata Frita', 'Porção de batata frita crocante', 15.00, None, None, None, 'https://images.pexels.com/photos/1893556/pexels-photo-1893556.jpeg?auto=compress&cs=tinysrgb&w=800')
    ]
    
    for adicional in adicionais:
        cursor.execute('''
            INSERT OR IGNORE INTO produtos (nome, descricao, categoria_id, preco_p, foto)
            VALUES (?, ?, 3, ?, ?)
        ''', (adicional[0], adicional[1], adicional[2], adicional[5]))
    
    # Sobremesas
    sobremesas = [
        ('Pudim de Leite', 'Pudim caseiro com calda de caramelo', 12.00, None, None, None, 'https://images.pexels.com/photos/6210959/pexels-photo-6210959.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Brownie com Sorvete', 'Brownie quente com sorvete de baunilha', 15.00, None, None, None, 'https://images.pexels.com/photos/291528/pexels-photo-291528.jpeg?auto=compress&cs=tinysrgb&w=800'),
        ('Açaí na Tigela', 'Açaí puro com granola e frutas', 18.00, None, None, None, 'https://images.pexels.com/photos/4958792/pexels-photo-4958792.jpeg?auto=compress&cs=tinysrgb&w=800')
    ]
    
    for sobremesa in sobremesas:
        cursor.execute('''
            INSERT OR IGNORE INTO produtos (nome, descricao, categoria_id, preco_p, foto)
            VALUES (?, ?, 4, ?, ?)
        ''', (sobremesa[0], sobremesa[1], sobremesa[2], sobremesa[5]))
    
    conn.commit()
    conn.close()

def gerar_qr_code_mesa(mesa_id):
    """Gera QR code único para a mesa"""
    # URL que o cliente acessará ao escanear o QR code
    url = f"http://localhost:5000/mesa/{mesa_id}/cliente"
    
    # Criar QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # Criar imagem
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Salvar como base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return img_str

# Função para verificar login
def verificar_login():
    if 'user_id' not in session:
        return False
    return True

def verificar_admin():
    if not verificar_login() or session.get('user_tipo') != 'admin':
        return False
    return True

def verificar_garcom_ou_admin():
    if not verificar_login():
        return False
    return session.get('user_tipo') in ['admin', 'garcom']

def get_configuracoes():
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nome_sistema, logo_sistema, telefone_whatsapp, endereco FROM configuracoes WHERE id = 1')
    config = cursor.fetchone()
    conn.close()
    if config:
        return {
            'nome_sistema': config[0],
            'logo_sistema': config[1],
            'telefone_whatsapp': config[2],
            'endereco': config[3]
        }
    return {
        'nome_sistema': 'PizzaSystem Pro',
        'logo_sistema': None,
        'telefone_whatsapp': '5511999999999',
        'endereco': 'Rua das Pizzas, 123'
    }

# Rota principal
@app.route('/')
def index():
    if verificar_login():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    config = get_configuracoes()
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        conn = sqlite3.connect('pizzaria.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, tipo FROM usuarios WHERE username = ? AND password = ? AND ativo = 1', 
                      (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['user_tipo'] = user[2]
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('login.html', config=config)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
def dashboard():
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Estatísticas do dia
    hoje = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM pedidos WHERE DATE(created_at) = ? AND status = "fechado"', (hoje,))
    pedidos_hoje = cursor.fetchone()[0]
    
    cursor.execute('SELECT COALESCE(SUM(total), 0) FROM pedidos WHERE DATE(created_at) = ? AND status = "fechado"', (hoje,))
    vendas_hoje = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM mesas WHERE status = "ocupada"')
    mesas_ocupadas = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM produtos WHERE ativo = 1')
    total_produtos = cursor.fetchone()[0]
    
    # Solicitações de conta pendentes
    cursor.execute('SELECT COUNT(*) FROM solicitacoes_conta WHERE status = "pendente"')
    solicitacoes_pendentes = cursor.fetchone()[0]
    
    # Pedidos da semana (últimos 7 dias)
    cursor.execute('''
        SELECT DATE(created_at) as data, COUNT(*) as quantidade, SUM(total) as valor
        FROM pedidos 
        WHERE created_at >= datetime('now', '-7 days') AND status = 'fechado'
        GROUP BY DATE(created_at)
        ORDER BY data
    ''')
    vendas_semana = cursor.fetchall()
    
    # Produtos mais vendidos
    cursor.execute('''
        SELECT ip.produto_nome, SUM(ip.quantidade) as total_vendido
        FROM itens_pedido ip
        JOIN pedidos p ON ip.pedido_id = p.id
        WHERE p.created_at >= datetime('now', '-30 days') AND p.status = 'fechado'
        GROUP BY ip.produto_nome
        ORDER BY total_vendido DESC
        LIMIT 5
    ''')
    produtos_populares = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html',
                         config=config,
                         pedidos_hoje=pedidos_hoje,
                         vendas_hoje=vendas_hoje,
                         mesas_ocupadas=mesas_ocupadas,
                         total_produtos=total_produtos,
                         solicitacoes_pendentes=solicitacoes_pendentes,
                         vendas_semana=vendas_semana,
                         produtos_populares=produtos_populares)

# Mesas
@app.route('/mesas')
def mesas():
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.id, m.status, m.total, m.cliente_solicitou_conta,
               CASE WHEN p.id IS NOT NULL THEN p.id ELSE 0 END as pedido_id,
               CASE WHEN sc.id IS NOT NULL THEN 1 ELSE 0 END as tem_solicitacao,
               m.opened_at, m.cliente_nome, m.cliente_telefone
        FROM mesas m
        LEFT JOIN pedidos p ON m.id = p.mesa_id AND p.status = 'aberto'
        LEFT JOIN solicitacoes_conta sc ON m.id = sc.mesa_id AND sc.status = 'pendente'
        ORDER BY m.id
    ''')
    mesas = cursor.fetchall()
    conn.close()
    
    return render_template('mesas.html', mesas=mesas, config=config)

# Continua com todas as outras rotas...
# (As rotas restantes seguem o mesmo padrão do código original)

@app.route('/adicionar_usuario')
def adicionar_usuario():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    return render_template('adicionar_usuario.html', config=config)

@app.route('/adicionar_usuario', methods=['POST'])
def salvar_usuario():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()
    tipo = request.form['tipo']
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO usuarios (username, password, tipo) VALUES (?, ?, ?)', 
                      (username, password, tipo))
        conn.commit()
        flash('Usuário adicionado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash('Nome de usuário já existe!', 'error')
    
    conn.close()
    return redirect(url_for('usuarios'))

@app.route('/usuario/<int:usuario_id>/editar')
def editar_usuario(usuario_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, tipo, ativo FROM usuarios WHERE id = ?', (usuario_id,))
    usuario = cursor.fetchone()
    conn.close()
    
    if not usuario:
        flash('Usuário não encontrado!', 'error')
        return redirect(url_for('usuarios'))
    
    return render_template('editar_usuario.html', usuario=usuario, config=config)

@app.route('/usuario/<int:usuario_id>/toggle')
def toggle_usuario(usuario_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    if usuario_id == session['user_id']:
        flash('Você não pode desativar seu próprio usuário!', 'error')
        return redirect(url_for('usuarios'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET ativo = NOT ativo WHERE id = ?', (usuario_id,))
    conn.commit()
    conn.close()
    
    flash('Status do usuário alterado!', 'success')
    return redirect(url_for('usuarios'))

@app.route('/adicionar_item_retirada/<int:pedido_id>', methods=['POST'])
def adicionar_item_retirada(pedido_id):
    if not verificar_login():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    produto_id = request.form['produto_id']
    tamanho = request.form.get('tamanho', 'P')
    quantidade = int(request.form.get('quantidade', 1))
    observacoes = request.form.get('observacoes', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar produto e preço
    cursor.execute('SELECT nome, preco_p, preco_m, preco_g, preco_familia FROM produtos WHERE id = ?', (produto_id,))
    produto = cursor.fetchone()
    
    if produto:
        precos = {'P': produto[1], 'M': produto[2], 'G': produto[3], 'Família': produto[4]}
        preco_unitario = precos.get(tamanho, produto[1]) or 0
        subtotal = preco_unitario * quantidade
        
        # Adicionar item
        cursor.execute('''
            INSERT INTO itens_pedido (pedido_id, produto_id, produto_nome, tamanho, 
                                    quantidade, preco_unitario, subtotal, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pedido_id, produto_id, produto[0], tamanho, quantidade, preco_unitario, subtotal, observacoes))
        
        # Atualizar total do pedido
        cursor.execute('SELECT SUM(subtotal) FROM itens_pedido WHERE pedido_id = ?', (pedido_id,))
        total = cursor.fetchone()[0] or 0
        
        cursor.execute('UPDATE pedidos SET total = ? WHERE id = ?', (total, pedido_id))
        
        conn.commit()
        flash('Item adicionado ao pedido!', 'success')
    
    conn.close()
    return redirect(url_for('editar_pedido_retirada', pedido_id=pedido_id))

@app.route('/remover_item/<int:item_id>')
def remover_item_pedido(item_id):
    if not verificar_login():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar pedido_id antes de remover
    cursor.execute('SELECT pedido_id FROM itens_pedido WHERE id = ?', (item_id,))
    result = cursor.fetchone()
    
    if result:
        pedido_id = result[0]
        
        # Remover item
        cursor.execute('DELETE FROM itens_pedido WHERE id = ?', (item_id,))
        
        # Atualizar total do pedido
        cursor.execute('SELECT SUM(subtotal) FROM itens_pedido WHERE pedido_id = ?', (pedido_id,))
        total = cursor.fetchone()[0] or 0
        
        cursor.execute('UPDATE pedidos SET total = ? WHERE id = ?', (total, pedido_id))
        
        conn.commit()
        flash('Item removido do pedido!', 'success')
        
        # Verificar se é pedido de mesa ou retirada
        cursor.execute('SELECT mesa_id, tipo FROM pedidos WHERE id = ?', (pedido_id,))
        pedido = cursor.fetchone()
        
        if pedido and pedido[1] == 'retirada':
            conn.close()
            return redirect(url_for('editar_pedido_retirada', pedido_id=pedido_id))
        elif pedido and pedido[0]:
            # Atualizar total da mesa
            cursor.execute('UPDATE mesas SET total = ? WHERE id = ?', (total, pedido[0]))
            conn.commit()
            conn.close()
            return redirect(url_for('pedido_mesa', mesa_id=pedido[0]))
    
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/alterar_status_pedido/<int:pedido_id>/<status>')
def alterar_status_pedido(pedido_id, status):
    if not verificar_login():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE pedidos SET status = ? WHERE id = ?', (status, pedido_id))
    conn.commit()
    conn.close()
    
    status_msg = {
        'preparando': 'Pedido em preparo!',
        'pronto': 'Pedido pronto para retirada!',
        'entregue': 'Pedido entregue!'
    }
    
    flash(status_msg.get(status, 'Status alterado!'), 'success')
    return redirect(url_for('retirada'))

@app.route('/finalizar_pedido_retirada/<int:pedido_id>')
def finalizar_pedido_retirada(pedido_id):
    if not verificar_login():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE pedidos SET status = "fechado", closed_at = datetime("now", "localtime") WHERE id = ?', 
                  (pedido_id,))
    conn.commit()
    conn.close()
    
    flash('Pedido finalizado com sucesso!', 'success')
    return redirect(url_for('retirada'))

@app.route('/ver_pedido_mesa/<int:mesa_id>')
def ver_pedido_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar pedido da mesa
    cursor.execute('''
        SELECT p.id, p.total, p.created_at, p.observacoes
        FROM pedidos p
        WHERE p.mesa_id = ? AND p.status = 'aberto'
    ''', (mesa_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Nenhum pedido encontrado para esta mesa!', 'error')
        return redirect(url_for('mesas'))
    
    # Buscar itens do pedido
    cursor.execute('''
        SELECT id, produto_nome, tamanho, quantidade, preco_unitario, subtotal, observacoes
        FROM itens_pedido WHERE pedido_id = ?
    ''', (pedido[0],))
    itens = cursor.fetchall()
    
    conn.close()
    
    return render_template('ver_pedido_mesa.html', 
                         mesa_id=mesa_id,
                         pedido=pedido,
                         itens=itens,
                         config=config)

# Rotas de relatórios (placeholder)
@app.route('/relatorio/vendas')
def relatorio_vendas():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar geração de relatório de vendas
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('relatorios'))

@app.route('/relatorio/produtos')
def relatorio_produtos():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar geração de relatório de produtos
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('relatorios'))

@app.route('/relatorio/mesas')
def relatorio_mesas():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar geração de relatório de mesas
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('relatorios'))

@app.route('/relatorio/hoje')
def relatorio_hoje():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar relatório de hoje
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('relatorios'))

@app.route('/relatorio/semana')
def relatorio_semana():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar relatório da semana
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('relatorios'))

@app.route('/relatorio/mes')
def relatorio_mes():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar relatório do mês
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('relatorios'))

@app.route('/relatorio/geral')
def relatorio_geral():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar relatório geral
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('relatorios'))

# Rotas de configurações
@app.route('/salvar_configuracoes', methods=['POST'])
def salvar_configuracoes():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    nome_sistema = request.form['nome_sistema']
    endereco = request.form.get('endereco', '')
    telefone_whatsapp = request.form.get('telefone_whatsapp', '')
    logo_sistema = request.form.get('logo_sistema', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE configuracoes 
        SET nome_sistema = ?, endereco = ?, telefone_whatsapp = ?, logo_sistema = ?,
            updated_at = datetime('now', 'localtime')
        WHERE id = 1
    ''', (nome_sistema, endereco, telefone_whatsapp, logo_sistema))
    conn.commit()
    conn.close()
    
    flash('Configurações salvas com sucesso!', 'success')
    return redirect(url_for('configuracoes'))

@app.route('/backup_sistema')
def backup_sistema():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar backup
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('configuracoes'))

@app.route('/gerenciar_categorias')
def gerenciar_categorias():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    # Implementar gerenciamento de categorias
    flash('Funcionalidade em desenvolvimento!', 'warning')
    return redirect(url_for('configuracoes'))

@app.route('/limpar_pedidos_antigos')
def limpar_pedidos_antigos():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pedidos WHERE created_at < datetime('now', '-30 days')")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    flash(f'{deleted} pedidos antigos removidos!', 'success')
    return redirect(url_for('configuracoes'))

@app.route('/resetar_mesas')
def resetar_mesas():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE mesas SET status = 'livre', total = 0, cliente_solicitou_conta = 0, 
                       observacoes_cliente = NULL, closed_at = datetime('now', 'localtime')
    ''')
    cursor.execute("UPDATE pedidos SET status = 'fechado' WHERE status = 'aberto' AND mesa_id IS NOT NULL")
    conn.commit()
    conn.close()
    
    flash('Todas as mesas foram liberadas!', 'success')
    return redirect(url_for('configuracoes'))

@app.route('/mesa/<int:mesa_id>/abrir')
def abrir_mesa_form(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    return render_template('abrir_mesa.html', mesa_id=mesa_id, config=config)

@app.route('/mesa/<int:mesa_id>/abrir', methods=['POST'])
def abrir_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    cliente_nome = request.form.get('cliente_nome', '').strip()
    cliente_telefone = request.form.get('cliente_telefone', '').strip()
    
    if not cliente_nome:
        flash('Nome do cliente é obrigatório!', 'error')
        return redirect(url_for('abrir_mesa_form', mesa_id=mesa_id))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Verificar se mesa já está ocupada
    cursor.execute('SELECT status FROM mesas WHERE id = ?', (mesa_id,))
    mesa = cursor.fetchone()
    
    if mesa and mesa[0] == 'livre':
        # Abrir mesa
        cursor.execute('''
            UPDATE mesas SET status = "ocupada", cliente_nome = ?, cliente_telefone = ?, 
                           opened_at = datetime("now", "localtime") WHERE id = ?
        ''', (cliente_nome, cliente_telefone, mesa_id))
        
        # Criar pedido
        cursor.execute('''
            INSERT INTO pedidos (mesa_id, tipo, usuario_id) 
            VALUES (?, ?, ?)
        ''', (mesa_id, 'salao', session['user_id']))
        
        conn.commit()
        flash(f'Mesa {mesa_id} aberta com sucesso!', 'success')
    else:
        flash(f'Mesa {mesa_id} já está ocupada!', 'error')
    
    conn.close()
    return redirect(url_for('mesas'))

# Solicitações de conta
@app.route('/solicitacoes')
def solicitacoes():
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.mesa_id, s.observacoes, s.created_at, s.status,
               u.username as atendido_por, s.atendido_at
        FROM solicitacoes_conta s
        LEFT JOIN usuarios u ON s.atendido_por = u.id
        ORDER BY s.created_at DESC
    ''')
    solicitacoes = cursor.fetchall()
    conn.close()
    
    return render_template('solicitacoes.html', solicitacoes=solicitacoes, config=config)

@app.route('/solicitacao/<int:solicitacao_id>/atender')
def atender_solicitacao(solicitacao_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE solicitacoes_conta 
        SET status = 'atendida', atendido_por = ?, atendido_at = datetime('now', 'localtime')
        WHERE id = ?
    ''', (session['user_id'], solicitacao_id))
    conn.commit()
    conn.close()
    
    flash('Solicitação atendida com sucesso!', 'success')
    return redirect(url_for('solicitacoes'))

# Pedidos para mesa
@app.route('/mesa/<int:mesa_id>/pedido')
def pedido_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Verificar se mesa está ocupada
    cursor.execute('SELECT status FROM mesas WHERE id = ?', (mesa_id,))
    mesa = cursor.fetchone()
    
    if not mesa or mesa[0] != 'ocupada':
        flash('Mesa não está ocupada!', 'error')
        return redirect(url_for('mesas'))
    
    # Buscar produtos por categoria
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1 ORDER BY nome')
    categorias = cursor.fetchall()
    
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria, 
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia, p.foto
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    # Buscar pedido atual da mesa
    cursor.execute('SELECT id FROM pedidos WHERE mesa_id = ? AND status = "aberto"', (mesa_id,))
    pedido = cursor.fetchone()
    
    conn.close()
    
    return render_template('pedido_mesa.html', 
                         mesa_id=mesa_id, 
                         categorias=categorias, 
                         produtos=produtos,
                         pedido_id=pedido[0] if pedido else None,
                         config=config)

@app.route('/mesa/<int:mesa_id>/adicionar_item', methods=['POST'])
def adicionar_item_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    produto_id = request.form['produto_id']
    tamanho = request.form.get('tamanho', 'P')
    quantidade = int(request.form.get('quantidade', 1))
    observacoes = request.form.get('observacoes', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar ou criar pedido
    cursor.execute('SELECT id FROM pedidos WHERE mesa_id = ? AND status = "aberto"', (mesa_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        cursor.execute('''
            INSERT INTO pedidos (mesa_id, tipo, usuario_id) 
            VALUES (?, ?, ?)
        ''', (mesa_id, 'salao', session['user_id']))
        pedido_id = cursor.lastrowid
    else:
        pedido_id = pedido[0]
    
    # Buscar produto e preço
    cursor.execute('SELECT nome, preco_p, preco_m, preco_g, preco_familia FROM produtos WHERE id = ?', (produto_id,))
    produto = cursor.fetchone()
    
    if produto:
        precos = {'P': produto[1], 'M': produto[2], 'G': produto[3], 'Família': produto[4]}
        preco_unitario = precos.get(tamanho, produto[1]) or 0
        subtotal = preco_unitario * quantidade
        
        # Adicionar item
        cursor.execute('''
            INSERT INTO itens_pedido (pedido_id, produto_id, produto_nome, tamanho, 
                                    quantidade, preco_unitario, subtotal, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pedido_id, produto_id, produto[0], tamanho, quantidade, preco_unitario, subtotal, observacoes))
        
        # Atualizar total do pedido
        cursor.execute('SELECT SUM(subtotal) FROM itens_pedido WHERE pedido_id = ?', (pedido_id,))
        total = cursor.fetchone()[0] or 0
        
        cursor.execute('UPDATE pedidos SET total = ? WHERE id = ?', (total, pedido_id))
        cursor.execute('UPDATE mesas SET total = ? WHERE id = ?', (total, mesa_id))
        
        conn.commit()
        flash('Item adicionado ao pedido!', 'success')
    
    conn.close()
    return redirect(url_for('pedido_mesa', mesa_id=mesa_id))

def gerar_relatorio_mesa(mesa_id, pedido_data, itens_data, cliente_nome, cliente_telefone, total):
    """Gera relatório da mesa em formato texto para WhatsApp"""
    config = get_configuracoes()
    
    relatorio = f"""🍕 *{config['nome_sistema']}*

📋 *RELATÓRIO DA MESA {mesa_id}*

👤 *Cliente:* {cliente_nome}
📱 *Telefone:* {cliente_telefone}
📅 *Data:* {pedido_data.split()[0] if pedido_data else 'N/A'}
⏰ *Horário:* {pedido_data.split()[1][:5] if ' ' in pedido_data else 'N/A'}

📝 *ITENS CONSUMIDOS:*
"""
    
    for item in itens_data:
        produto_nome = item[1]
        tamanho = item[2]
        quantidade = item[3]
        subtotal = item[5]
        observacoes = item[6] if item[6] else ""
        
        relatorio += f"\n• {produto_nome} ({tamanho})"
        relatorio += f"\n  Qtd: {quantidade} - R$ {subtotal:.2f}"
        if observacoes:
            relatorio += f"\n  Obs: {observacoes}"
        relatorio += "\n"
    
    relatorio += f"\n💰 *TOTAL: R$ {total:.2f}*"
    
    if config.get('endereco'):
        relatorio += f"\n\n📍 {config['endereco']}"
    
    relatorio += "\n\n✨ Obrigado pela preferência!"
    relatorio += "\n🍕 Volte sempre!"
    
    return relatorio

def enviar_whatsapp(telefone, mensagem):
    """Gera link do WhatsApp com a mensagem"""
    # Limpar telefone (remover caracteres especiais)
    telefone_limpo = ''.join(filter(str.isdigit, telefone))
    
    # Se não tem código do país, adicionar 55 (Brasil)
    if len(telefone_limpo) == 11:  # Celular brasileiro sem código
        telefone_limpo = '55' + telefone_limpo
    elif len(telefone_limpo) == 10:  # Fixo brasileiro sem código
        telefone_limpo = '55' + telefone_limpo
    
    # Codificar mensagem para URL
    mensagem_encoded = urllib.parse.quote(mensagem)
    
    # Gerar link do WhatsApp
    whatsapp_url = f"https://wa.me/{telefone_limpo}?text={mensagem_encoded}"
    
    return whatsapp_url

# Fechar mesa
@app.route('/mesa/<int:mesa_id>/fechar')
def fechar_mesa(mesa_id):
    if not verificar_garcom_ou_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar dados da mesa e pedido
    cursor.execute('''
        SELECT p.id, p.total, p.created_at, m.cliente_nome, m.cliente_telefone
        FROM pedidos p
        JOIN mesas m ON p.mesa_id = m.id
        WHERE p.mesa_id = ? AND p.status = 'aberto'
    ''', (mesa_id,))
    pedido = cursor.fetchone()
    
    if pedido:
        # Buscar itens do pedido
        cursor.execute('''
            SELECT id, produto_nome, tamanho, quantidade, preco_unitario, subtotal, observacoes
            FROM itens_pedido WHERE pedido_id = ?
        ''', (pedido[0],))
        itens = cursor.fetchall()
        
        # Fechar pedido
        cursor.execute('UPDATE pedidos SET status = "fechado", closed_at = datetime("now", "localtime") WHERE id = ?', 
                      (pedido[0],))
        
        # Liberar mesa
        cursor.execute('''
            UPDATE mesas SET status = "livre", total = 0, cliente_solicitou_conta = 0,
                           observacoes_cliente = NULL, cliente_nome = NULL, cliente_telefone = NULL,
                           closed_at = datetime("now", "localtime") 
            WHERE id = ?
        ''', (mesa_id,))
        
        # Marcar solicitações como atendidas
        cursor.execute('''
            UPDATE solicitacoes_conta 
            SET status = 'atendida', atendido_por = ?, atendido_at = datetime('now', 'localtime')
            WHERE mesa_id = ? AND status = 'pendente'
        ''', (session['user_id'], mesa_id))
        
        conn.commit()
        
        # Gerar relatório e link do WhatsApp se tiver telefone
        if pedido[4]:  # cliente_telefone
            relatorio = gerar_relatorio_mesa(mesa_id, pedido[2], itens, pedido[3], pedido[4], pedido[1])
            whatsapp_url = enviar_whatsapp(pedido[4], relatorio)
            
            conn.close()
            return render_template('fechar_mesa.html', 
                                 mesa_id=mesa_id,
                                 cliente_nome=pedido[3],
                                 cliente_telefone=pedido[4],
                                 total=pedido[1],
                                 whatsapp_url=whatsapp_url,
                                 relatorio=relatorio,
                                 config=config)
        else:
            flash(f'Mesa {mesa_id} fechada com sucesso! Total: R$ {pedido[1]:.2f}', 'success')
    
    conn.close()
    return redirect(url_for('mesas'))

# Pedidos para retirada
@app.route('/retirada')
def retirada():
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar produtos por categoria
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1 ORDER BY nome')
    categorias = cursor.fetchall()
    
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria, 
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia, p.foto
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    # Buscar pedidos de retirada em aberto
    cursor.execute('''
        SELECT p.id, p.cliente_nome, p.cliente_telefone, p.total, p.created_at, p.status
        FROM pedidos p
        WHERE p.tipo = 'retirada' AND p.status IN ('aberto', 'preparando')
        ORDER BY p.created_at DESC
    ''')
    pedidos_retirada = cursor.fetchall()
    
    conn.close()
    
    return render_template('retirada.html', 
                         categorias=categorias, 
                         produtos=produtos,
                         pedidos_retirada=pedidos_retirada,
                         config=config)

@app.route('/retirada/novo', methods=['POST'])
def novo_pedido_retirada():
    if not verificar_login():
        return redirect(url_for('login'))
    
    cliente_nome = request.form['cliente_nome']
    cliente_telefone = request.form.get('cliente_telefone', '')
    observacoes = request.form.get('observacoes', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Criar pedido
    cursor.execute('''
        INSERT INTO pedidos (tipo, usuario_id, cliente_nome, cliente_telefone, observacoes)
        VALUES (?, ?, ?, ?, ?)
    ''', ('retirada', session['user_id'], cliente_nome, cliente_telefone, observacoes))
    
    pedido_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    flash('Pedido criado com sucesso!', 'success')
    return redirect(url_for('editar_pedido_retirada', pedido_id=pedido_id))

@app.route('/retirada/<int:pedido_id>/editar')
def editar_pedido_retirada(pedido_id):
    if not verificar_login():
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Buscar pedido
    cursor.execute('''
        SELECT id, cliente_nome, cliente_telefone, total, observacoes, status
        FROM pedidos WHERE id = ? AND tipo = 'retirada'
    ''', (pedido_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Pedido não encontrado!', 'error')
        return redirect(url_for('retirada'))
    
    # Buscar produtos por categoria
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1 ORDER BY nome')
    categorias = cursor.fetchall()
    
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria, 
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia, p.foto
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    # Buscar itens do pedido
    cursor.execute('''
        SELECT id, produto_nome, tamanho, quantidade, preco_unitario, subtotal, observacoes
        FROM itens_pedido WHERE pedido_id = ?
    ''', (pedido_id,))
    itens = cursor.fetchall()
    
    conn.close()
    
    return render_template('editar_pedido_retirada.html', 
                         pedido=pedido,
                         categorias=categorias, 
                         produtos=produtos,
                         itens=itens,
                         config=config)

# Produtos (Admin)
@app.route('/produtos')
def produtos():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1 ORDER BY nome')
    categorias = cursor.fetchall()
    
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria, 
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia, p.foto, p.ativo
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    conn.close()
    
    return render_template('produtos.html', produtos=produtos, categorias=categorias, config=config)

@app.route('/produtos/adicionar', methods=['POST'])
def adicionar_produto():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    nome = request.form['nome']
    descricao = request.form.get('descricao', '')
    categoria_id = request.form['categoria_id']
    preco_p = request.form.get('preco_p') or None
    preco_m = request.form.get('preco_m') or None
    preco_g = request.form.get('preco_g') or None
    preco_familia = request.form.get('preco_familia') or None
    foto = request.form.get('foto', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO produtos (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto))
    
    conn.commit()
    conn.close()
    
    flash('Produto adicionado com sucesso!', 'success')
    return redirect(url_for('produtos'))

@app.route('/produtos/<int:produto_id>/toggle')
def toggle_produto(produto_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE produtos SET ativo = NOT ativo WHERE id = ?', (produto_id,))
    conn.commit()
    conn.close()
    
    flash('Status do produto alterado!', 'success')
    return redirect(url_for('produtos'))

@app.route('/produtos/<int:produto_id>/editar')
def editar_produto(produto_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, p.categoria_id, p.preco_p, p.preco_m, 
               p.preco_g, p.preco_familia, p.foto, p.ativo
        FROM produtos p WHERE p.id = ?
    ''', (produto_id,))
    produto = cursor.fetchone()
    
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1 ORDER BY nome')
    categorias = cursor.fetchall()
    
    conn.close()
    
    if not produto:
        flash('Produto não encontrado!', 'error')
        return redirect(url_for('produtos'))
    
    return render_template('editar_produto.html', produto=produto, categorias=categorias, config=config)

@app.route('/produtos/<int:produto_id>/editar', methods=['POST'])
def salvar_edicao_produto(produto_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    nome = request.form['nome']
    descricao = request.form.get('descricao', '')
    categoria_id = request.form['categoria_id']
    preco_p = request.form.get('preco_p') or None
    preco_m = request.form.get('preco_m') or None
    preco_g = request.form.get('preco_g') or None
    preco_familia = request.form.get('preco_familia') or None
    foto = request.form.get('foto', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE produtos 
        SET nome = ?, descricao = ?, categoria_id = ?, preco_p = ?, preco_m = ?, 
            preco_g = ?, preco_familia = ?, foto = ?
        WHERE id = ?
    ''', (nome, descricao, categoria_id, preco_p, preco_m, preco_g, preco_familia, foto, produto_id))
    
    conn.commit()
    conn.close()
    
    flash('Produto atualizado com sucesso!', 'success')
    return redirect(url_for('produtos'))

@app.route('/usuarios/<int:usuario_id>/editar', methods=['POST'])
def salvar_edicao_usuario(usuario_id):
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    username = request.form['username']
    password = request.form.get('password', '').strip()
    tipo = request.form['tipo']
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    try:
        if password:  # Se nova senha foi fornecida
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('UPDATE usuarios SET username = ?, password = ?, tipo = ? WHERE id = ?', 
                          (username, password_hash, tipo, usuario_id))
        else:  # Manter senha atual
            cursor.execute('UPDATE usuarios SET username = ?, tipo = ? WHERE id = ?', 
                          (username, tipo, usuario_id))
        
        conn.commit()
        flash('Usuário atualizado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash('Nome de usuário já existe!', 'error')
    
    conn.close()
    return redirect(url_for('usuarios'))
# Usuários (Admin)
@app.route('/usuarios')
def usuarios():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, tipo, ativo, created_at FROM usuarios ORDER BY created_at DESC')
    usuarios = cursor.fetchall()
    conn.close()
    
    return render_template('usuarios.html', usuarios=usuarios, config=config)

# Relatórios (Admin)
@app.route('/relatorios')
def relatorios():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    return render_template('relatorios.html', config=config)

# Configurações (Admin)
@app.route('/configuracoes')
def configuracoes():
    if not verificar_admin():
        flash('Acesso negado!', 'error')
        return redirect(url_for('login'))
    
    config = get_configuracoes()
    return render_template('configuracoes.html', config=config)

# QR Code da mesa
@app.route('/mesa/<int:mesa_id>/qrcode')
def qrcode_mesa(mesa_id):
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('SELECT qr_code FROM mesas WHERE id = ?', (mesa_id,))
    mesa = cursor.fetchone()
    conn.close()
    
    if mesa and mesa[0]:
        # Decodificar base64 e retornar imagem
        import base64
        import io
        from flask import send_file
        
        img_data = base64.b64decode(mesa[0])
        img_buffer = io.BytesIO(img_data)
        img_buffer.seek(0)
        
        return send_file(img_buffer, mimetype='image/png')
    
    flash('QR Code não encontrado!', 'error')
    return redirect(url_for('mesas'))

# Interface do cliente (via QR Code)
@app.route('/mesa/<int:mesa_id>/cliente')
def cliente_mesa(mesa_id):
    config = get_configuracoes()
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Verificar se mesa existe
    cursor.execute('SELECT status FROM mesas WHERE id = ?', (mesa_id,))
    mesa = cursor.fetchone()
    
    if not mesa:
        return render_template('cliente_erro.html', 
                             erro="Mesa não encontrada!", 
                             config=config)
    
    # Buscar cardápio
    cursor.execute('''
        SELECT p.id, p.nome, p.descricao, c.nome as categoria, 
               p.preco_p, p.preco_m, p.preco_g, p.preco_familia, p.foto
        FROM produtos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.ativo = 1
        ORDER BY c.nome, p.nome
    ''')
    produtos = cursor.fetchall()
    
    cursor.execute('SELECT id, nome FROM categorias WHERE ativo = 1 ORDER BY nome')
    categorias = cursor.fetchall()
    
    conn.close()
    
    return render_template('cliente_mesa.html', 
                         mesa_id=mesa_id,
                         produtos=produtos,
                         categorias=categorias,
                         config=config)

@app.route('/mesa/<int:mesa_id>/solicitar_conta', methods=['POST'])
def solicitar_conta(mesa_id):
    observacoes = request.form.get('observacoes', '')
    
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    
    # Verificar se já existe solicitação pendente
    cursor.execute('SELECT id FROM solicitacoes_conta WHERE mesa_id = ? AND status = "pendente"', (mesa_id,))
    if cursor.fetchone():
        flash('Já existe uma solicitação pendente para esta mesa!', 'warning')
    else:
        # Criar solicitação
        cursor.execute('''
            INSERT INTO solicitacoes_conta (mesa_id, observacoes)
            VALUES (?, ?)
        ''', (mesa_id, observacoes))
        
        # Marcar na mesa
        cursor.execute('UPDATE mesas SET cliente_solicitou_conta = 1, observacoes_cliente = ? WHERE id = ?', 
                      (observacoes, mesa_id))
        
        conn.commit()
        flash('Conta solicitada com sucesso! Um garçom virá atendê-lo em breve.', 'success')
    
    conn.close()
    return redirect(url_for('cliente_mesa', mesa_id=mesa_id))

# API para notificações
@app.route('/api/notifications')
def api_notifications():
    conn = sqlite3.connect('pizzaria.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM solicitacoes_conta WHERE status = "pendente"')
    count = cursor.fetchone()[0]
    conn.close()
    return jsonify({'count': count})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)