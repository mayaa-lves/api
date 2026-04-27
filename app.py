from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, firestore
from auth import token_obrigatorio, gerar_token
from flask_cors import CORS
import os
from dotenv import load_dotenv
import json
from flasgger import Swagger
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Configuração do Swagger
app.config['SWAGGER'] = {
    'openapi': '3.0.2'
}
swagger = Swagger(app, template_file='openapi.yaml')

# Configurações gerais
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
CORS(app, origins="*")
ADM_USUARIO = os.getenv("ADM_USUARIO")
ADM_SENHA = os.getenv("ADM_SENHA")

# Conexão com Firebase
if os.getenv("VERCEL"):
    cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_CREDENTIALS")))
else:
    cred = credentials.Certificate("firebase.json")

firebase_admin.initialize_app(cred)
db = firestore.client()

# ============================================================
# ROTA PRINCIPAL
# ============================================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "api": "API do sistema de artesanato (Treino)",
        "version": "2.0",
        "author": "Maya"
    }), 200

# ============================================================
# ROTA DE LOGIN
# ============================================================
@app.route("/login", methods=["POST"])
def login():
    dados = request.get_json()

    if not dados:
        return jsonify({"Error": "Envie os dados para login"}), 400
    
    usuario = dados.get('usuario')
    senha = dados.get('senha')

    if not usuario or not senha:
        return jsonify({"Error": "Usuário e senha são obrigatórios!"}), 400
    
    if usuario == ADM_USUARIO and senha == ADM_SENHA:
        token = gerar_token(usuario)
        return jsonify({"message": "Login realizado com sucesso!", "token": token}), 200
    
    return jsonify({"Error": "Usuário ou senha inválidos"}), 401

# ============================================================
# ROTAS PÚBLICAS - PRODUTOS
# ============================================================
@app.route('/produtos', methods=['GET'])
def listar_produtos():
    produtos = []
    lista = db.collection('produtos').stream()

    for item in lista:
        produtos.append(item.to_dict())

    return jsonify(produtos), 200

@app.route('/produtos/<int:id>', methods=['GET'])
def buscar_produto_by_id(id):
    lista = db.collection('produtos').where('id', '==', id).stream()

    for item in lista:
        return jsonify(item.to_dict()), 200
    
    return jsonify({"error": "Produto não encontrado"}), 404

# ============================================================
# ROTAS PRIVADAS - PRODUTOS (ADMIN)
# ============================================================
@app.route('/criarprodutos', methods=['POST'])
@token_obrigatorio
def criar_produto():
    dados = request.get_json()

    if not dados or "nome" not in dados or "preco" not in dados or "descricao" not in dados or "categoria" not in dados or "link_img" not in dados:
        return jsonify({"error": "Dados inválidos!"}), 400

    try:
        contador_ref = db.collection("contador").document("controle_id")
        contador_doc = contador_ref.get()
        ultimo_id = contador_doc.to_dict().get("ultimo_id", 0)
        novo_id = ultimo_id + 1
        contador_ref.update({"ultimo_id": novo_id})

        produto_data = {
            "id": novo_id,
            "nome": dados["nome"],
            "preco": dados["preco"],
            "descricao": dados["descricao"],
            "categoria": dados["categoria"],
            "link_img": dados["link_img"],
            "tempo_producao": dados.get("tempo_producao", "5 dias úteis"),
            "materiais_usados": dados.get("materiais_usados", [])
        }
        
        db.collection("produtos").add(produto_data)
        
        return jsonify({"message": "Produto criado com sucesso!", "id": novo_id}), 201
    except Exception as e:
        return jsonify({"error": f"Erro ao criar produto: {str(e)}"}), 500

@app.route('/produtos/<int:id>', methods=['PUT'])
@token_obrigatorio
def put_produtos(id):
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
    dados = request.get_json()
    
    docs = db.collection("produtos").where("id", "==", id).limit(1).get()

    for doc in docs:
        doc_ref = db.collection("produtos").document(doc.id)
        doc_ref.update(dados)

    return jsonify({"message": "Produto atualizado com sucesso!"}), 200

@app.route('/produtos/<int:id>', methods=['DELETE'])
@token_obrigatorio
def excluir_produto(id):  
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
    dados = request.get_json()
    
    if not dados or "nome" not in dados or "quantidade" not in dados:
        return jsonify({"error": "Os campos 'nome' e 'quantidade' são obrigatórios!"}), 400
    
    try:
        contador_ref = db.collection("contador_materiais").document("controle_id")
        contador_doc = contador_ref.get()
        
        if contador_doc.exists:
            ultimo_id = contador_doc.to_dict().get("ultimo_id", 0)
            novo_id = ultimo_id + 1
            contador_ref.update({"ultimo_id": novo_id})
        else:
            novo_id = 1
            contador_ref.set({"ultimo_id": 1})
        
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
# ROTAS PARA COMENTÁRIOS (PÚBLICAS)
# ============================================================
@app.route('/comentarios/<int:produto_id>', methods=['GET'])
def listar_comentarios(produto_id):
    """Lista todos os comentários de um produto específico"""
    try:
        comentarios = []
        lista = db.collection('comentarios').where('produto_id', '==', produto_id).order_by('data', direction=firestore.Query.DESCENDING).stream()
        
        for doc in lista:
            comentario = doc.to_dict()
            comentario['id'] = doc.id  # ID automático do Firebase
            comentarios.append(comentario)
        
        return jsonify(comentarios), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/comentarios', methods=['POST'])
def criar_comentario():
    """Cria um novo comentário para um produto"""
    dados = request.get_json()
    
    if not dados or "produto_id" not in dados or "nome" not in dados or "estrelas" not in dados or "texto" not in dados:
        return jsonify({"error": "Campos obrigatórios: produto_id, nome, estrelas, texto"}), 400
    
    try:
        novo_comentario = {
            "produto_id": dados["produto_id"],
            "nome": dados["nome"][:50],
            "estrelas": dados["estrelas"],
            "texto": dados["texto"][:500],
            "data": datetime.now().isoformat()
        }
        
        doc_ref = db.collection('comentarios').add(novo_comentario)
        
        return jsonify({"message": "Comentário adicionado com sucesso!", "id": doc_ref[1].id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# ROTAS DE ADMIN PARA COMENTÁRIOS (EXCLUIR)
# ============================================================
@app.route('/admin/comentarios', methods=['GET'])
@token_obrigatorio
def listar_todos_comentarios():
    """Lista TODOS os comentários (apenas admin) - útil para moderação"""
    try:
        comentarios = []
        lista = db.collection('comentarios').order_by('data', direction=firestore.Query.DESCENDING).stream()
        
        for doc in lista:
            comentario = doc.to_dict()
            comentario['id'] = doc.id
            comentarios.append(comentario)
        
        return jsonify(comentarios), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/comentarios/<comentario_id>', methods=['DELETE'])
@token_obrigatorio
def excluir_comentario(comentario_id):
    """Exclui um comentário pelo ID do documento (apenas admin)"""
    try:
        doc_ref = db.collection('comentarios').document(comentario_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({"error": "Comentário não encontrado"}), 404
        
        doc_ref.delete()
        return jsonify({"message": "Comentário excluído com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# TRATAMENTO DE ERROS
# ============================================================
@app.errorhandler(404)
def erro404(error):
    return jsonify({"error": "Rota não encontrada!"}), 404

@app.errorhandler(500)
def erro500(error):
    return jsonify({"error": "Erro interno no servidor!"}), 500

if __name__ == '__main__':
    app.run(debug=True)