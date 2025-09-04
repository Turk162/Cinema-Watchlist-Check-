#!/usr/bin/env python3
"""
Script per controllare se i film della watchlist Letterboxd
sono in programmazione nei cinema di Roma
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
        # Configurazione Telegram (ottenibile da @BotFather)
        self.telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        # URL configurabili
        self.letterboxd_rss = os.environ.get('LETTERBOXD_RSS', 
            'https://letterboxd.com/Guidaccio/rss/')
        self.mymovies_urls = [
            'https://www.mymovies.it/cinema/roma/',
            'https://www.mymovies.it/cinema/roma/versione-originale/'
        ]
        
    def get_watchlist_films(self):
        """Estrae i film dalla watchlist Letterboxd via RSS o web scraping"""
        # Prova prima con RSS
        try:
            print("📡 Trying RSS feed...")
            feed = feedparser.parse(self.letterboxd_rss)
            
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
            return unique_films[:50]  # Limita a 50 per sicurezza
            
        except Exception as e:
            print(f"❌ Error scraping watchlist: {e}")
            return []
    
    def get_roma_cinema_films(self):
        """Scrapa i film in programmazione a Roma da mymovies.it"""
        all_films = []
        
        for url in self.mymovies_urls:
            try:
                print(f"📡 Scraping {url}...")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Cerca i titoli dei film (pattern tipico di mymovies)
                film_elements = soup.find_all(['h1', 'h2', 'h3'], string=re.compile(r'.+'))
                film_links = soup.find_all('a', href=re.compile(r'/film/'))
                
                # Estrai i titoli dai link dei film
                for link in film_links:
                    if link.text.strip() and len(link.text.strip()) > 2:
                        title = link.text.strip()
                        # Pulisci il titolo
                        clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title)
                        if clean_title and clean_title not in [f['title'] for f in all_films]:
                            all_films.append({
                                'title': clean_title.strip(),
                                'source': url,
                                'url': link.get('href', '')
                            })
                            
                print(f"✅ Found {len([f for f in all_films if f['source'] == url])} films from this source")
                
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
                continue
                
        print(f"🎬 Total films in Roma cinemas: {len(all_films)}")
        return all_films
    
    def find_matches(self, watchlist_films, cinema_films):
        """Trova corrispondenze tra watchlist e cinema usando fuzzy matching"""
        matches = []
        
        print("🔍 Looking for matches...")
        
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
                    continue
                
                # Fuzzy matching (per titoli leggermente diversi)
                similarity = difflib.SequenceMatcher(None, watchlist_title, cinema_title).ratio()
                if similarity > 0.85:  # 85% di similarità
                    matches.append({
                        'watchlist_film': watchlist_film,
                        'cinema_film': cinema_film,
                        'match_score': similarity,
                        'match_type': 'fuzzy'
                    })
                    
        print(f"🎯 Found {len(matches)} matches")
        return matches
    
    def send_telegram_notification(self, matches):
        """Invia notifica Telegram con i match trovati"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("⚠️ Telegram not configured, printing results instead:")
            self.print_matches(matches)
            return
            
        if not matches:
            message = "🎭 Nessun film della tua watchlist è attualmente in programmazione a Roma"
        else:
            message = f"🎬 FILM TROVATI A ROMA! ({len(matches)} match)\n\n"
            
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                source = "Roma" if "versione-originale" not in match['cinema_film']['source'] else "Roma (V.O.)"
                score = match['match_score']
                
                message += f"{i}. 🎞️ {film}\n"
                message += f"   📍 {source}\n"
                message += f"   🎯 Match: {score:.0%}\n\n"
                
            message += f"🗓️ Controllato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print("✅ Telegram notification sent!")
            
        except Exception as e:
            print(f"❌ Error sending Telegram notification: {e}")
            self.print_matches(matches)
    
    def print_matches(self, matches):
        """Stampa i risultati sulla console"""
        print("\n" + "="*50)
        print("🎬 RISULTATI CONTROLLO CINEMA ROMA")
        print("="*50)
        
        if not matches:
            print("❌ Nessun film della watchlist trovato in programmazione")
        else:
            print(f"✅ Trovati {len(matches)} film in programmazione:")
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                source = "Roma" if "versione-originale" not in match['cinema_film']['source'] else "Roma (V.O.)"
                score = match['match_score']
                print(f"\n{i}. {film}")
                print(f"   Programmato a: {source}")
                print(f"   Accuratezza match: {score:.0%}")
                
        print(f"\n🕒 Controllato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
        print("="*50)
    
    def run(self):
        """Esegue il controllo completo"""
        print("🚀 Starting cinema watchlist checker...")
        
        # 1. Ottieni film dalla watchlist
        watchlist_films = self.get_watchlist_films()
        if not watchlist_films:
            print("❌ No films found in watchlist")
            return
            
        # 2. Ottieni film in programmazione a Roma
        cinema_films = self.get_roma_cinema_films()
        if not cinema_films:
            print("❌ No films found in Roma cinemas")
            return
            
        # 3. Trova corrispondenze
        matches = self.find_matches(watchlist_films, cinema_films)
        
        # 4. Invia notifica
        self.send_telegram_notification(matches)
        
        print("✅ Check completed!")

if __name__ == "__main__":
    checker = CinemaWatchlistChecker()
    checker.run()
