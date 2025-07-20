# PizzaSystem Pro

Sistema completo de gerenciamento para pizzarias desenvolvido em Python Flask.

## Funcionalidades

- **Dashboard**: Visão geral das vendas, mesas e estatísticas
- **Gerenciamento de Mesas**: Controle visual do salão com QR codes
- **Pedidos**: Sistema completo para pedidos de mesa e retirada
- **Produtos**: Gerenciamento do cardápio com categorias
- **Usuários**: Sistema de autenticação com diferentes níveis de acesso
- **Solicitações**: Clientes podem solicitar a conta via QR code
- **Relatórios**: Análise de vendas e performance
- **Interface do Cliente**: Acesso via QR code para visualizar cardápio

## Tecnologias Utilizadas

- **Backend**: Python Flask
- **Frontend**: HTML, Tailwind CSS, Jinja2
- **Banco de Dados**: SQLite3
- **Relatórios**: ReportLab
- **QR Codes**: qrcode + Pillow

## Instalação

1. Clone o repositório:
```bash
git clone <url-do-repositorio>
cd pizzasystem-pro
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute o sistema:
```bash
python app.py
```

4. Acesse no navegador:
```
http://localhost:5000
```

## Usuários Padrão

- **Admin**: 
  - Usuário: `admin`
  - Senha: `admin123`

- **Garçom**: 
  - Usuário: `garcom`
  - Senha: `garcom123`

## Estrutura do Projeto

```
pizzasystem-pro/
├── app.py              # Aplicação principal
├── requirements.txt    # Dependências
├── README.md          # Documentação
├── pizzaria.db        # Banco de dados (criado automaticamente)
└── templates/         # Templates HTML
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── mesas.html
    ├── produtos.html
    ├── usuarios.html
    ├── solicitacoes.html
    ├── retirada.html
    ├── pedido_mesa.html
    ├── editar_pedido_retirada.html
    ├── relatorios.html
    ├── configuracoes.html
    ├── cliente_mesa.html
    └── cliente_erro.html
```

## Funcionalidades por Tipo de Usuário

### Administrador
- Acesso completo ao sistema
- Gerenciamento de produtos e categorias
- Gerenciamento de usuários
- Relatórios e configurações
- Controle de mesas e pedidos

### Garçom
- Gerenciamento de mesas
- Criação e edição de pedidos
- Atendimento de solicitações de conta
- Pedidos para retirada

### Atendente
- Pedidos para retirada
- Visualização do dashboard

## Banco de Dados

O sistema utiliza SQLite3 com as seguintes tabelas:

- `usuarios`: Controle de acesso
- `categorias`: Categorias de produtos
- `produtos`: Cardápio da pizzaria
- `mesas`: Controle das mesas do salão
- `pedidos`: Pedidos de mesa e retirada
- `itens_pedido`: Itens dos pedidos
- `solicitacoes_conta`: Solicitações de conta dos clientes
- `configuracoes`: Configurações do sistema

## QR Codes

Cada mesa possui um QR code único que permite aos clientes:
- Visualizar o cardápio completo
- Solicitar a conta diretamente
- Ver informações da pizzaria

## Responsividade

O sistema é totalmente responsivo, funcionando perfeitamente em:
- Desktop
- Tablets
- Smartphones

## Suporte

Para suporte técnico, entre em contato com o desenvolvedor.

---

**Desenvolvido por João Layon**
© 2025 Todos os direitos reservados