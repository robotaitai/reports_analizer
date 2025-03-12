# Expense Analyzer

This project analyzes expense HTML reports, extracts transactions, aggregates totals by business, and provides a simple web dashboard with analytics.

## Features

- **Automated Scanning:** Reads HTML files from the `excel_files/` folder.
- **Duplicate Detection:** Prevents duplicate transactions based on date, merchant, and amount.
- **Category Management:** Assign and update business categories (configurable via `config.yaml`).
- **Analytics:** Displays transactions, aggregated business totals, and pie/bar charts.
- **File Upload:** Upload new HTML files via the web interface.

## Configuration

Update `config.yaml` to change the list of categories:

```yaml
categories:
  - Uncategorized
  - Food
  - Clothing
  - Travel
  - Entertainment
  - Utilities
  - Healthcare
  - Education
  - Car Expenses
  - Other
```
## Setup
 
1.	Create a virtual environment and activate it:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
2. Access the dashboard at: http://127.0.0.1:5000

## Git

The .gitignore file is set up to ignore the excel_files/ folder, virtual environment, and database files.

# License
MIT License