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
        
        # URL configurabili - AGGIORNATO per RomaToday
        self.letterboxd_rss = os.environ.get('LETTERBOXD_RSS', 
            'https://letterboxd.com/Guidaccio/rss/')
        self.roma_cinema_urls = [
            'https://www.romatoday.it/eventi/cinema/',
            'https://www.romatoday.it/eventi/tipo/cinema/'
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
        """Scrapa i film in programmazione a Roma da romatoday.it"""
        all_films = []
        
        for url in self.roma_cinema_urls:
            try:
                print(f"📡 Scraping {url}...")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Cerca i film su RomaToday - diversi pattern possibili
                film_elements = self.extract_films_romatoday(soup, url)
                
                for film_data in film_elements:
                    if film_data and film_data['title'] not in [f['title'] for f in all_films]:
                        all_films.append(film_data)
                        
                print(f"✅ Found {len([f for f in all_films if f['source'] == url])} films from this source")
                
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
                continue
                
        print(f"🎬 Total films in Roma cinemas: {len(all_films)}")
        return all_films
    
    def extract_films_romatoday(self, soup, source_url):
        """Estrae film specificamente da RomaToday.it"""
        films = []
        
        try:
            # Pattern 1: Cerca link con "cinema" o "film" nell'href
            cinema_links = soup.find_all('a', href=re.compile(r'(cinema|film)', re.I))
            
            for link in cinema_links:
                title_text = link.get_text(strip=True)
                if title_text and len(title_text) > 3 and len(title_text) < 100:
                    # Pulisci il titolo
                    clean_title = re.sub(r'\s*-\s*.*$', '', title_text)  # Rimuovi tutto dopo il primo "-"
                    clean_title = re.sub(r'\s*\(\d{4}\).*$', '', clean_title)  # Rimuovi anno
                    clean_title = re.sub(r'\s*(al cinema|cinema|programmazione).*$', '', clean_title, flags=re.I)
                    
                    if len(clean_title) > 3:
                        # Estrai info cinema dall'URL o dal contesto
                        cinema_info = self.extract_cinema_info_romatoday(link, soup)
                        
                        films.append({
                            'title': clean_title.strip(),
                            'source': source_url,
                            'film_url': link.get('href', ''),
                            'cinema_info': cinema_info
                        })
            
            # Pattern 2: Cerca titoli in elementi comuni (h1, h2, h3, strong)
            title_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'b'], string=re.compile(r'^[A-Za-z0-9À-ÿ\s\-:]+$'))
            
            for element in title_elements:
                title_text = element.get_text(strip=True)
                if title_text and 5 < len(title_text) < 80:
                    # Filtri per evitare testi non pertinenti
                    skip_words = ['programmazione', 'eventi', 'roma', 'cinema', 'oggi', 'domani', 'week', 'festival']
                    if not any(word in title_text.lower() for word in skip_words):
                        clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title_text)
                        
                        if len(clean_title) > 3:
                            # Cerca link vicino a questo elemento
                            parent = element.parent
                            nearby_link = None
                            if parent:
                                nearby_link = parent.find('a', href=True)
                            
                            cinema_info = {'search_url': source_url}
                            if nearby_link:
                                cinema_info = self.extract_cinema_info_romatoday(nearby_link, soup)
                            
                            films.append({
                                'title': clean_title.strip(),
                                'source': source_url,
                                'film_url': nearby_link.get('href', '') if nearby_link else '',
                                'cinema_info': cinema_info
                            })
            
            # Pattern 3: Cerca negli attributi alt delle immagini (poster film)
            images = soup.find_all('img', alt=True)
            for img in images:
                alt_text = img.get('alt', '').strip()
                if alt_text and 5 < len(alt_text) < 80:
                    clean_title = re.sub(r'\s*\(\d{4}\).*$', '', alt_text)
                    clean_title = re.sub(r'\s*(poster|locandina|foto).*$', '', clean_title, flags=re.I)
                    
                    if len(clean_title) > 3:
                        # Cerca link padre dell'immagine
                        parent_link = img.find_parent('a')
                        
                        cinema_info = {'search_url': source_url}
                        if parent_link:
                            cinema_info = self.extract_cinema_info_romatoday(parent_link, soup)
                        
                        films.append({
                            'title': clean_title.strip(),
                            'source': source_url,
                            'film_url': parent_link.get('href', '') if parent_link else '',
                            'cinema_info': cinema_info
                        })
            
        except Exception as e:
            print(f"Error extracting from RomaToday: {e}")
        
        # Rimuovi duplicati
        unique_films = []
        seen_titles = set()
        for film in films:
            if film['title'] not in seen_titles and len(film['title']) > 3:
                seen_titles.add(film['title'])
                unique_films.append(film)
        
        return unique_films[:100]  # Limita a 100 per performance
    
    def extract_cinema_info_romatoday(self, link_element, soup):
        """Estrae informazioni sui cinema da RomaToday"""
        cinema_info = {}
        
        try:
            link_href = link_element.get('href', '')
            link_text = link_element.get_text(strip=True)
            
            # Se il link contiene info su un cinema specifico
            if '/sala/' in link_href:
                # Estrai nome cinema dall'URL
                cinema_match = re.search(r'/sala/([^/]+)', link_href)
                if cinema_match:
                    cinema_name = cinema_match.group(1).replace('-', ' ').title()
                    cinema_info['cinemas'] = [cinema_name]
            
            # Cerca nomi di cinema romani noti nel testo del link
            roma_cinemas = [
                'Troisi', 'Quattro Fontane', 'Barberini', 'Adriano', 'Greenwich', 
                'UCI', 'The Space', 'Giulio Cesare', 'Nuovo Olimpia', 'Casa del Cinema',
                'Palazzo Altemps', 'Farnese', 'Intrastevere', 'Dei Piccoli'
            ]
            
            for cinema in roma_cinemas:
                if cinema.lower() in link_text.lower():
                    cinema_info['cinemas'] = cinema_info.get('cinemas', []) + [cinema]
            
            # URL completo se relativo
            if link_href and not link_href.startswith('http'):
                if link_href.startswith('/'):
                    cinema_info['cinema_url'] = f"https://www.romatoday.it{link_href}"
                else:
                    cinema_info['cinema_url'] = f"https://www.romatoday.it/{link_href}"
            elif link_href:
                cinema_info['cinema_url'] = link_href
            
            # Cerca orari nel contesto circostante
            parent = link_element.parent
            if parent:
                context_text = parent.get_text()
                times = re.findall(r'\b\d{1,2}[:.]\d{2}\b', context_text)
                if times:
                    cinema_info['times'] = times[:5]
            
            cinema_info['search_url'] = 'https://www.romatoday.it/eventi/cinema/'
            
        except Exception as e:
            print(f"Warning: Could not extract cinema info from RomaToday: {e}")
            cinema_info = {'search_url': 'https://www.romatoday.it/eventi/cinema/'}
            
        return cinema_info
    
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
        
        # Rimuovi duplicati mantenendo il match con score più alto
        unique_matches = {}
        for match in matches:
            film_title = match['watchlist_film']['title']
            if film_title not in unique_matches or match['match_score'] > unique_matches[film_title]['match_score']:
                unique_matches[film_title] = match
        
        final_matches = list(unique_matches.values())
        print(f"🎯 Found {len(final_matches)} unique matches")
        return final_matches
    
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
                cinema_film = match['cinema_film']
                source = "RomaToday Cinema" 
                score = match['match_score']
                
                message += f"{i}. 🎞️ <b>{film}</b>\n"
                message += f"   📍 {source}\n"
                message += f"   🎯 Match: {score:.0%}\n"
                
                # Aggiungi info sui cinema se disponibili
                cinema_info = cinema_film.get('cinema_info', {})
                
                if cinema_info.get('cinemas'):
                    cinemas_list = ', '.join(cinema_info['cinemas'][:3])  # Max 3 cinema
                    message += f"   🏛️ Cinema: {cinemas_list}\n"
                
                if cinema_info.get('times'):
                    times_list = ', '.join(cinema_info['times'][:3])  # Max 3 orari
                    message += f"   🕐 Orari: {times_list}\n"
                
                # Link specifico al cinema se disponibile (RomaToday)
                if cinema_info.get('cinema_url'):
                    message += f"   🎬 <a href='{cinema_info['cinema_url']}'>Programmazione dettagliata</a>\n"
                
                # Link per cercare su Google (backup)
                search_query = film.replace(' ', '+')
                google_search = f"https://www.google.com/search?q={search_query}+cinema+Roma+programmazione+2025"
                message += f"   🔍 <a href='{google_search}'>Cerca altri cinema</a>\n"
                
                # Link RomaToday generale per il film
                romatoday_search = f"https://www.romatoday.it/eventi/cinema/"
                message += f"   📰 <a href='{romatoday_search}'>Tutti i cinema su RomaToday</a>\n"
                
                message += "\n"
                
            message += f"🗓️ Controllato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}\n"
            message += f"💡 <i>Clicca i link per dettagli su cinema e orari</i>"
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
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
        print("🎬 RISULTATI CONTROLLO CINEMA ROMA (RomaToday)")
        print("="*50)
        
        if not matches:
            print("❌ Nessun film della watchlist trovato in programmazione")
        else:
            print(f"✅ Trovati {len(matches)} film in programmazione:")
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                cinema_film = match['cinema_film']
                source = "RomaToday Cinema"
                score = match['match_score']
                
                print(f"\n{i}. {film}")
                print(f"   Fonte: {source}")
                print(f"   Accuratezza match: {score:.0%}")
                
                # Mostra info sui cinema se disponibili
                cinema_info = cinema_film.get('cinema_info', {})
                
                if cinema_info.get('cinemas'):
                    cinemas_list = ', '.join(cinema_info['cinemas'][:3])
                    print(f"   Cinema: {cinemas_list}")
                
                if cinema_info.get('times'):
                    times_list = ', '.join(cinema_info['times'][:3])
                    print(f"   Orari: {times_list}")
                
                if cinema_info.get('cinema_url'):
                    print(f"   URL Programmazione: {cinema_info['cinema_url']}")
                
                print(f"   Ricerca Google: https://www.google.com/search?q={film.replace(' ', '+')}+cinema+Roma")
                
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
     
