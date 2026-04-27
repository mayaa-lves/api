# ============================================================
# API DO SISTEMA DE ARTESANATO - MAYA
# ============================================================
# Este arquivo contém todas as rotas da API:
# - Produtos (CRUD completo)
# - Materiais (CRUD completo)
# - Autenticação (login com JWT)
# ============================================================

from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, firestore
from auth import token_obrigatorio, gerar_token
from flask_cors import CORS
import os
from dotenv import load_dotenv
import json
from flasgger import Swagger

# Carrega as variáveis do arquivo .env (usuário/senha admin, chave secreta)
load_dotenv()

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÃO DO SWAGGER (DOCUMENTAÇÃO AUTOMÁTICA DA API)
# ============================================================
app.config['SWAGGER'] = {
    'openapi': '3.0.2'
}
swagger = Swagger(app, template_file='openapi.yaml')

# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")  # Chave para assinar os tokens JWT
# No seu app.py, substitua a linha do CORS por:
CORS(app, origins="*", supports_credentials=True, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])  # Permite que qualquer front-end acesse a API
ADM_USUARIO = os.getenv("ADM_USUARIO")  # Usuário admin (do .env)
ADM_SENHA = os.getenv("ADM_SENHA")      # Senha admin (do .env)

# ============================================================
# CONEXÃO COM O FIREBASE
# ============================================================
# Verifica se está rodando na Vercel (produção) ou localmente
if os.getenv("VERCEL"):
    # Na Vercel, as credenciais estão em uma variável de ambiente JSON
    cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_CREDENTIALS")))
else:
    # Localmente, as credenciais estão no arquivo firebase.json
    cred = credentials.Certificate("firebase.json")

firebase_admin.initialize_app(cred)
db = firestore.client()  # Cliente do Firestore para operações no banco

# ============================================================
# ROTA PRINCIPAL (BOAS-VINDAS)
# ============================================================
@app.route('/', methods=['GET'])
def home():
    """Rota raiz da API - retorna informações básicas"""
    return jsonify({
        "api": "API do sistema de artesanato (Treino)",
        "version": "1.0",
        "author": "Maya"
    }), 200

# ============================================================
# ROTA DE LOGIN (PÚBLICA)
# ============================================================
@app.route("/login", methods=["POST"])
def login():
    """
    Faz login e retorna um token JWT para usar nas rotas protegidas.
    ---
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              usuario: {type: string, example: "admin"}
              senha: {type: string, example: "123456"}
    responses:
      200:
        description: Login realizado com sucesso. Retorna token.
      401:
        description: Usuário ou senha inválidos.
    """
    dados = request.get_json()

    if not dados:
        return jsonify({"Error": "Envie os dados para login"}), 400
    
    usuario = dados.get('usuario')
    senha = dados.get('senha')

    if not usuario or not senha:
        return jsonify({"Error": "Usuário e senha são obrigatórios!"}), 400
    
    # Verifica se o usuário e senha correspondem ao que está no .env
    if usuario == ADM_USUARIO and senha == ADM_SENHA:
        token = gerar_token(usuario)
        return jsonify({"message": "Login realizado com sucesso!", "token": token}), 200
    
    return jsonify({"Error": "Usuário ou senha inválidos"}), 401

# ============================================================
# ROTAS PÚBLICAS (QUALQUER PESSOA PODE VER)
# ============================================================

@app.route('/produtos', methods=['GET'])
def listar_produtos():
    """
    Retorna todos os produtos cadastrados (vitrine pública).
    ---
    responses:
      200:
        description: Lista de produtos retornada com sucesso.
    """
    produtos = []
    lista = db.collection('produtos').stream()

    for item in lista:
        # Converte cada documento do Firebase em dicionário Python
        produtos.append(item.to_dict())

    return jsonify(produtos), 200


@app.route('/produtos/<int:id>', methods=['GET'])
def buscar_produto_by_id(id):
    """
    Busca um produto específico pelo ID.
    ---
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Produto encontrado.
      404:
        description: Produto não encontrado.
    """
    lista = db.collection('produtos').where('id', '==', id).stream()

    for item in lista:
        return jsonify(item.to_dict()), 200
    
    return jsonify({"error": "Produto não encontrado"}), 404

# ============================================================
# ROTAS PRIVADAS (PRECISAM DE TOKEN JWT)
# ============================================================

@app.route('/criarprodutos', methods=['POST'])
@token_obrigatorio
def criar_produto():
    """
    Cria um novo produto (apenas admin).
    ---
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [nome, preco, descricao, categoria, link_img]
            properties:
              nome: {type: string, example: "Vaso de Flores"}
              preco: {type: number, example: 25.50}
              descricao: {type: string, example: "Artesanato feito com limpa cachimbos"}
              categoria: {type: string, example: "Decoração"}
              link_img: {type: string, example: "https://..."}
              tempo_producao: {type: string, example: "3 dias úteis"}  # NOVO
              materiais_usados: {type: array, example: [{"id_material": 1, "quantidade": 5}]}  # NOVO
    responses:
      201:
        description: Produto criado com sucesso.
      400:
        description: Dados inválidos.
      401:
        description: Token obrigatório.
    """
    dados = request.get_json()

    # Validação dos campos obrigatórios
    if not dados or "nome" not in dados or "preco" not in dados or "descricao" not in dados or "categoria" not in dados or "link_img" not in dados:
        return jsonify({"error": "Dados inválidos!"}), 400

    try:
        # Gerar novo ID automático (sequencial)
        contador_ref = db.collection("contador").document("controle_id")
        contador_doc = contador_ref.get()
        ultimo_id = contador_doc.to_dict().get("ultimo_id", 0)
        novo_id = ultimo_id + 1
        contador_ref.update({"ultimo_id": novo_id})

        # Dados do produto (incluindo os novos campos)
        produto_data = {
            "id": novo_id,
            "nome": dados["nome"],
            "preco": dados["preco"],
            "descricao": dados["descricao"],
            "categoria": dados["categoria"],
            "link_img": dados["link_img"],
            "tempo_producao": dados.get("tempo_producao", "5 dias úteis"),  # Valor padrão
            "materiais_usados": dados.get("materiais_usados", [])           # Lista de materiais usados
        }
        
        db.collection("produtos").add(produto_data)
        
        return jsonify({"message": "Produto criado com sucesso!", "id": novo_id}), 201
    except Exception as e:
        return jsonify({"error": f"Erro ao criar produto: {str(e)}"}), 500


@app.route('/produtos/<int:id>', methods=['PUT'])
@token_obrigatorio
def put_produtos(id):
    """
    Atualiza um produto COMPLETAMENTE (todos os campos).
    ---
    security:
      - BearerAuth: []
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              nome: {type: string}
              preco: {type: number}
              descricao: {type: string}
              categoria: {type: string}
              link_img: {type: string}
              tempo_producao: {type: string}
              materiais_usados: {type: array}
    responses:
      200:
        description: Produto atualizado com sucesso.
      401:
        description: Token obrigatório.
    """
    dados = request.get_json()

    if not dados or "nome" not in dados or "preco" not in dados or "descricao" not in dados or "categoria" not in dados or "link_img" not in dados:
        return jsonify({"error": "Dados inválidos!"}), 400
    
    docs = db.collection("produtos").where("id", "==", id).limit(1).get()

    for doc in docs:
        doc_ref = db.collection("produtos").document(doc.id)
        doc_ref.update({
            "nome": dados["nome"],
            "preco": dados["preco"],
            "descricao": dados["descricao"],
            "categoria": dados["categoria"],
            "link_img": dados["link_img"],
            "tempo_producao": dados.get("tempo_producao", "5 dias úteis"),
            "materiais_usados": dados.get("materiais_usados", [])
        })

    return jsonify({"message": "Produto atualizado com sucesso!"}), 200


@app.route('/produtos/<int:id>', methods=['PATCH'])
@token_obrigatorio
def patch_produtos(id):
    """
    Atualiza UM OU MAIS campos do produto (atualização parcial).
    ---
    security:
      - BearerAuth: []
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            description: Envie APENAS os campos que quer alterar.
    responses:
      200:
        description: Produto atualizado com sucesso.
    """
    dados = request.get_json()
    
    docs = db.collection("produtos").where("id", "==", id).limit(1).get()

    for doc in docs:
        doc_ref = db.collection("produtos").document(doc.id)
        doc_ref.update(dados)

    return jsonify({"message": "Produto atualizado com sucesso!"}), 200


@app.route('/produtos/<int:id>', methods=['DELETE'])
@token_obrigatorio
def excluir_produto(id):
    """
    Exclui um produto do banco de dados.
    ---
    security:
      - BearerAuth: []
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Produto excluído com sucesso.
    """
    docs = db.collection("produtos").where("id", "==", id).limit(1).get()

    for doc in docs:
        doc_ref = db.collection("produtos").document(doc.id)
        doc_ref.delete()

    return jsonify({"message": "Produto excluído com sucesso!"}), 200

# ============================================================
# ROTAS PARA MATERIAIS (ESTOQUE)
# ============================================================

@app.route('/materiais', methods=['POST'])
@token_obrigatorio
def criar_material():
    """Cria um novo material no estoque"""
    dados = request.get_json()
    
    if not dados or "nome" not in dados or "quantidade" not in dados:
        return jsonify({"error": "Os campos 'nome' e 'quantidade' são obrigatórios!"}), 400
    
    try:
        # Gera ID automático para o material
        contador_ref = db.collection("contador_materiais").document("controle_id")
        contador_doc = contador_ref.get()
        
        if contador_doc.exists:
            ultimo_id = contador_doc.to_dict().get("ultimo_id", 0)
            novo_id = ultimo_id + 1
            contador_ref.update({"ultimo_id": novo_id})
        else:
            novo_id = 1
            contador_ref.set({"ultimo_id": 1})
        
        # Salva o material no Firestore
        db.collection("materiais").add({
            "id": novo_id,
            "nome": dados["nome"],
            "quantidade": dados["quantidade"],
            "quantidade_minima_alerta": dados.get("quantidade_minima_alerta", 10),
            "unidade": dados.get("unidade", "unidades")
        })
        
        return jsonify({"message": "Material criado com sucesso!", "id": novo_id}), 201
    except Exception as e:
        return jsonify({"error": f"Erro ao criar material: {str(e)}"}), 500


@app.route('/materiais', methods=['GET'])
@token_obrigatorio
def listar_materiais():
    """Lista todos os materiais do estoque"""
    try:
        materiais = []
        lista = db.collection('materiais').stream()
        
        for documento in lista:
            materiais.append(documento.to_dict())
        
        return jsonify(materiais), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao listar materiais: {str(e)}"}), 500


@app.route('/materiais/<int:id>', methods=['GET'])
@token_obrigatorio
def buscar_material(id):
    """Busca um material específico pelo ID"""
    try:
        docs = db.collection('materiais').where('id', '==', id).limit(1).get()
        
        for doc in docs:
            return jsonify(doc.to_dict()), 200
        
        return jsonify({"error": "Material não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/materiais/<int:id>', methods=['PUT'])
@token_obrigatorio
def atualizar_material_total(id):
    """Atualiza TODOS os campos de um material"""
    dados = request.get_json()
    
    if not dados or "nome" not in dados or "quantidade" not in dados:
        return jsonify({"error": "Campos 'nome' e 'quantidade' são obrigatórios!"}), 400
    
    try:
        docs = db.collection('materiais').where('id', '==', id).limit(1).get()
        
        doc_id = None
        for doc in docs:
            doc_id = doc.id
            break
        
        if not doc_id:
            return jsonify({"error": "Material não encontrado"}), 404
        
        doc_ref = db.collection('materiais').document(doc_id)
        doc_ref.update({
            "nome": dados["nome"],
            "quantidade": dados["quantidade"],
            "quantidade_minima_alerta": dados.get("quantidade_minima_alerta", 10),
            "unidade": dados.get("unidade", "unidades")
        })
        
        return jsonify({"message": "Material atualizado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/materiais/<int:id>', methods=['PATCH'])
@token_obrigatorio
def atualizar_material(id):
    """Atualiza UM OU MAIS campos de um material (ex: só a quantidade)"""
    try:
        dados = request.get_json()
        
        docs = db.collection('materiais').where('id', '==', id).limit(1).get()
        
        doc_id = None
        for doc in docs:
            doc_id = doc.id
            break
        
        if not doc_id:
            return jsonify({"error": "Material não encontrado"}), 404
        
        doc_ref = db.collection('materiais').document(doc_id)
        doc_ref.update(dados)
        
        return jsonify({"message": "Material atualizado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao atualizar material: {str(e)}"}), 500


@app.route('/materiais/<int:id>', methods=['DELETE'])
@token_obrigatorio
def excluir_material(id):
    """Exclui um material do estoque"""
    try:
        docs = db.collection('materiais').where('id', '==', id).limit(1).get()
        
        doc_id = None
        for doc in docs:
            doc_id = doc.id
            break
        
        if not doc_id:
            return jsonify({"error": "Material não encontrado"}), 404
        
        db.collection('materiais').document(doc_id).delete()
        
        return jsonify({"message": "Material excluído com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# TRATAMENTO DE ERROS GLOBAIS
# ============================================================
@app.errorhandler(404)
def erro404(error):
    """Rota não encontrada"""
    return jsonify({"error": "Rota não encontrada!"}), 404

@app.errorhandler(500)
def erro500(error):
    """Erro interno do servidor"""
    return jsonify({"error": "Erro interno no servidor!"}), 500

# ============================================================
# INICIALIZAÇÃO DO SERVIDOR
# ============================================================
if __name__ == '__main__':
    app.run(debug=True)