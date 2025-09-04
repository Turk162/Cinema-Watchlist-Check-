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
    
    def get_roma_cinema_films(self):
        """Scrapa i film in programmazione a Roma da romatoday.it"""
        all_films = []
        roma_urls = [
            'https://www.romatoday.it/eventi/cinema/',
            'https://www.romatoday.it/eventi/tipo/cinema/'
        ]
        
        for url in roma_urls:
            try:
                print(f"📡 Scraping {url}...")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Pattern 1: Link con "cinema" o "film" 
                cinema_links = soup.find_all('a', href=re.compile(r'(cinema|film)', re.I))
                
                for link in cinema_links:
                    title_text = link.get_text(strip=True)
                    if title_text and 5 < len(title_text) < 80:
                        # Pulisci il titolo
                        clean_title = re.sub(r'\s*-\s*.*$', '', title_text)
                        clean_title = re.sub(r'\s*\(\d{4}\).*$', '', clean_title)
                        clean_title = re.sub(r'\s*(al cinema|cinema|programmazione).*$', '', clean_title, flags=re.I)
                        
                        if len(clean_title) > 3 and clean_title not in [f['title'] for f in all_films]:
                            all_films.append({
                                'title': clean_title.strip(),
                                'source': url,
                                'cinema_info': {'search_url': url}
                            })
                
                # Pattern 2: Titoli in h1, h2, h3
                title_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong'], string=re.compile(r'^[A-Za-z0-9À-ÿ\s\-:]+$'))
                
                for element in title_elements:
                    title_text = element.get_text(strip=True)
                    if title_text and 5 < len(title_text) < 80:
                        skip_words = ['programmazione', 'eventi', 'roma', 'cinema', 'oggi', 'domani', 'festival']
                        if not any(word in title_text.lower() for word in skip_words):
                            clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title_text)
                            
                            if len(clean_title) > 3 and clean_title not in [f['title'] for f in all_films]:
                                all_films.append({
                                    'title': clean_title.strip(),
                                    'source': url,
                                    'cinema_info': {'search_url': url}
                                })
                
                print(f"✅ Found {len([f for f in all_films if f['source'] == url])} films from this source")
                
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
                continue
        
        # Rimuovi duplicati e limita
        unique_films = []
        seen_titles = set()
        for film in all_films:
            if film['title'] not in seen_titles and len(film['title']) > 3:
                seen_titles.add(film['title'])
                unique_films.append(film)
        
        final_films = unique_films[:50]  # Limita a 50 per performance
        print(f"🎬 Total unique films from Roma: {len(final_films)}")
        
        # Mostra alcuni film trovati per debug
        if final_films:
            sample_titles = [f['title'] for f in final_films[:10]]
            print(f"📋 Sample Roma films: {sample_titles}")
        
        return final_films
    
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
            message = "🎭 Nessun film della tua watchlist è attualmente in programmazione a Roma"
        else:
            message = f"🎬 FILM TROVATI A ROMA! ({len(matches)} match)\n\n"
            
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                score = match['match_score']
                
                message += f"{i}. 🎞️ <b>{film}</b>\n"
                message += f"   🎯 Match: {score:.0%}\n"
                message += f"   📍 RomaToday Cinema\n"
                
                # Link per cercare programmazione
                search_query = film.replace(' ', '+')
                google_search = f"https://www.google.com/search?q={search_query}+cinema+Roma+programmazione+2025"
                message += f"   🔍 <a href='{google_search}'>Cerca programmazione</a>\n"
                message += f"   📰 <a href='https://www.romatoday.it/eventi/cinema/'>RomaToday Cinema</a>\n\n"
                
            message += f"🗓️ Controllato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
            
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
                
            # 2. Ottieni film in programmazione (versione REALE)
            print("\n🎬 STEP 2: Getting cinema films...")
            cinema_films = self.get_roma_cinema_films()
            
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
