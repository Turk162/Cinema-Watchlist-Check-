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
        """Estrae i film dalla watchlist Letterboxd via RSS"""
        try:
            print("📡 Downloading Letterboxd watchlist...")
            feed = feedparser.parse(self.letterboxd_rss)
            
            films = []
            for entry in feed.entries:
                # Il titolo del film è nel title del feed
                title = entry.title
                # Rimuovi anno e info extra
                clean_title = re.sub(r'\s+\(\d{4}\).*$', '', title)
                films.append({
                    'title': clean_title.strip(),
                    'original_title': title,
                    'url': entry.link if hasattr(entry, 'link') else ''
                })
                
            print(f"✅ Found {len(films)} films in watchlist")
            return films
            
        except Exception as e:
            print(f"❌ Error getting watchlist: {e}")
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
