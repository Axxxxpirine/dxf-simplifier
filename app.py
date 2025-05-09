from flask import Flask, request, jsonify, send_file
import os
import ezdxf
import numpy as np
from werkzeug.utils import secure_filename
from shapely.geometry import LineString

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
DOWNLOAD_FOLDER = 'downloads'
ALLOWED_EXTENSIONS = {'dxf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_all_polylines(doc):
    msp = doc.modelspace()
    polylines = []
    for e in msp:
        if e.dxftype() == 'LWPOLYLINE':
            points = [(pt[0], pt[1]) for pt in e.get_points()]
            polylines.append(points)
        elif e.dxftype() == 'POLYLINE':
            points = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices()]
            polylines.append(points)
    return polylines

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier reçu'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'message': 'Fichier reçu', 'filename': filename}), 200
    else:
        return jsonify({'error': 'Fichier non autorisé'}), 400

@app.route('/simplify', methods=['GET'])
def simplify():
    filename = request.args.get('filename')
    percent = float(request.args.get('percent', 0))

    if not filename:
        return jsonify({'error': 'Nom de fichier requis'}), 400

    input_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(input_path):
        return jsonify({'error': 'Fichier non trouvé'}), 404

    try:
        doc = ezdxf.readfile(input_path)
        polylines = get_all_polylines(doc)
        simplified_polylines = []

        for poly in polylines:
            if len(poly) < 3:
                simplified_polylines.append(poly)
                continue
            num_points = len(poly)
            target_count = max(2, int(num_points * (1 - percent / 100)))
            if target_count >= num_points:
                simplified = poly
            else:
                indices = np.linspace(0, num_points - 1, target_count, dtype=int)
                simplified = [poly[i] for i in indices]
            simplified_polylines.append(simplified)

        new_doc = ezdxf.new()
        msp = new_doc.modelspace()
        for poly in simplified_polylines:
            if len(poly) >= 2:
                msp.add_lwpolyline(poly)

        output_path = os.path.join(DOWNLOAD_FOLDER, f"simplified_{filename}")
        new_doc.saveas(output_path)

        return jsonify({'message': 'Fichier simplifié généré', 'download_url': f'/download_file?filename=simplified_{filename}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_file')
def download_file():
    filename = request.args.get('filename')
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({'error': 'Fichier non trouvé'}), 404

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)