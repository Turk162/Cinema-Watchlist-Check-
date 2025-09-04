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
                
                # Cerca strutture più dettagliate per i film
                film_containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'film|movie|cinema', re.I))
                
                for container in film_containers:
                    # Cerca titoli e link nei container
                    title_links = container.find_all('a', href=re.compile(r'/film/'))
                    
                    for link in title_links:
                        if link.text.strip() and len(link.text.strip()) > 2:
                            title = link.text.strip()
                            clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title)
                            
                            # Cerca informazioni sui cinema vicino al titolo
                            cinema_info = self.extract_cinema_info(container, url)
                            
                            if clean_title and not any(f['title'] == clean_title for f in all_films):
                                film_data = {
                                    'title': clean_title.strip(),
                                    'source': url,
                                    'film_url': link.get('href', ''),
                                    'cinema_info': cinema_info
                                }
                                all_films.append(film_data)
                
                # Fallback: cerca tutti i link ai film
                if not all_films or len([f for f in all_films if f['source'] == url]) < 5:
                    film_links = soup.find_all('a', href=re.compile(r'/film/'))
                    
                    for link in film_links:
                        if link.text.strip() and len(link.text.strip()) > 2:
                            title = link.text.strip()
                            clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title)
                            
                            if clean_title and not any(f['title'] == clean_title for f in all_films):
                                film_data = {
                                    'title': clean_title.strip(),
                                    'source': url,
                                    'film_url': link.get('href', ''),
                                    'cinema_info': {'search_url': url}
                                }
                                all_films.append(film_data)
                            
                print(f"✅ Found {len([f for f in all_films if f['source'] == url])} films from this source")
                
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
                continue
                
        print(f"🎬 Total films in Roma cinemas: {len(all_films)}")
        return all_films
    
    def extract_cinema_info(self, container, source_url):
        """Estrae informazioni sui cinema da un container HTML"""
        cinema_info = {'search_url': source_url}
        
        try:
            # Cerca nomi di cinema noti
            cinema_patterns = [
                r'UCI\s+\w+', r'The\s+Space\s+\w+', r'Cinema\s+\w+', r'Multisala\s+\w+',
                r'Barberini', r'Adriano', r'Greenwich', r'Troisi', r'Giulio Cesare',
                r'Nuovo Olimpia', r'Casa del Cinema', r'Palazzo Altemps'
            ]
            
            text_content = container.get_text(' ', strip=True)
            
            for pattern in cinema_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    cinema_info['cinemas'] = list(set(matches))
                    break
            
            # Cerca orari
            time_pattern = r'\b\d{1,2}[:.]?\d{0,2}\b'
            times = re.findall(time_pattern, text_content)
            if times:
                cinema_info['times'] = times[:5]  # Max 5 orari
            
            # Cerca link specifici ai cinema
            cinema_links = container.find_all('a', href=re.compile(r'cinema|multisala|theatre', re.I))
            if cinema_links:
                cinema_info['cinema_links'] = [link.get('href') for link in cinema_links[:3]]
                
        except Exception as e:
            print(f"Warning: Could not extract cinema info: {e}")
            
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
                source = "Roma (V.O.)" if "versione-originale" in cinema_film['source'] else "Roma"
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
                
                # Link per cercare programmazioni dettagliate
                search_query = film.replace(' ', '+')
                search_url = f"https://www.google.com/search?q={search_query}+cinema+Roma+programmazione"
                message += f"   🔍 <a href='{search_url}'>Cerca programmazione</a>\n"
                
                # Link diretto se disponibile
                if cinema_film.get('film_url') and cinema_film['film_url'].startswith('http'):
                    message += f"   🎬 <a href='{cinema_film['film_url']}'>Dettagli film</a>\n"
                elif cinema_film.get('film_url'):
                    full_url = f"https://www.mymovies.it{cinema_film['film_url']}"
                    message += f"   🎬 <a href='{full_url}'>Dettagli film</a>\n"
                
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
        print("🎬 RISULTATI CONTROLLO CINEMA ROMA")
        print("="*50)
        
        if not matches:
            print("❌ Nessun film della watchlist trovato in programmazione")
        else:
            print(f"✅ Trovati {len(matches)} film in programmazione:")
            for i, match in enumerate(matches, 1):
                film = match['watchlist_film']['title']
                cinema_film = match['cinema_film']
                source = "Roma (V.O.)" if "versione-originale" in cinema_film['source'] else "Roma"
                score = match['match_score']
                
                print(f"\n{i}. {film}")
                print(f"   Programmato a: {source}")
                print(f"   Accuratezza match: {score:.0%}")
                
                # Mostra info sui cinema se disponibili
                cinema_info = cinema_film.get('cinema_info', {})
                
                if cinema_info.get('cinemas'):
                    cinemas_list = ', '.join(cinema_info['cinemas'][:3])
                    print(f"   Cinema: {cinemas_list}")
                
                if cinema_info.get('times'):
                    times_list = ', '.join(cinema_info['times'][:3])
                    print(f"   Orari: {times_list}")
                
                if cinema_film.get('film_url'):
                    if cinema_film['film_url'].startswith('http'):
                        print(f"   URL: {cinema_film['film_url']}")
                    else:
                        print(f"   URL: https://www.mymovies.it{cinema_film['film_url']}")
                
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
