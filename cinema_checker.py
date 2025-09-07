#!/usr/bin/env python3
"""
Script per controllare se i film della watchlist Letterboxd
sono in programmazione nei cinema di Roma - VERSIONE AVANZATA
"""
import requests
import feedparser
import re
from bs4 import BeautifulSoup
import difflib
from datetime import datetime
import os
import json
import string

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
                            'alternative_titles': [],
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
        """Scrapa la watchlist direttamente dalla pagina web con titoli multipli"""
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
            
            print("🔍 Looking for film containers with multiple titles...")
            
            # Pattern 1: Cerca container di film con poster
            film_containers = soup.find_all(['li', 'div'], class_=re.compile(r'(poster|film|movie)', re.I))
            
            for container in film_containers:
                film_titles = self.extract_multiple_titles_from_container(container, watchlist_url)
                if film_titles:
                    films.append(film_titles)
                    print(f"📽️ Found: {film_titles}")
            
            # Pattern 2: Fallback con immagini
            if len(films) < 5:
                print("🔄 Fallback to image alt text method...")
                for img in soup.find_all('img', alt=True):
                    alt_text = img.get('alt', '')
                    if alt_text and alt_text != 'Poster' and len(alt_text) > 3:
                        clean_title = self.clean_title(alt_text)
                        if clean_title:
                            films.append({
                                'title': clean_title,
                                'original_title': alt_text,
                                'alternative_titles': [],
                                'url': watchlist_url
                            })
            
            print(f"✅ Found {len(films)} films via enhanced web scraping")
            return films[:30]
            
        except Exception as e:
            print(f"❌ Error scraping watchlist: {e}")
            return []
    
    def extract_multiple_titles_from_container(self, container, watchlist_url):
        """Estrae titoli multipli da un container di film"""
        try:
            main_title = None
            alt_titles = []
            
            # 1. Cerca negli attributi alt delle immagini
            img = container.find('img', alt=True)
            if img:
                main_title = img.get('alt', '').strip()
            
            # 2. Cerca nei link al film
            film_link = container.find('a', href=re.compile(r'/film/'))
            if film_link and film_link.get_text(strip=True):
                potential_title = film_link.get_text(strip=True)
                if not main_title:
                    main_title = potential_title
                elif potential_title != main_title:
                    alt_titles.append(potential_title)
            
            # 3. Cerca sottotitoli in corsivo
            subtitle_elements = container.find_all(['em', 'i', 'span'], string=re.compile(r'^[A-Za-z0-9À-ÿ\s\-:,\.\'\"]+$'))
            
            for element in subtitle_elements:
                text = element.get_text(strip=True)
                if text and len(text) > 3 and text not in [main_title] + alt_titles:
                    if not any(word in text.lower() for word in ['directed', 'starring', 'runtime', 'year']):
                        alt_titles.append(text)
            
            if main_title:
                main_title = self.clean_title(main_title)
                clean_alt_titles = [self.clean_title(title) for title in alt_titles if self.clean_title(title)]
                
                final_alt_titles = []
                for alt_title in clean_alt_titles:
                    if len(alt_title) > 3 and alt_title != main_title:
                        similarity = difflib.SequenceMatcher(None, main_title.lower(), alt_title.lower()).ratio()
                        if similarity < 0.9:
                            final_alt_titles.append(alt_title)
                
                return {
                    'title': main_title,
                    'original_title': main_title,
                    'alternative_titles': final_alt_titles[:3],
                    'url': watchlist_url
                }
                
        except Exception as e:
            print(f"Warning: Error extracting titles from container: {e}")
        
        return None
    
    def clean_title(self, title):
        """Pulisce un titolo rimuovendo info extra"""
        if not title:
            return ""
            
        clean = re.sub(r'\s+\(\d{4}\).*$', '', title)
        clean = re.sub(r'\s*[–—-]\s*(directed|starring|runtime).*$', '', clean, flags=re.I)
        clean = re.sub(r'\s+', ' ', clean)
        
        return clean.strip()
    
    def get_roma_cinema_films(self):
        """Scrapa i film in programmazione a Roma da ComingSoon.it"""
        all_films = []
        
        cinema_sources = [
            'https://www.comingsoon.it/cinema/roma/',
        ]
        
        for url in cinema_sources:
            try:
                print(f"📡 Scraping {url}...")
                
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
                
                print(f"✅ Found {len(films_from_source)} films from {url}")
                all_films.extend(films_from_source)
                
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
                continue
        
        # Rimuovi duplicati
        unique_films = []
        seen_titles = set()
        for film in all_films:
            if film['title'] not in seen_titles and len(film['title']) > 2:
                seen_titles.add(film['title'])
                unique_films.append(film)
        
        final_films = unique_films[:150]
        print(f"🎬 Total unique films from Roma (ComingSoon): {len(final_films)}")
        
        if final_films:
            sample_titles = [f['title'] for f in final_films[:20]]
            print(f"📋 Sample Roma films: {sample_titles}")
        
        return final_films
    
    def extract_comingsoon_films(self, soup, source_url):
        """Estrae film specificamente da ComingSoon.it"""
        films = []
        
        try:
            # Cerca link ai film
            film_links = soup.find_all('a', href=re.compile(r'(/film/|/cinema/)', re.I))
            
            for link in film_links:
                title_text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if title_text and len(title_text) > 3 and len(title_text) < 100:
                    skip_words = ['home', 'contatti', 'cinema', 'orari', 'prezzi', 'info', 'roma']
                    if not any(word in title_text.lower() for word in skip_words):
                        clean_title = self.clean_title(title_text)
                        
                        if len(clean_title) > 3:
                            film_url = href if href.startswith('http') else f"https://www.comingsoon.it{href}"
                            
                            films.append({
                                'title': clean_title,
                                'source': source_url,
                                'cinema_info': {
                                    'search_url': source_url,
                                    'film_url': film_url,
                                    'source_name': 'ComingSoon'
                                }
                            })
            
            # Cerca nei titoli
            title_elements = soup.find_all(['h1', 'h2', 'h3', 'h4'], string=re.compile(r'^[A-Za-z0-9À-ÿ\s\-:\.]+$'))
            
            for element in title_elements:
                title_text = element.get_text(strip=True)
                if title_text and 5 < len(title_text) < 100:
                    skip_words = ['programmazione', 'cinema', 'roma', 'orari', 'coming soon']
                    if not any(word in title_text.lower() for word in skip_words):
                        clean_title = self.clean_title(title_text)
                        
                        if len(clean_title) > 3:
                            films.append({
                                'title': clean_title,
                                'source': source_url,
                                'cinema_info': {
                                    'search_url': source_url,
                                    'source_name': 'ComingSoon'
                                }
                            })
                            
        except Exception as e:
            print(f"Error extracting from ComingSoon: {e}")
        
        return films
    
    def find_matches(self, watchlist_films, cinema_films):
        """Trova corrispondenze tra watchlist e cinema usando titoli multipli"""
        matches = []
        
        print("🔍 Looking for matches with multiple title support...")
        
        for watchlist_film in watchlist_films:
            if isinstance(watchlist_film, dict) and 'alternative_titles' in watchlist_film:
                titles_to_check = [watchlist_film['title']] + watchlist_film.get('alternative_titles', [])
                film_display_name = watchlist_film['title']
            else:
                if isinstance(watchlist_film, dict):
                    titles_to_check = [watchlist_film['title']]
                    film_display_name = watchlist_film['title']
                else:
                    continue
            
            print(f"🎯 Checking '{film_display_name}'")
            
            best_match = None
            best_score = 0
            
            for cinema_film in cinema_films:
                cinema_title = cinema_film['title']
                
                for watchlist_title in titles_to_check:
                    if not watchlist_title or len(watchlist_title) < 3:
                        continue
                    
                    # Matching esatto
                    if watchlist_title.lower().strip() == cinema_title.lower().strip():
                        match_score = 1.0
                        match_type = 'exact'
                        print(f"  ✅ Exact match: '{watchlist_title}' = '{cinema_title}'")
                    else:
                        # Matching avanzato
                        match_score = self.advanced_title_matching(watchlist_title, cinema_title)
                        match_type = 'advanced'
                        
                        if match_score > 0.75:
                            print(f"  ✅ Advanced match: '{watchlist_title}' ~ '{cinema_title}' ({match_score:.0%})")
                    
                    if match_score > best_score and match_score > 0.75:
                        best_match = {
                            'watchlist_film': {
                                'title': film_display_name,
                                'original_title': watchlist_film.get('original_title', film_display_name),
                                'matched_title': watchlist_title,
                                'url': watchlist_film.get('url', '')
                            },
                            'cinema_film': cinema_film,
                            'match_score': match_score,
                            'match_type': match_type
                        }
                        best_score = match_score
            
            if best_match:
                matches.append(best_match)
        
        print(f"✅ Total matches found: {len(matches)}")
        return matches
    
    def advanced_title_matching(self, title1, title2):
        """Matching avanzato per gestire titoli inglese/italiano"""
        norm1 = self.normalize_title(title1)
        norm2 = self.normalize_title(title2)
        
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
                message += f"   📍 ComingSoon Cinema\n"
                
                search_query = film.replace(' ', '+')
                google_search = f"https://www.google.com/search?q={search_query}+cinema+Roma+programmazione+orari+2025"
                message += f"   🔍 <a href='{google_search}'>Cerca programmazione</a>\n\n"
                
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
        print("🎬 RISULTATI CINEMA ROMA (ComingSoon)")
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
                
        print(f"\n🕒 Controllato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
        print("="*50)
    
    def run(self):
        """Esegue il controllo completo"""
        print("🚀 Starting cinema watchlist checker...")
        
        try:
            # 1. Ottieni film dalla watchlist
            print("\n📋 STEP 1: Getting watchlist...")
            watchlist_films = self.get_watchlist_films()
            if not watchlist_films:
                print("❌ No films found in watchlist")
                self.send_telegram_notification([])
                return
                
            # 2. Ottieni film in programmazione
            print("\n🎬