import os
import requests

API_KEY = os.getenv('ODDS_API_KEY', '').strip()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()

BOOKMAKERS = 'draftkings,fanduel,betmgm,williamhill_us,fanatics,betrivers'
SPORTS = ['baseball_mlb', 'basketball_wnba']

# The main odds endpoint only supports featured markets (h2h, spreads, totals)
MARKETS = 'h2h,spreads,totals'

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Telegram API Error: {response.text}")
        else:
            print("Telegram alert sent successfully.")
    except Exception as e:
        print(f"Error sending telegram: {e}")

def scan_market():
    alerts = []
    for sport in SPORTS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            'apiKey': API_KEY,
            'regions': 'us',
            'markets': MARKETS,
            'oddsFormat': 'american',
            'bookmakers': BOOKMAKERS
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200:
                print(f"Odds API Error ({sport}): Status {response.status_code} - {response.text}")
                continue
            events = response.json()
        except Exception as e:
            print(f"Request exception for {sport}: {e}")
            continue

        for event in events:
            home = event.get('home_team', 'Team A')
            away = event.get('away_team', 'Team B')
            matchup = f"{away} @ {home}"
            
            book_prices = {}
            for bookmaker in event.get('bookmakers', []):
                b_key = bookmaker['key']
                for market in bookmaker.get('markets', []):
                    m_key = market['key']
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name')
                        price = outcome.get('price')
                        if price is not None:
                            try:
                                int_price = int(price)
                                key = (m_key, name)
                                if key not in book_prices:
                                    book_prices[key] = {}
                                book_prices[key][b_key] = int_price
                            except ValueError:
                                continue
            
            for (m_key, name), books in book_prices.items():
                if len(books) < 2:
                    continue
                best_book = max(books, key=books.get)
                worst_book = min(books, key=books.get)
                best_val = books[best_book]
                worst_val = books[worst_book]
                
                diff = abs(best_val - worst_val)
                if diff >= 15:
                    alerts.append(f"🚨 VA Discrepancy Found ({sport.upper()} - {m_key})\n{matchup}\nTarget: {name}\nBest: {best_book} ({best_val})\nWorst: {worst_book} ({worst_val})")

    if alerts:
        for alert in alerts[:4]:
            send_telegram(alert)
    else:
        send_telegram("ℹ️ VA Scanner check complete: All lines tightly aligned.")

if __name__ == '__main__':
    scan_market()
