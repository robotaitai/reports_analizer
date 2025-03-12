# parser.py
from bs4 import BeautifulSoup

def parse_html_transactions(file_path):
    """
    Parses an HTML file and extracts transactions.
    Expected structure in the HTML:
    
      <div role="cell" xlcell="1" data-header="תאריך העסקה" class="ts-table-row-item xlFull-date">
          <span class="ts-num show-exporttool">28/02/25</span>
      </div>
      <div role="cell" xlcell="2" data-header="שם בית העסק" class="ts-table-row-item tw-flex-grow-2">
          <span>Merchant Name</span>
      </div>
      <div role="cell" xlcell="3" data-header="סכום העסקה" class="ts-table-row-item xlformatNumber">
          <app-common-number size="sm">
            <div class="ts-num sm">
              <span class="ng-star-inserted">39.46</span>
            </div>
          </app-common-number>
    
    Returns a list of dictionaries with keys: date, merchant, amount.
    
    This updated version normalizes the amount (removing commas) and uses a deduplication set to avoid duplicate transactions.
    """
    transactions = []
    seen = set()  # To track unique transactions (date, merchant, normalized amount)
    
    with open(file_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, 'html.parser')

    entries = soup.find_all('section', class_='cc-table-entry')
    for entry in entries:
        try:
            date_cell = entry.find('div', {'data-header': 'תאריך העסקה'})
            date_value = date_cell.find('span').text.strip() if date_cell else None

            merchant_cell = entry.find('div', {'data-header': 'שם בית העסק'})
            merchant_value = merchant_cell.find('span').text.strip() if merchant_cell else None

            amount_cell = entry.find('div', {'data-header': 'סכום העסקה'})
            amount_span = amount_cell.find('span', class_='ng-star-inserted') if amount_cell else None
            amount_value = amount_span.text.strip() if amount_span else None

            if date_value and merchant_value and amount_value:
                # Normalize the amount: remove Unicode markers and commas.
                norm_amount = amount_value.replace('\u200e', '').replace(',', '').strip()
                # Create a deduplication key using normalized values.
                key = (date_value.strip(), merchant_value.strip(), norm_amount)
                if key in seen:
                    continue
                seen.add(key)
                transactions.append({
                    'date': date_value,
                    'merchant': merchant_value,
                    'amount': norm_amount,
                })
        except Exception as e:
            print("Error parsing an entry:", e)
    return transactions