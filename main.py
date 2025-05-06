from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os

app = Flask(__name__)
CORS(app)

# Simulação de armazenamento em memória
floor_plans = {}
markers = []

@app.route('/api/markers', methods=['GET', 'POST'])
def handle_markers():
    if request.method == 'GET':
        return jsonify(markers)
    elif request.method == 'POST':
        data = request.get_json()
        if not data or 'x' not in data or 'y' not in data or 'type' not in data or 'name' not in data or 'ip' not in data:
            return jsonify({'error': 'Dados de marcador inválidos'}), 400
        marker = {
            'x': data['x'],
            'y': data['y'],
            'type': data['type'],
            'name': data['name'],
            'ip': data['ip']
        }
        markers.append(marker)
        return jsonify({'message': 'Marcador salvo com sucesso'}), 201

@app.route('/api/markers/<int:index>', methods=['DELETE'])
def delete_marker(index):
    if 0 <= index < len(markers):
        markers.pop(index)
        return jsonify({'message': 'Marcador excluído com sucesso'})
    return jsonify({'error': 'Índice de marcador inválido'}), 404

@app.route('/api/floorplan', methods=['POST'])
def save_floor_plan():
    data = request.get_json()
    if not data or 'dxfContent' not in data or 'markers' not in data:
        return jsonify({'error': 'Dados da planta baixa inválidos'}), 400
    floor_plan_id = str(uuid.uuid4())
    floor_plans[floor_plan_id] = {
        'dxfContent': data['dxfContent'],
        'markers': data['markers']
    }
    return jsonify({'message': 'Planta baixa salva com sucesso', 'id': floor_plan_id}), 201

@app.route('/api/floorplan/<floor_plan_id>', methods=['GET', 'PUT'])
def handle_floor_plan(floor_plan_id):
    if floor_plan_id not in floor_plans:
        return jsonify({'error': 'Planta baixa não encontrada'}), 404
    if request.method == 'GET':
        return jsonify(floor_plans[floor_plan_id])
    elif request.method == 'PUT':
        data = request.get_json()
        if not data or 'dxfContent' not in data or 'markers' not in data:
            return jsonify({'error': 'Dados da planta baixa inválidos'}), 400
        floor_plans[floor_plan_id] = {
            'dxfContent': data['dxfContent'],
            'markers': data['markers']
        }
        return jsonify({'message': 'Planta baixa atualizada com sucesso', 'id': floor_plan_id})

@app.route('/api/floorplans', methods=['GET'])
def list_floor_plans():
    return jsonify({'floorPlans': list(floor_plans.keys())})

if __name__ == '__main__':
    app.run(debug=True, port=5000)