from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
markers = []

@app.route('/api/markers', methods=['POST'])
def add_marker():
    data = request.get_json()
    x = data.get('x')
    y = data.get('y')
    type_ = data.get('type')
    if x is not None and y is not None and type_:
        markers.append({'x': x, 'y': y, 'type': type_})
        return jsonify({'message': 'Marker saved', 'id': len(markers) - 1}), 201
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/api/markers', methods=['GET'])
def get_markers():
    return jsonify(markers)

@app.route('/api/markers/<int:index>', methods=['DELETE'])
def delete_marker(index):
    if 0 <= index < len(markers):
        markers.pop(index)
        return jsonify({'message': 'Marker deleted'}), 200
    return jsonify({'error': 'Marker not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')  # Bind to 0.0.0.0 to allow external connections