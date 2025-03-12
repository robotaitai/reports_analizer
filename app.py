import os
from datetime import datetime
import yaml  # Requires PyYAML (pip install pyyaml)
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from parser import parse_html_transactions

app = Flask(__name__)

# Load configuration from config.yaml
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
# Get the categories list from the config, or fallback to a default list.
categories = config.get("categories", [
    "Uncategorized", "Food", "Clothing", "Travel", "Entertainment",
    "Utilities", "Healthcare", "Education", "Car Expenses", "Other"
])

# Create a database file with today’s date (e.g., expenses_2025-03-13.db)
today_str = datetime.today().strftime('%Y-%m-%d')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///expenses_{today_str}.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the Transaction model
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_date = db.Column(db.Date, nullable=False)
    merchant_name = db.Column(db.String(255), nullable=False)
    transaction_amount = db.Column(db.Float, nullable=False)
    source_file = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_date': self.transaction_date.strftime("%Y-%m-%d"),
            'merchant_name': self.merchant_name,
            'transaction_amount': self.transaction_amount,
            'source_file': self.source_file,
        }

# Define the Business model (aggregated totals with a category)
class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    merchant_name = db.Column(db.String(255), unique=True, nullable=False)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    category = db.Column(db.String(255), default="Uncategorized")

    def to_dict(self):
        return {
            'id': self.id,
            'merchant_name': self.merchant_name,
            'total_amount': self.total_amount,
            'category': self.category,
        }

# Function to update the Business table based on transactions
def update_business_totals():
    from sqlalchemy import func
    results = db.session.query(Transaction.merchant_name, func.sum(Transaction.transaction_amount))\
                        .group_by(Transaction.merchant_name).all()
    for merchant, total in results:
        business = Business.query.filter_by(merchant_name=merchant).first()
        if business:
            business.total_amount = total
        else:
            business = Business(merchant_name=merchant, total_amount=total)
            db.session.add(business)
    db.session.commit()

# Home route: pass transactions, businesses, aggregated categories, and categories list to the template.
@app.route('/')
def index():
    transactions = Transaction.query.order_by(Transaction.transaction_date.desc()).all()
    businesses = Business.query.order_by(Business.merchant_name).all()
    # Aggregate totals per category for the pie chart.
    from collections import defaultdict
    import json
    aggregated_categories = defaultdict(float)
    for b in businesses:
        aggregated_categories[b.category] += b.total_amount
    aggregated_categories_json = json.dumps(dict(aggregated_categories))
    return render_template('index.html', 
                           transactions=transactions, 
                           businesses=businesses,
                           aggregated_categories_json=aggregated_categories_json,
                           categories=categories)

# API endpoint to scan the dedicated folder for HTML files and process them.
@app.route('/api/scan', methods=['POST'])
def scan_folder():
    folder_path = os.path.join(os.getcwd(), 'excel_files')
    if not os.path.exists(folder_path):
        return jsonify({'error': 'Folder not found'}), 404

    files = os.listdir(folder_path)
    processed_files = 0
    total_transactions = 0

    for file_name in files:
        if file_name.lower().endswith('.html'):
            # Skip if this file was already processed (based on source_file field).
            existing_file = Transaction.query.filter_by(source_file=file_name).first()
            if existing_file:
                print(f"Skipping already processed file: {file_name}")
                continue

            file_path = os.path.join(folder_path, file_name)
            transactions_data = parse_html_transactions(file_path)

            for data in transactions_data:
                try:
                    transaction_date = datetime.strptime(data['date'], '%d/%m/%y').date()
                except ValueError:
                    transaction_date = datetime.utcnow().date()

                # Normalize amount string (remove Unicode markers and commas)
                amount_str = data['amount'].replace('\u200e', '').replace(',', '').strip()
                try:
                    transaction_amount = float(amount_str)
                except ValueError:
                    print(f"Skipping transaction with invalid amount: {data['amount']}")
                    continue

                merchant = data['merchant'].strip()

                # Check for duplicate transaction (by date, merchant, and amount)
                existing_tx = Transaction.query.filter_by(
                    transaction_date=transaction_date,
                    merchant_name=merchant,
                    transaction_amount=transaction_amount
                ).first()
                if existing_tx:
                    continue

                transaction = Transaction(
                    transaction_date=transaction_date,
                    merchant_name=merchant,
                    transaction_amount=transaction_amount,
                    source_file=file_name
                )
                db.session.add(transaction)
                total_transactions += 1
            processed_files += 1

    db.session.commit()
    update_business_totals()
    return jsonify({
        'message': f'Processed {processed_files} files with a total of {total_transactions} transactions.'
    })

# API endpoint to upload a new file manually.
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    folder_path = os.path.join(os.getcwd(), 'excel_files')
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, file.filename)
    # Check if file already exists and has been processed.
    if os.path.exists(file_path):
        existing = Transaction.query.filter_by(source_file=file.filename).first()
        if existing:
            return jsonify({'message': 'File already processed'}), 200

    file.save(file_path)
    transactions_data = parse_html_transactions(file_path)
    total_transactions = 0
    for data in transactions_data:
        try:
            transaction_date = datetime.strptime(data['date'], '%d/%m/%y').date()
        except ValueError:
            transaction_date = datetime.utcnow().date()

        amount_str = data['amount'].replace('\u200e', '').replace(',', '').strip()
        try:
            transaction_amount = float(amount_str)
        except ValueError:
            print(f"Skipping transaction with invalid amount: {data['amount']}")
            continue

        merchant = data['merchant'].strip()

        existing_tx = Transaction.query.filter_by(
            transaction_date=transaction_date,
            merchant_name=merchant,
            transaction_amount=transaction_amount
        ).first()
        if existing_tx:
            continue

        transaction = Transaction(
            transaction_date=transaction_date,
            merchant_name=merchant,
            transaction_amount=transaction_amount,
            source_file=file.filename
        )
        db.session.add(transaction)
        total_transactions += 1
    db.session.commit()
    update_business_totals()
    return jsonify({'message': f'Uploaded and processed {total_transactions} transactions from file.'})

# API endpoint to retrieve all transactions as JSON.
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    transactions = Transaction.query.all()
    transactions_list = [t.to_dict() for t in transactions]
    return jsonify(transactions_list)

# API endpoint to retrieve aggregated businesses data.
@app.route('/api/businesses', methods=['GET'])
def get_businesses():
    businesses = Business.query.all()
    businesses_list = [b.to_dict() for b in businesses]
    return jsonify(businesses_list)

# API endpoint to update the category for a business.
@app.route('/api/businesses/<int:business_id>', methods=['POST'])
def update_business(business_id):
    business = Business.query.get(business_id)
    if not business:
        return jsonify({'error': 'Business not found'}), 404
    data = request.get_json()
    if 'category' not in data:
        return jsonify({'error': 'No category provided'}), 400
    business.category = data['category']
    db.session.commit()
    return jsonify({'message': 'Category updated', 'business': business.to_dict()})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)