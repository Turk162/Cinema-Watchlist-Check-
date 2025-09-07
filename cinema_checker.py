#!/usr/bin/env python3
"""
Script per controllare se i film della watchlist Letterboxd
sono in programmazione nei cinema di Roma
"""
import requests
from bs4 import BeautifulSoup
import difflib
from datetime import datetime
import os
import string
import time
import re  # <-- AGGIUNGI QUESTA RIGA

class CinemaWatchlistChecker:
    def __init__(self):
        print("Initializing CinemaWatchlistChecker...")
        
        # Configurazione Telegram
        self.telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        print(f"Telegram configured: {bool(self.telegram_bot_token and self.telegram_chat_id)}")
        
        # URL configurabili
        self.letterboxd_rss = os.environ.get('LETTERBOXD_RSS', 
            'https://letterboxd.com/Guidaccio/rss/')
        
        print(f"Letterboxd RSS: {self.letterboxd_rss}")
        
    def get_watchlist_films(self):
        """Estrae tutti i film dalla watchlist Letterboxd via web scraping multi-pagina"""
        try:
            # Estrai username dall'URL
            username = self.letterboxd_rss.split('/')[-3] if 'letterboxd.com' in self.letterboxd_rss else 'guidaccio'
            
            print(f"Scraping watchlist for user: {username}")
            films = self.get_all_watchlist_films(username)
            
            if films:
                # Converti in formato consistente
                formatted_films = []
                for film_title in films:
                    formatted_films.append({
                        'title': film_title,
                        'original_title': film_title,
                        'alternative_titles': [],
                        'url': f'https://letterboxd.com/{username}/watchlist/'
                    })
                
                print(f"Found {len(formatted_films)} films in watchlist")
                return formatted_films
            else:
                print("No films found in watchlist")
                return []
                
        except Exception as e:
            print(f"Error getting watchlist: {e}")
            return []
    
    def get_all_watchlist_films(self, username):
        """Scrapa tutte le pagine della watchlist Letterboxd"""
        films = []
        page = 1
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        while True:
            if page == 1:
                url = f"https://letterboxd.com/{username}/watchlist/"
            else:
                url = f"https://letterboxd.com/{username}/watchlist/page/{page}/"
                
            print(f"  Scraping page {page}...")
            
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code != 200:
                    print(f"  Page {page} returned {response.status_code}, stopping")
                    break
                    
                soup = BeautifulSoup(response.content, 'html.parser')
                page_films = []
                
                for img in soup.find_all('img', alt=True):
                    alt_text = img.get('alt', '').strip()
                    if (alt_text and 
			            alt_text != 'Poster' and 
			            alt_text.lower() != username.lower() and  # Filtra username
			            alt_text != username and  # Filtra anche case sensitive
			            len(alt_text) > 3 and
			            alt_text not in films):  # Evita duplicati
                        page_films.append(alt_text)
                
                if len(page_films) < 2:  # Deve trovare almeno 2 film
                    print(f"  Found only {len(page_films)} films on page {page}, stopping")
                    break
                    
                films.extend(page_films)
                print(f"  Found {len(page_films)} films on page {page}")
                

                page += 1
                time.sleep(0.5)  # Pausa tra richieste
                
            except Exception as e:
                print(f"  Error on page {page}: {e}")
                break
        
        return films
    
    def get_roma_cinema_films(self):
        """Scrapa i film in programmazione a Roma da ComingSoon.it"""
        all_films = []
        
        url = 'https://www.comingsoon.it/cinema/roma/'
        
        try:
            print(f"Scraping {url}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
                'Referer': 'https://www.comingsoon.it/',
            }
            
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            films_from_source = self.extract_comingsoon_films(soup, url)
            
            print(f"Found {len(films_from_source)} films from ComingSoon")
            all_films.extend(films_from_source)
                
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        
        print(f"Total films from Roma: {len(all_films)}")
        
        if all_films:
            sample_titles = [f['title'] for f in all_films[:10]]
            print(f"Sample Roma films: {sample_titles}")
        
        return all_films

    def extract_comingsoon_films(self, soup, source_url):
        """Estrae film specificamente da ComingSoon.it"""
        films = []
        
        try:
            print("Extracting films from ComingSoon...")
            
            # Usa il metodo che ha funzionato: container specifici
            film_containers = soup.find_all('div', class_='header-scheda streaming min no-bg container-fluid pbm')
            
            print(f"Found {len(film_containers)} film containers")
            
            for container in film_containers:
                try:
                    # Cerca il titolo nel link con classe "tit_olo h1"
                    title_link = container.find('a', class_='tit_olo h1')
                    
                    if title_link:
                        film_title = title_link.get_text(strip=True)
                        
                        if len(film_title) > 3 and len(film_title) < 200:
                            # Ottieni URL del film se disponibile
                            film_url = title_link.get('href', '') if title_link else ''
                            if film_url and not film_url.startswith('http'):
                                film_url = 'https://www.comingsoon.it' + film_url
                            
                            films.append({
                                'title': film_title,
                                'source': source_url,
                                'cinema_info': {
                                    'search_url': source_url,
                                    'source_name': 'ComingSoon',
                                    'film_url': film_url
                                }
                            })
                            
                except Exception as e:
                    print(f"Error processing film container: {e}")
                    continue
            
        except Exception as e:
            print(f"Error extracting from ComingSoon: {e}")
        
        print(f"Total films extracted: {len(films)}")
        return films
    
    def find_matches(self, watchlist_films, cinema_films):
        """Trova corrispondenze con matching migliorato"""
        matches = []
        
        print("Looking for matches...")
        print(f"Watchlist has {len(watchlist_films)} films")
        print(f"Cinema has {len(cinema_films)} films")
        
        for watchlist_film in watchlist_films:
            if not isinstance(watchlist_film, dict):
                continue
                
            film_display_name = watchlist_film['title']
            print(f"Checking '{film_display_name}'...")
            
            best_match = None
            best_score = 0
            
            for cinema_film in cinema_films:
                cinema_title = cinema_film['title']
                
                # METODO 1: Matching esatto (case insensitive)
                if film_display_name.lower().strip() == cinema_title.lower().strip():
                    match_score = 1.0
                    print(f"  EXACT MATCH: '{film_display_name}' = '{cinema_title}'")
                    
                # METODO 2: Watchlist title contenuto nel cinema title
                elif film_display_name.lower().strip() in cinema_title.lower().strip():
                    match_score = 0.9
                    print(f"  CONTAINED MATCH: '{film_display_name}' in '{cinema_title}'")
                    
                # METODO 3: Cinema title contenuto nel watchlist title  
                elif cinema_title.lower().strip() in film_display_name.lower().strip():
                    match_score = 0.85
                    print(f"  REVERSE CONTAINED: '{cinema_title}' in '{film_display_name}'")
                    
                # METODO 4: Matching avanzato
                else:
                    match_score = self.advanced_title_matching(film_display_name, cinema_title)
                    if match_score > 0.7:
                        print(f"  ADVANCED MATCH: '{film_display_name}' ~ '{cinema_title}' ({match_score:.0%})")
                
                # Aggiorna il best match se questo è migliore
                if match_score > best_score and match_score > 0.7:  # Soglia minima
                    best_match = {
                        'watchlist_film': {
                            'title': film_display_name,
                            'original_title': watchlist_film.get('original_title', film_display_name),
                            'url': watchlist_film.get('url', '')
                        },
                        'cinema_film': cinema_film,
                        'match_score': match_score,
                        'match_type': 'exact' if match_score == 1.0 else 'partial'
                    }
                    best_score = match_score
            
            if best_match:
                matches.append(best_match)
                print(f"  BEST MATCH for '{film_display_name}': {best_match['cinema_film']['title']} ({best_score:.0%})")
        
        print(f"Total matches found: {len(matches)}")
        return matches
    
    def advanced_title_matching(self, title1, title2):
        """Matching avanzato per gestire titoli inglese/italiano"""
        norm1 = self.normalize_title(title1)
        norm2 = self.normalize_title(title2)
        
        # Prova diversi metodi di matching
        base_score = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        clean_score = difflib.SequenceMatcher(None, self.remove_articles(norm1), self.remove_articles(norm2)).ratio()
        keyword_score = self.keyword_matching(norm1, norm2)
        
        return max(base_score, clean_score, keyword_score)
    
    def normalize_title(self, title):
        """Normalizza il titolo per il matching"""
        normalized = title.lower().strip()
        normalized = normalized.translate(str.maketrans('', '', string.punctuation))
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def remove_articles(self, title):
        """Rimuove articoli e parole comuni"""
        articles = ['the', 'a', 'an', 'il', 'la', 'lo', 'i', 'le', 'gli', 'un', 'una', 'uno']
        words = title.split()
        filtered_words = [word for word in words if word not in articles]
        return ' '.join(filtered_words)
    
    def keyword_matching(self, title1, title2):
        """Matching basato su parole chiave comuni"""
        words1 = {w for w in title1.split() if len(w) > 2}
        words2 = {w for w in title2.split() if len(w) > 2}
        
        if not words1 or not words2:
            return 0
        
        common_words = words1.intersection(words2)
        if not common_words:
            return 0
        
        return len(common_words) / max(len(words1), len(words2))
    
    def send_telegram_notification(self, matches):
        """Invia notifica Telegram"""
        print("Preparing Telegram notification...")
        
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("Telegram not configured, printing results instead")
            self.print_matches(matches)
            return
            
        if not matches:
            message = "Nessun film della tua watchlist è attualmente in programmazione a Roma"
        else:
            message = f"FILM TROVATI A ROMA! ({len(matches)} match)\n\n"
            
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                cinema_title = match['cinema_film']['title']
                score = match['match_score']
                
                message += f"{i}. {film}\n"
                message += f"   Trovato come: {cinema_title}\n"
                message += f"   Match: {score:.0%}\n"
                
                search_query = cinema_title.replace(' ', '+')
                google_search = f"https://www.google.com/search?q={search_query}+cinema+Roma+programmazione+orari+2025"
                message += f"   Cerca programmazione: {google_search}\n\n"
                
            message += f"Controllato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
            
        try:
            print("Sending Telegram message...")
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("Telegram notification sent successfully!")
            
        except Exception as e:
            print(f"Error sending Telegram notification: {e}")
            self.print_matches(matches)
    
    def print_matches(self, matches):
        """Stampa i risultati sulla console"""
        print("\n" + "="*50)
        print("RISULTATI CONTROLLO CINEMA")
        print("="*50)
        
        if not matches:
            print("Nessun film della tua watchlist è attualmente in programmazione a Roma")
        else:
            print(f"TROVATI {len(matches)} FILM DELLA TUA WATCHLIST!")
            print()
            
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                cinema_title = match['cinema_film']['title']
                score = match['match_score']
                
                print(f"{i}. Film cercato: {film}")
                print(f"   Trovato come: {cinema_title}")
                print(f"   Match: {score:.0%}")
                print(f"   Fonte: {match['cinema_film']['cinema_info']['source_name']}")
                
                search_query = cinema_title.replace(' ', '+')
                print(f"   Cerca programmazione: https://www.google.com/search?q={search_query}+cinema+Roma+programmazione+orari")
                print()
        
        print(f"Controllato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
        print("="*50)
    
    def run(self):
        """Metodo principale per eseguire il controllo"""
        print("Avvio controllo cinema per watchlist...")
        
        try:
            # 1. Ottieni film dalla watchlist
            print("\nRecupero watchlist...")
            watchlist_films = self.get_watchlist_films()
            
            if not watchlist_films:
                print("Nessun film trovato nella watchlist")
                return
            
            print(f"Trovati {len(watchlist_films)} film nella watchlist")
            
            # 2. Ottieni film dai cinema di Roma
            print("\nRecupero programmazione cinema Roma...")
            cinema_films = self.get_roma_cinema_films()
            
            if not cinema_films:
                print("Nessun film trovato nei cinema di Roma")
                return
            
            print(f"Trovati {len(cinema_films)} film nei cinema")
            
            # 3. Trova corrispondenze
            print("\nRicerca corrispondenze...")
            matches = self.find_matches(watchlist_films, cinema_films)
            
            # 4. Invia notifica
            print("\nInvio notifica...")
            self.send_telegram_notification(matches)
            
            print("Controllo completato!")
            
        except Exception as e:
            print(f"Errore durante l'esecuzione: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    checker = CinemaWatchlistChecker()
    checker.run()
