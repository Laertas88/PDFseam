import os
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from flask import Flask, request, render_template, send_file, jsonify

# Initialiser Flask
app = Flask(__name__)

# Définir les dossiers pour les fichiers téléversés et générés
UPLOAD_FOLDER = './uploads'
OUTPUT_FOLDER = './output'

# Créer les dossiers s'ils n'existent pas
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Route principale pour afficher la page HTML
@app.route('/')
def index():
    return render_template('index.html')

# Route pour gérer le téléversement et l'assemblage
@app.route('/upload', methods=['POST'])
def upload_pdf():
    # Vérifie si un fichier a été envoyé
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Fichier vide"}), 400

    # Récupérer les paramètres lignes et colonnes depuis le formulaire
    try:
        rows = int(request.form.get('rows', 1))  # Valeur par défaut : 1
        cols = int(request.form.get('cols', 1))  # Valeur par défaut : 1
    except ValueError:
        return jsonify({"error": "Les lignes et colonnes doivent être des nombres entiers"}), 400

    # Enregistrer le fichier téléversé
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)

    # Vérifier si le plan de collage est suffisant
    total_pages = len(fitz.open(input_path))  # Nombre total de pages dans le PDF
    if rows * cols < total_pages:
        return jsonify({
            "error": f"Le plan de collage ({rows}x{cols}) est insuffisant pour {total_pages} pages."
        }), 400

    # Générer le chemin pour le fichier PDF assemblé
    output_path = os.path.join(OUTPUT_FOLDER, f"assembled_{file.filename}")

    # Calculer le plan de collage
    positions = []
    for i in range(total_pages):
        col = i % cols
        row = i // cols
        positions.append((col, row))

    # Assembler le PDF en fonction du plan
    assemble_pdf_with_positions(input_path, output_path, positions, cols=cols)

    # Retourner le fichier assemblé à l'utilisateur
    return send_file(output_path, as_attachment=True)

# Route pour prévisualiser le plan de collage
@app.route('/preview', methods=['POST'])
def preview_pdf():
    # Vérifie si un fichier a été envoyé
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Fichier vide"}), 400

    # Enregistrer le fichier temporairement pour calculer le nombre de pages
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)

    try:
        total_pages = len(fitz.open(input_path))  # Nombre total de pages dans le PDF
        os.remove(input_path)  # Supprimer le fichier temporaire
        return jsonify({"totalPages": total_pages}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors du traitement : {str(e)}"}), 500

# Fonction pour assembler le PDF avec des positions spécifiques
def assemble_pdf_with_positions(pdf_path, output_path, positions, cols=4):
    """
    Assemble le PDF en respectant un plan de collage spécifique.
    :param pdf_path: Chemin du fichier PDF source.
    :param output_path: Chemin du fichier PDF généré.
    :param positions: Liste des positions sous forme de tuples [(col, row), ...].
    :param cols: Nombre de colonnes dans la grille.
    """
    # Charger le PDF d'origine
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # Dimensions d'une page A4
    a4_width, a4_height = A4

    # Calculer la taille de la grande page
    rows = (total_pages + cols - 1) // cols
    large_width = cols * a4_width
    large_height = rows * a4_height

    # Créer un canevas pour le fichier final
    c = canvas.Canvas(output_path, pagesize=(large_width, large_height))

    for i, position in enumerate(positions):
        if i >= total_pages:
            break

        page = doc[i]
        pix = page.get_pixmap(dpi=150)  # Rendre la page en tant qu'image
        img_path = f"temp_page_{i + 1}.png"
        pix.save(img_path)  # Sauvegarder temporairement l'image

        # Récupérer les coordonnées pour cette page
        col, row = position
        x_offset = col * a4_width
        y_offset = large_height - (row + 1) * a4_height

        # Ajouter l'image au canevas
        c.drawImage(img_path, x_offset, y_offset, width=a4_width, height=a4_height)

        # Supprimer l'image temporaire
        os.remove(img_path)

    # Sauvegarder le fichier PDF final
    c.save()
    print(f"PDF assemblé généré : {output_path}")

# Lancer le serveur Flask
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
