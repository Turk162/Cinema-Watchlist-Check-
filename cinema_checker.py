#!/usr/bin/env python3
"""
Script per controllare se i film della watchlist Letterboxd
sono in programmazione nei cinema di Roma - VERSIONE DEBUG
"""
import requests
import feedparser
import re
from bs4 import BeautifulSoup
import difflib
from datetime import datetime
import os
import json

class CinemaWatchlistChecker:
    def __init__(self):
        print("🔧 Initializing CinemaWatchlistChecker...")
        
        # Configurazione Telegram
        self.telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        print(f"🔑 Telegram configured: {bool(self.telegram_bot_token and self.telegram_chat_id)}")
        
        # URL configurabili
        self.letterboxd_rss = os.environ.get('LETTERBOXD_RSS', 
            'https://letterboxd.com/Guidaccio/rss/')
        
        print(f"📋 Letterboxd RSS: {self.letterboxd_rss}")
        
    def get_watchlist_films(self):
        """Estrae i film dalla watchlist Letterboxd via RSS o web scraping"""
        try:
            print("📡 Trying RSS feed...")
            feed = feedparser.parse(self.letterboxd_rss)
            print(f"📊 RSS entries found: {len(feed.entries)}")
            
            if feed.entries:
                films = []
                for entry in feed.entries:
                    title = entry.title
                    # Rimuovi rating e anno per ottenere solo il titolo
                    clean_title = re.sub(r'\s*,\s*\d{4}\s*-\s*[★½]*.*$', '', title)
                    clean_title = re.sub(r'\s+\(\d{4}\).*$', '', clean_title)
                    
                    # Controlla se è dalla watchlist (non ha rating)
                    if '★' not in title:  # Film senza rating = in watchlist
                        films.append({
                            'title': clean_title.strip(),
                            'original_title': title,
                            'url': entry.link if hasattr(entry, 'link') else ''
                        })
                        
                if films:
                    print(f"✅ Found {len(films)} films in RSS watchlist")
                    return films
                    
        except Exception as e:
            print(f"⚠️ RSS failed: {e}")
        
        # Se RSS fallisce, prova web scraping
        print("📡 Trying web scraping...")
        return self.get_watchlist_from_web()
    
    def get_watchlist_from_web(self):
        """Scrapa la watchlist direttamente dalla pagina web"""
        try:
            username = self.letterboxd_rss.split('/')[-3] if 'letterboxd.com' in self.letterboxd_rss else 'guidaccio'
            watchlist_url = f"https://letterboxd.com/{username}/watchlist/"
            print(f"🌐 Scraping watchlist: {watchlist_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(watchlist_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            films = []
            
            # Cerca i poster dei film (pattern tipico di Letterboxd)
            for img in soup.find_all('img', alt=True):
                alt_text = img.get('alt', '')
                if alt_text and alt_text != 'Poster':
                    # Pulisci il titolo dall'alt text
                    clean_title = re.sub(r'\s+\(\d{4}\).*$', '', alt_text)
                    if clean_title and len(clean_title) > 1:
                        films.append({
                            'title': clean_title.strip(),
                            'original_title': alt_text,
                            'url': watchlist_url
                        })
            
            # Rimuovi duplicati
            seen = set()
            unique_films = []
            for film in films:
                if film['title'] not in seen:
                    seen.add(film['title'])
                    unique_films.append(film)
            
            print(f"✅ Found {len(unique_films)} films via web scraping")
            return unique_films[:20]  # Limita per test
            
        except Exception as e:
            print(f"❌ Error scraping watchlist: {e}")
            return []
    
    def get_simple_roma_films(self):
        """Versione semplificata per ottenere film romani"""
        print("🎬 Getting Roma cinema films (simple version)...")
        
        # Lista film di test per debugging
        test_films = [
            {'title': 'Dune', 'source': 'test', 'cinema_info': {'search_url': 'test'}},
            {'title': 'The Batman', 'source': 'test', 'cinema_info': {'search_url': 'test'}},
            {'title': 'Spider-Man', 'source': 'test', 'cinema_info': {'search_url': 'test'}},
            {'title': 'Avengers', 'source': 'test', 'cinema_info': {'search_url': 'test'}},
            {'title': 'Inception', 'source': 'test', 'cinema_info': {'search_url': 'test'}}
        ]
        
        print(f"🎭 Test films loaded: {len(test_films)}")
        return test_films
    
    def find_matches(self, watchlist_films, cinema_films):
        """Trova corrispondenze tra watchlist e cinema"""
        matches = []
        
        print("🔍 Looking for matches...")
        print(f"📋 Watchlist films: {[f['title'] for f in watchlist_films[:5]]}...")
        print(f"🎬 Cinema films: {[f['title'] for f in cinema_films[:5]]}...")
        
        for watchlist_film in watchlist_films:
            watchlist_title = watchlist_film['title'].lower()
            
            for cinema_film in cinema_films:
                cinema_title = cinema_film['title'].lower()
                
                # Matching esatto
                if watchlist_title == cinema_title:
                    matches.append({
                        'watchlist_film': watchlist_film,
                        'cinema_film': cinema_film,
                        'match_score': 1.0,
                        'match_type': 'exact'
                    })
                    print(f"🎯 Exact match: {watchlist_title}")
                    continue
                
                # Fuzzy matching
                similarity = difflib.SequenceMatcher(None, watchlist_title, cinema_title).ratio()
                if similarity > 0.8:  # 80% di similarità per test
                    matches.append({
                        'watchlist_film': watchlist_film,
                        'cinema_film': cinema_film,
                        'match_score': similarity,
                        'match_type': 'fuzzy'
                    })
                    print(f"🎯 Fuzzy match: {watchlist_title} ~ {cinema_title} ({similarity:.0%})")
        
        print(f"✅ Total matches found: {len(matches)}")
        return matches
    
    def send_telegram_notification(self, matches):
        """Invia notifica Telegram"""
        print("📱 Preparing Telegram notification...")
        
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("⚠️ Telegram not configured, printing results instead")
            self.print_matches(matches)
            return
            
        if not matches:
            message = "🎭 Nessun film della tua watchlist trovato nei cinema di Roma (test debug)"
        else:
            message = f"🎬 FILM TROVATI! ({len(matches)} match - test debug)\n\n"
            
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                score = match['match_score']
                
                message += f"{i}. 🎞️ {film}\n"
                message += f"   🎯 Match: {score:.0%}\n"
                message += f"   📍 Test Cinema Roma\n\n"
                
            message += f"🗓️ Test eseguito il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
            
        try:
            print("📤 Sending Telegram message...")
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("✅ Telegram notification sent successfully!")
            
        except Exception as e:
            print(f"❌ Error sending Telegram notification: {e}")
            self.print_matches(matches)
    
    def print_matches(self, matches):
        """Stampa i risultati sulla console"""
        print("\n" + "="*50)
        print("🎬 RISULTATI TEST CINEMA ROMA")
        print("="*50)
        
        if not matches:
            print("❌ Nessun film della watchlist trovato")
        else:
            print(f"✅ Trovati {len(matches)} film:")
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                score = match['match_score']
                print(f"\n{i}. {film}")
                print(f"   Match: {score:.0%}")
                
        print(f"\n🕒 Test eseguito il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
        print("="*50)
    
    def run(self):
        """Esegue il controllo completo - versione debug"""
        print("🚀 Starting cinema watchlist checker (DEBUG VERSION)...")
        
        try:
            # 1. Ottieni film dalla watchlist
            print("\n📋 STEP 1: Getting watchlist...")
            watchlist_films = self.get_watchlist_films()
            if not watchlist_films:
                print("❌ No films found in watchlist")
                # Invia comunque notifica
                self.send_telegram_notification([])
                return
                
            # 2. Ottieni film in programmazione (versione test)
            print("\n🎬 STEP 2: Getting cinema films...")
            cinema_films = self.get_simple_roma_films()
            
            # 3. Trova corrispondenze
            print("\n🔍 STEP 3: Finding matches...")
            matches = self.find_matches(watchlist_films, cinema_films)
            
            # 4. Invia notifica
            print("\n📱 STEP 4: Sending notification...")
            self.send_telegram_notification(matches)
            
            print("\n✅ Debug check completed successfully!")
            
        except Exception as e:
            print(f"💥 FATAL ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("🎬 Cinema Watchlist Checker - DEBUG VERSION")
    print("=" * 50)
    
    try:
        checker = CinemaWatchlistChecker()
        checker.run()
    except Exception as e:
        print(f"💥 SCRIPT FAILED: {e}")
        import traceback
        traceback.print_exc()
