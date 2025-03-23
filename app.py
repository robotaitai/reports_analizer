import os
from datetime import datetime
import yaml
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from parser import parse_html_transactions
from collections import defaultdict
import json

app = Flask(__name__)

# Load configurations
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)
categories = config.get("categories", ["Uncategorized", "Food", "Clothing", "Travel", "Entertainment",
                                       "Utilities", "Healthcare", "Education", "Car Expenses", "Other", "fines"])

with open("default_categories.yaml", encoding="utf-8") as f:
    default_category_mapping = yaml.safe_load(f)["default_categories"]

today_str = datetime.today().strftime('%Y-%m-%d')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///expenses_{today_str}.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_date = db.Column(db.Date, nullable=False)
    merchant_name = db.Column(db.String(255), nullable=False)
    transaction_amount = db.Column(db.Float, nullable=False)
    source_file = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    merchant_name = db.Column(db.String(255), unique=True, nullable=False)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    category = db.Column(db.String(255), default="Uncategorized")

def update_business_totals():
    from sqlalchemy import func
    results = db.session.query(Transaction.merchant_name, func.sum(Transaction.transaction_amount))\
                        .group_by(Transaction.merchant_name).all()

    for merchant, total in results:
        category = default_category_mapping.get(merchant, "Uncategorized")
        business = Business.query.filter_by(merchant_name=merchant).first()
        if business:
            business.total_amount = total
            # FORCE UPDATE CATEGORY FROM YAML
            business.category = category
        else:
            business = Business(merchant_name=merchant, total_amount=total, category=category)
            db.session.add(business)

    db.session.commit()

@app.route('/')
def index():
    transactions = Transaction.query.order_by(Transaction.transaction_date.desc()).all()
    businesses = Business.query.order_by(Business.merchant_name).all()
    aggregated_categories = defaultdict(float)
    for b in businesses:
        aggregated_categories[b.category] += b.total_amount
    aggregated_categories_json = json.dumps(dict(aggregated_categories))
    return render_template('index.html', 
                           transactions=transactions, 
                           businesses=businesses,
                           aggregated_categories_json=aggregated_categories_json,
                           categories=categories)

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
            existing_file = Transaction.query.filter_by(source_file=file_name).first()
            if existing_file:
                continue

            file_path = os.path.join(folder_path, file_name)
            transactions_data = parse_html_transactions(file_path)

            for data in transactions_data:
                try:
                    transaction_date = datetime.strptime(data['date'], '%d/%m/%y').date()
                    amount_str = data['amount'].replace('\u200e', '').replace(',', '').strip()
                    transaction_amount = float(amount_str)
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
                        source_file=file_name
                    )
                    db.session.add(transaction)
                    total_transactions += 1
                except ValueError:
                    continue
            processed_files += 1

    db.session.commit()
    update_business_totals()
    return jsonify({
        'message': f'Processed {processed_files} files, added {total_transactions} transactions.'
    })

@app.route('/api/pie_data')
def pie_data():
    businesses = Business.query.all()
    aggregated_categories = defaultdict(float)
    for b in businesses:
        aggregated_categories[b.category] += b.total_amount
    return jsonify(aggregated_categories)

@app.route('/api/businesses/<int:business_id>', methods=['POST'])
def update_business(business_id):
    business = Business.query.get(business_id)
    if not business:
        return jsonify({'error': 'Business not found'}), 404
    data = request.get_json()
    business.category = data['category']
    db.session.commit()
    return jsonify({'message': 'Category updated', 'business': business.merchant_name})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5001)