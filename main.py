from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

floor_plans = {}  # Store floor plans with ID as key
floor_plan_id_counter = 0
markers = []

@app.route('/api/markers', methods=['POST'])
def add_marker():
    data = request.get_json()
    x = data.get('x')
    y = data.get('y')
    type_ = data.get('type')
    name = data.get('name')
    ip = data.get('ip')
    if all([x is not None, y is not None, type_, name, ip]):
        marker = {'x': x, 'y': y, 'type': type_, 'name': name, 'ip': ip}
        markers.append(marker)
        return jsonify({'message': 'Marker saved', 'id': len(markers) - 1}), 201
    return jsonify({'error': 'Invalid data: x, y, type, name, and ip are required'}), 400

@app.route('/api/markers', methods=['GET'])
def get_markers():
    return jsonify(markers)

@app.route('/api/markers/<int:index>', methods=['DELETE'])
def delete_marker(index):
    if 0 <= index < len(markers):
        markers.pop(index)
        return jsonify({'message': 'Marker deleted'}), 200
    return jsonify({'error': 'Marker not found'}), 404

@app.route('/api/floorplan', methods=['POST'])
def save_floor_plan():
    global floor_plan_id_counter
    data = request.get_json()
    dxf_content = data.get('dxfContent')
    markers = data.get('markers')
    if dxf_content and markers is not None:
        floor_plans[floor_plan_id_counter] = {
            'dxfContent': dxf_content,
            'markers': markers
        }
        response = {'message': 'Floor plan saved', 'id': floor_plan_id_counter}
        floor_plan_id_counter += 1
        return jsonify(response), 201
    return jsonify({'error': 'Invalid data: dxfContent and markers are required'}), 400

@app.route('/api/floorplan/<int:id>', methods=['GET'])
def get_floor_plan(id):
    if id in floor_plans:
        return jsonify(floor_plans[id]), 200
    return jsonify({'error': 'Floor plan not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')