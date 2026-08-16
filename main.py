import os
import requests

ODDS_API_KEY = os.getenv('ODDS_API_KEY', 'f0b8eddeb970f8aa61af5e7fd292e310')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8908381273:AAHDG3wnyg-gL4DDI6oQpsw0MRyS9BjOifk')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '8040201784')

VA_BOOKMAKERS = 'draftkings,fanduel,betmgm,williamhill_us,fanatics,betrivers'
SPORTS = ['baseball_mlb', 'basketball_wnba']

# Markets configuration
GAME_MARKETS = 'h2h,spreads,totals'
MLB_PROP_MARKETS = (
    'batter_hits,batter_runs_scored,batter_rbis,batter_total_bases,'
    'batter_home_runs,pitcher_strikeouts,batter_hits_runs_rbis'
)
WNBA_PROP_MARKETS = (
    'player_points,player_rebounds,player_assists,'
    'player_points_rebounds_assists,player_points_rebounds,'
    'player_points_assists,player_rebounds_assists'
)

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID, 
        'text': message, 
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception:
        pass

all_alerts = []

for sport in SPORTS:
    sport_label = "MLB" if sport == 'baseball_mlb' else "WNBA"
    
    # 1. Scan Game-Level Markets (h2h, spreads, totals)
    odds_url = f'https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={ODDS_API_KEY}&regions=us&markets={GAME_MARKETS}&bookmakers={VA_BOOKMAKERS}'
    response = requests.get(odds_url)
    
    if response.status_code == 200:
        games = response.json()
        for game in games:
            home = game['home_team']
            away = game['away_team']
            books = game.get('bookmakers', [])
            
            if len(books) < 2:
                continue
                
            market_prices = {'h2h': {}, 'spreads': {}, 'totals': {}}
            for book in books:
                book_title = book['title']
                for market in book.get('markets', []):
                    m_key = market['key']
                    if m_key in market_prices:
                        for outcome in market.get('outcomes', []):
                            name = outcome.get('name')
                            price = outcome.get('price')
                            point = outcome.get('point', '')
                            key_name = f"{name} ({point})" if point != '' else name
                            
                            if key_name not in market_prices[m_key]:
                                market_prices[m_key][key_name] = []
                            market_prices[m_key][key_name].append({'book': book_title, 'price': price})
            
            for m_key, outcomes in market_prices.items():
                for target, entries in outcomes.items():
                    if len(entries) >= 2:
                        prices = [e['price'] for e in entries]
                        best_entry = max(entries, key=lambda x: x['price'])
                        worst_entry = min(entries, key=lambda x: x['price'])
                        
                        if max(prices) - min(prices) >= 15:
                            alert_msg = (
                                f"🚨 *VA Discrepancy Found ({sport_label} - {m_key.upper()})*\n"
                                f"*{away} @ {home}*\n"
                                f"• **Target**: {target}\n"
                                f"• **Best**: {best_entry['book']} (`{best_entry['price']}`)\n"
                                f"• **Worst**: {worst_entry['book']} (`{worst_entry['price']}`)\n"
                            )
                            all_alerts.append(alert_msg)

    # 2. Scan Player Props
    events_url = f'https://api.the-odds-api.com/v4/sports/{sport}/events?apiKey={ODDS_API_KEY}'
    events_res = requests.get(events_url)
    
    if events_res.status_code == 200:
        events = events_res.json()
        prop_markets = MLB_PROP_MARKETS if sport == 'baseball_mlb' else WNBA_PROP_MARKETS
        
        for event in events[:3]: # Limited to first 3 events to manage API request volume
            event_id = event['id']
            home = event['home_team']
            away = event['away_team']
            
            event_odds_url = f'https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds?apiKey={ODDS_API_KEY}&regions=us&markets={prop_markets}&bookmakers={VA_BOOKMAKERS}'
            odds_res = requests.get(event_odds_url)
            
            if odds_res.status_code == 200:
                event_data = odds_res.json()
                books = event_data.get('bookmakers', [])
                
                if len(books) < 2:
                    continue
                    
                prop_prices = {}
                for book in books:
                    book_title = book['title']
                    for market in book.get('markets', []):
                        m_key = market['key']
                        for outcome in market.get('outcomes', []):
                            player_name = outcome.get('description', '')
                            over_under = outcome.get('name', '')
                            point = outcome.get('point', '')
                            price = outcome.get('price', 0)
                            
                            if not player_name:
                                continue
                                
                            key_identifier = f"{player_name} - {m_key} ({point} {over_under})"
                            if key_identifier not in prop_prices:
                                prop_prices[key_identifier] = []
                            prop_prices[key_identifier].append({'book': book_title, 'price': price})
                
                for target, entries in prop_prices.items():
                    if len(entries) >= 2:
                        prices = [e['price'] for e in entries]
                        best_entry = max(entries, key=lambda x: x['price'])
                        worst_entry = min(entries, key=lambda x: x['price'])
                        
                        if max(prices) - min(prices) >= 15:
                            alert_msg = (
                                f"🚨 *VA Extended Prop Discrepancy ({sport_label})*\n"
                                f"*{away} @ {home}*\n"
                                f"• **Prop**: {target}\n"
                                f"• **Best**: {best_entry['book']} (`{best_entry['price']}`)\n"
                                f"• **Worst**: {worst_entry['book']} (`{worst_entry['price']}`)\n"
                            )
                            all_alerts.append(alert_msg)

# Deliver results to Telegram
if all_alerts:
    final_message = "\n".join(all_alerts[:4])
    send_telegram_alert(final_message)
    print("Discrepancy alerts pushed to Telegram successfully!")
else:
    status_message = f"ℹ️ VA Scanner check complete for MLB & WNBA: All lines tightly aligned."
    send_telegram_alert(status_message)
    print("Scanner completed. Status update sent.")
