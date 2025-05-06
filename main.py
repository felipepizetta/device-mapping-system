import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from uuid import uuid4

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

# Arquivo para armazenamento persistente
DATA_FILE = "floor_plans.json"

# Inicializar arquivo JSON se não existir
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({"floor_plans": []}, f)

# Carregar planos do arquivo
def load_floor_plans():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)["floor_plans"]

# Salvar planos no arquivo
def save_floor_plans(floor_plans):
    with open(DATA_FILE, 'w') as f:
        json.dump({"floor_plans": floor_plans}, f)

@app.route('/api/floorplan', methods=['POST', 'OPTIONS'])
def create_floor_plan():
    if request.method == 'OPTIONS':
        print("Recebida requisição OPTIONS para /api/floorplan")
        return jsonify({}), 200

    data = request.get_json()
    if not data or not all(key in data for key in ['name', 'dxfContent', 'markers']):
        return jsonify({"error": "name, dxfContent e markers são obrigatórios"}), 400
    
    floor_plans = load_floor_plans()
    id = str(uuid4())
    floor_plan = {
        "id": id,
        "name": data["name"],
        "dxfContent": data["dxfContent"],
        "markers": data["markers"]
    }
    floor_plans.append(floor_plan)
    save_floor_plans(floor_plans)
    
    print(f"Planta salva: ID={id}, Nome={data['name']}")
    return jsonify({"id": id}), 200

@app.route('/api/floorplan/<id>', methods=['PUT', 'OPTIONS'])
def update_floor_plan(id):
    if request.method == 'OPTIONS':
        print(f"Recebida requisição OPTIONS para /api/floorplan/{id}")
        return jsonify({}), 200

    data = request.get_json()
    if not data or not all(key in data for key in ['name', 'dxfContent', 'markers']):
        return jsonify({"error": "name, dxfContent e markers são obrigatórios"}), 400
    
    floor_plans = load_floor_plans()
    for i, plan in enumerate(floor_plans):
        if plan["id"] == id:
            floor_plans[i] = {
                "id": id,
                "name": data["name"],
                "dxfContent": data["dxfContent"],
                "markers": data["markers"]
            }
            save_floor_plans(floor_plans)
            print(f"Planta atualizada: ID={id}, Nome={data['name']}")
            return jsonify({"id": id}), 200
    
    return jsonify({"error": "Planta não encontrada"}), 404

@app.route('/api/floorplan/<id>', methods=['GET'])
def get_floor_plan(id):
    floor_plans = load_floor_plans()
    for plan in floor_plans:
        if plan["id"] == id:
            print(f"Planta recuperada: ID={id}, Nome={plan['name']}")
            return jsonify(plan), 200
    
    return jsonify({"error": "Planta não encontrada"}), 404

@app.route('/api/floorplans', methods=['GET'])
def list_floor_plans():
    floor_plans = load_floor_plans()
    print("Listando plantas baixas:", [{"id": plan["id"], "name": plan["name"]} for plan in floor_plans])
    return jsonify({"floorPlans": [{"id": plan["id"], "name": plan["name"]} for plan in floor_plans]}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)