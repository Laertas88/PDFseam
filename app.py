import os
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from flask import Flask, request, render_template, send_file, jsonify
import paypalrestsdk

# Initialiser Flask
app = Flask(__name__)

# Définir les dossiers pour les fichiers téléversés et générés
UPLOAD_FOLDER = './uploads'
OUTPUT_FOLDER = './output'
TEMP_FOLDER = './temp'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Configuration PayPal
paypalrestsdk.configure({
    "mode": "sandbox",  # Changez en "live" pour production
    "client_id": "AQTr-ljXZoZsIgaVyaUrPv6DJRBp3W6qngUNky4DWVAmuOzAiRDIqenF1ysSJQjnYdsk5olsJ9z1Tc78",
    "client_secret": "EI9eYA89-xLA_FefqYt2-UTu5Mxv1GqKqf2f9DB7PBHtfSoxq8RzQf-vMnLp-anMgZckP9KQq4AVHyCo"
})
# Liste blanche d'emails
WHITELISTED_EMAILS = ["remimarin83@gmail.com", "haeussermarine@gmail.com"]

@app.route('/validate-email', methods=['GET'])
def validate_email():
    email = request.args.get('email')
    if email in WHITELISTED_EMAILS:
        return jsonify({"is_whitelisted": True})
    return jsonify({"is_whitelisted": False})
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Aucun fichier fourni"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Fichier vide"}), 400

        try:
            left_margin = float(request.form.get('left_margin', '0').replace(',', '.'))
            right_margin = float(request.form.get('right_margin', '0').replace(',', '.'))
            top_margin = float(request.form.get('top_margin', '0').replace(',', '.'))
            bottom_margin = float(request.form.get('bottom_margin', '0').replace(',', '.'))
            rows = int(request.form.get('rows', '1'))
            cols = int(request.form.get('cols', '1'))
        except ValueError:
            return jsonify({"error": "Les marges et dimensions doivent être des nombres valides."}), 400

        mm_to_points = 72 / 25.4
        left_margin *= mm_to_points
        right_margin *= mm_to_points
        top_margin *= mm_to_points
        bottom_margin *= mm_to_points

        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)

        original_name, extension = os.path.splitext(file.filename)
        output_filename = f"{original_name}_converted{extension}"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        cropped_pages = crop_pdf_pages(input_path, left_margin, right_margin, top_margin, bottom_margin)
        assemble_cropped_pages(cropped_pages, output_path, rows, cols)

        for page in cropped_pages:
            os.remove(page)

        return send_file(output_path, as_attachment=True, mimetype='application/pdf', download_name=output_filename)

    except Exception as e:
        print(f"Erreur : {e}")
        return jsonify({"error": f"Erreur lors du traitement : {str(e)}"}), 500


@app.route('/preview', methods=['POST'])
def preview_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Aucun fichier fourni"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Fichier vide"}), 400

        left_margin = float(request.form.get('left_margin', '0').replace(',', '.'))
        right_margin = float(request.form.get('right_margin', '0').replace(',', '.'))
        top_margin = float(request.form.get('top_margin', '0').replace(',', '.'))
        bottom_margin = float(request.form.get('bottom_margin', '0').replace(',', '.'))

        mm_to_points = 72 / 25.4
        left_margin *= mm_to_points
        right_margin *= mm_to_points
        top_margin *= mm_to_points
        bottom_margin *= mm_to_points

        input_path = os.path.join(TEMP_FOLDER, file.filename)
        file.save(input_path)

        doc = fitz.open(input_path)
        preview_images = []

        for i, page in enumerate(doc):
            crop_rect = fitz.Rect(
                left_margin,
                top_margin,
                page.rect.width - right_margin,
                page.rect.height - bottom_margin,
            )
            pix = page.get_pixmap(dpi=72, clip=crop_rect)
            temp_path = os.path.join(TEMP_FOLDER, f"preview_page_{i}.png")
            pix.save(temp_path)
            preview_images.append(f"/temp/preview_page_{i}.png")

        return jsonify(preview_images)

    except Exception as e:
        print(f"Erreur : {e}")
        return jsonify({"error": f"Erreur lors de la prévisualisation : {str(e)}"}), 500


def crop_pdf_pages(pdf_path, left_margin, right_margin, top_margin, bottom_margin):
    doc = fitz.open(pdf_path)
    cropped_pages = []
    a4_width, a4_height = 595.28, 841.89

    for i, page in enumerate(doc):
        crop_rect = fitz.Rect(
            left_margin,
            top_margin,
            a4_width - right_margin,
            a4_height - bottom_margin
        )
        pix = page.get_pixmap(dpi=150, clip=crop_rect)
        temp_path = os.path.join(TEMP_FOLDER, f"cropped_page_{i + 1}.png")
        pix.save(temp_path)
        cropped_pages.append(temp_path)

    return cropped_pages


def assemble_cropped_pages(cropped_pages, output_path, rows, cols):
    if rows * cols < len(cropped_pages):
        raise ValueError("La grille spécifiée (lignes x colonnes) est insuffisante pour contenir toutes les pages.")

    sample_pix = fitz.open(cropped_pages[0]).load_page(0).get_pixmap(dpi=150)
    cropped_width = sample_pix.width
    cropped_height = sample_pix.height

    total_width = cols * cropped_width
    total_height = rows * cropped_height

    c = canvas.Canvas(output_path, pagesize=(total_width, total_height))

    for i, cropped_page in enumerate(cropped_pages):
        col = i % cols
        row = i // cols
        x_offset = col * cropped_width
        y_offset = total_height - (row + 1) * cropped_height

        c.drawImage(cropped_page, x_offset, y_offset, width=cropped_width, height=cropped_height)

    c.save()


@app.route('/create-payment', methods=['POST'])
def create_payment():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": "http://127.0.0.1:8080/execute-payment",
            "cancel_url": "http://127.0.0.1:8080/cancel",
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": "Génération de PDF",
                    "sku": "001",
                    "price": "0.20",
                    "currency": "EUR",
                    "quantity": 1
                }]
            },
            "amount": {"total": "1.00", "currency": "EUR"},
            "description": "Paiement pour la génération de PDF."
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return jsonify({"approval_url": link.href})
    else:
        return jsonify({"error": payment.error}), 500


@app.route('/execute-payment', methods=['GET'])
def execute_payment():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')

    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        return "Paiement réussi ! Vous pouvez maintenant générer votre PDF."
    else:
        return jsonify({"error": "Erreur lors de l'exécution du paiement."}), 500


@app.route('/generate-free', methods=['POST'])
def generate_free_pdf():
    user_email = request.form.get('email')
    if user_email in ["user@example.com", "vip@example.com"]:
        return "Génération gratuite autorisée."
    else:
        return jsonify({"error": "Vous n'êtes pas autorisé à générer gratuitement."}), 403


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
