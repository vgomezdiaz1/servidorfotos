from flask import Flask, request, redirect, url_for, render_template, send_from_directory,send_file
from PIL import Image, ExifTags
import os
import json
from datetime import datetime
import sqlite3
import zipfile
from io import BytesIO

app = Flask(__name__)

UPLOAD_FOLDER = 'C:\\Users\\Victo\\Pictures\\prueba'  # Ruta donde se guardarán las fotos
THUMBNAIL_FOLDER = 'C:\\Users\\Victo\\Pictures\\prueba\\miniaturas'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER

# Asegúrate de que los directorios de subida y miniaturas existan
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect('photos.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            date_taken TEXT NOT NULL,
            metadata TEXT,
            storage_location TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def extract_date_taken(image_path):
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()

        if exif_data:
            # Buscar la etiqueta de fecha en los metadatos EXIF
            for tag, value in ExifTags.TAGS.items():
                if value == 'DateTimeOriginal':
                    date_taken = exif_data.get(tag)
                    if date_taken:
                        # Formatear la fecha de 'YYYY:MM:DD HH:MM:SS' a 'YYYYMMDD_HHMMSS'
                        return datetime.strptime(date_taken, '%Y:%m:%d %H:%M:%S').strftime('%Y%m%d_%H%M%S')
    except Exception as e:
        print(f"Error extrayendo metadatos EXIF: {e}")
    
    # Si no se puede extraer la fecha, devolver la fecha actual
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def extract_metadata(image_path):
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if exif_data:
            # Convertir los metadatos EXIF a un formato JSON
            return json.dumps(exif_data)
    except Exception as e:
        print(f"Error extrayendo metadatos: {e}")
    return None

def store_photo_info(filename, date_taken, metadata, storage_location):
    conn = sqlite3.connect('photos.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO photos (filename, date_taken, metadata, storage_location)
        VALUES (?, ?, ?, ?)
    ''', (filename, date_taken, metadata, storage_location))
    conn.commit()
    conn.close()

def create_thumbnail(image_path, filename):
    thumbnail_size = (200, 200)
    img = Image.open(image_path)
    img.thumbnail(thumbnail_size)
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], filename)
    img.save(thumbnail_path)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No se ha enviado ningún archivo", 400

    file = request.files['file']
    if file.filename == '':
        return "No se ha seleccionado ningún archivo", 400

    # Guardar temporalmente la imagen para leer los metadatos EXIF
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(temp_path)

    # Extraer la fecha de la imagen
    date_taken = extract_date_taken(temp_path)

    # Renombrar la imagen con la fecha tomada
    file_ext = os.path.splitext(file.filename)[1]  # Obtener la extensión del archivo
    new_filename = f"{date_taken}{file_ext}"

    # Definir la ruta final de la imagen renombrada
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
    os.rename(temp_path, file_path)

    # Crear una miniatura de la imagen
    create_thumbnail(file_path, new_filename)

    # Extraer metadatos y almacenarlos
    metadata = extract_metadata(temp_path)

    # Almacenar la información en SQLite
    store_photo_info(new_filename, date_taken, metadata, file_path)

    return f"Archivo {new_filename} subido con éxito", 200

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'photo' not in request.files:
        return "No se seleccionó ningún archivo"
    file = request.files['photo']
    
    if file.filename == '':
        return "No se seleccionó ningún archivo"
    
    # Guardar el archivo en la carpeta de uploads
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    
    return redirect(url_for('index'))

@app.route('/')
def index():
    conn = sqlite3.connect('photos.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM photos ORDER BY date_taken DESC')
    photos = cursor.fetchall()
    conn.close()

    grouped_photos = {}
    for photo in photos:
        date_time = photo[2] 
        date = date_time.split('_')[0] 
        
        if date not in grouped_photos:
            grouped_photos[date] = []
        grouped_photos[date].append(photo)

    return render_template('index.html', grouped_photos=grouped_photos)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/thumbnails/<filename>')
def uploaded_thumbnail(filename):
    return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename)

@app.route('/download_photos', methods=['POST'])
def download_photos():
    selected_photos = request.form.getlist('selected_photos')
    print("Fotos seleccionadas:", selected_photos)  # Depuración

    if not selected_photos:
        return "No seleccionaste ninguna foto."

    # Crear archivo zip en memoria
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for photo_name in selected_photos:
            file_path = os.path.join(UPLOAD_FOLDER, photo_name)
            if os.path.exists(file_path):
                zf.write(file_path, arcname=photo_name)
            else:
                print(f"Archivo no encontrado: {file_path}")  # Depuración de archivos inexistentes

    memory_file.seek(0)

    # Devolver el archivo zip para descarga
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='fotos_seleccionadas.zip'
    )


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
