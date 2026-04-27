from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, firestore
from auth import token_obrigatorio, gerar_token
from flask_cors import CORS
import os
from dotenv import load_dotenv
import json
from flasgger import Swagger

load_dotenv() # Carrega as variáveis de ambiente do arquivo .env

app = Flask(__name__)

# versão do apen api
app.config['SWAGGER'] = {
    'openapi': '3.0.2'
    }
# chamando o open api para o codigo
swagger = Swagger(app, template_file='openapi.yaml')
# ---------------------------------------------

# configurando a SECRET_KEY da aplicação a partir da variável de ambiente
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
CORS(app, origins="*")
ADM_USUARIO = os.getenv("ADM_USUARIO")
ADM_SENHA = os.getenv("ADM_SENHA")

if os.getenv("VERCEL"):
    # online na vercel
    cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_CREDENTIALS")))
else:
    # localmente
    cred = credentials.Certificate("firebase.json") # carrega as credenciais do firebase a partir do arquivo local

firebase_admin.initialize_app(cred) # inicializa o app do firebase com as credenciais

# conectar ao firestore
db = firestore.client()
# ---------------------------------------------

# rota principal - boas vindas da api
@app.route('/',methods=['GET'])
def home():
    return jsonify({
        "api": "API do sistema de artesanato (Treino)",
        "version": "1.0",
        "author": "Maya"
            }), 200

# rota de login
# ROTA LOGIN
@app.route("/login", methods = ["POST"])
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
        return jsonify({"message": "Login realizado com sucesso!", "token":token}),200
    
    return jsonify({"Error": "Usuário ou senha inválidos"}),401
#--------------------------------------------

# ROTAS PUBLICAS (sem autenticação)
# rota para listar os produtos 
@app.route('/produtos', methods=['GET'])
def listar_produtos():
    produtos = []
    lista = db.collection('produtos').stream()

    for item in lista:
        produtos.append(item.to_dict())

    return jsonify(produtos), 200
# --------------------------------------------

# rota para buscar produto por id
@app.route('/produtos/<int:id>', methods=['GET'])
def buscar_produto_by_id(id):
    lista = db.collection('produtos').where('id', '==', id).stream()

    for item in lista:
        return jsonify(item.to_dict()), 200
    
    return jsonify({"error": "Produto não encontrado"}), 404
# --------------------------------------------


# ROTAS PRIVADAS (com autenticação)
@app.route('/criarprodutos', methods=['POST'])
@token_obrigatorio
def criar_produto():
    
    dados = request.get_json()

    if not dados or "nome" not in dados or "preco" not in dados or "descricao" not in dados or "categoria" not in dados or "link_img" not in dados:
        return jsonify({"error": "Dados inválidos!"}), 400

    try:
        contador_ref = db.collection("contador").document("controle_id")
        contador_doc = contador_ref.get()
        ultimo_id = contador_doc.to_dict().get("ultimo_id")
        novo_id = ultimo_id + 1
        contador_ref.update({"ultimo_id": novo_id})

        db.collection("produtos").add({
            "id": novo_id,
            "nome": dados["nome"],
            "preco": dados["preco"],
            "descricao": dados["descricao"],
            "categoria": dados["categoria"],
            "link_img": dados["link_img"]
            })
        
        return jsonify({"message": "Produto criado com sucesso!"}), 201
    except:
        return jsonify({"error": "Erro ao criar produto!"}), 500
# --------------------------------------------

# rota para add materiais ao produto
@app.route('/materiais', methods=['POST'])
@token_obrigatorio
def criar_material():
    """
    Cria um novo material no estoque
    ---
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              nome: {type: string, example: "Limpa cachimbos azul"}
              quantidade: {type: number, example: 100}
              quantidade_minima_alerta: {type: number, example: 10}
              unidade: {type: string, example: "unidades"}
    responses:
      201:
        description: Material criado com sucesso
      400:
        description: Dados inválidos
      401:
        description: Token obrigatório
    """
    dados = request.get_json()
    
    # Validação: campos obrigatórios
    if not dados or "nome" not in dados or "quantidade" not in dados:
        return jsonify({"error": "Os campos 'nome' e 'quantidade' são obrigatórios!"}), 400
    
    try:
        # 1. Buscar o último ID usado
        contador_ref = db.collection("contador_materiais").document("controle_id")
        contador_doc = contador_ref.get()
        
        if contador_doc.exists:
            ultimo_id = contador_doc.to_dict().get("ultimo_id", 1)
            novo_id = ultimo_id + 1
            contador_ref.update({"ultimo_id": novo_id})
        else:
            # Se o documento não existe, cria com ID 1
            novo_id = 1
            contador_ref.set({"ultimo_id": 1})
        
        # 2. Criar o documento do material
        db.collection("materiais").add({
            "id": novo_id,
            "nome": dados["nome"],
            "quantidade": dados["quantidade"],
            "quantidade_minima_alerta": dados.get("quantidade_minima_alerta", 10),
            "unidade": dados.get("unidade", "unidades")
        })
        
        return jsonify({
            "message": "Material criado com sucesso!",
            "id": novo_id
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Erro ao criar material: {str(e)}"}), 500

# rota para atualizar produto totalmente (put)
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
            "link_img": dados["link_img"]
        })

    return jsonify({"message": "Produto atualizado com sucesso!"}), 200 
# --------------------------------------------------------

# rota para atualizar produto parcialmente (patch)
@app.route('/produtos/<int:id>', methods=['PATCH'])
@token_obrigatorio
def patch_produtos(id):
    dados = request.get_json()
    
    docs = db.collection("produtos").where("id", "==", id).limit(1).get()

    for doc in docs:
        doc_ref = db.collection("produtos").document(doc.id)
        doc_ref.update(dados)

    return jsonify({"message": "Produto atualizado com sucesso!"}), 200
# --------------------------------------------------------

# rota para deletar produto
@app.route('/produtos/<int:id>', methods=['DELETE'])
@token_obrigatorio
def excluir_produto(id):  
    docs = db.collection("produtos").where("id", "==", id).limit(1).get()

    for doc in docs:
        doc_ref = db.collection("produtos").document(doc.id)
        doc_ref.delete()

    return jsonify({"message": "Produto excluído com sucesso!"}), 200
# --------------------------------------------------------

# TRATAMENTO DE ERROS
@app.errorhandler(404)
def erro404(error):
    return jsonify({"error": "Rota não encontrada!"}), 404

@app.errorhandler(500)
def erro500(error):
    return jsonify({"error": "Erro interno no servidor!"}), 500
# --------------------------------------------------------

if __name__ == '__main__' :
    app.run(debug=True)