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
                film_titles = self.extract_multiple_titles_from_container(container)
                if film_titles:
                    films.append(film_titles)
                    print(f"📽️ Found: {film_titles}")
            
            # Pattern 2: Cerca nelle immagini con alt text
            if len(films) < 5:  # Se non trova abbastanza film, usa il metodo classico
                print("🔄 Fallback to image alt text method...")
                for img in soup.find_all('img', alt=True):
                    alt_text = img.get('alt', '')
                    if alt_text and alt_text != 'Poster' and len(alt_text) > 3:
                        # Cerca titoli multipli nel context dell'immagine
                        film_titles = self.extract_titles_from_context(img, alt_text)
                        if film_titles and film_titles not in films:
                            films.append(film_titles)
            
            # Pattern 3: Cerca in base alla struttura HTML tipica di Letterboxd
            print("🔍 Looking for Letterboxd-specific structures...")
            title_links = soup.find_all('a', href=re.compile(r'/film/'))
            
            for link in title_links:
                if link.get_text(strip=True):
                    film_titles = self.extract_titles_from_link_context(link)
                    if film_titles and film_titles not in films:
                        films.append(film_titles)
            
            print(f"✅ Found {len(films)} films via enhanced web scraping")
            print(f"📋 Sample films: {films[:3]}")
            
            return films[:30]  # Limita per performance
            
        except Exception as e:
            print(f"❌ Error scraping watchlist: {e}")
            return []
    
    def extract_multiple_titles_from_container(self, container):
        """Estrae titoli multipli da un container di film"""
        try:
            # Cerca il titolo principale
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
            
            # 3. Cerca sottotitoli/titoli originali
            # Cerca elementi con testo in corsivo o classi che indicano titoli alternativi
            subtitle_elements = container.find_all(['em', 'i', 'span'], string=re.compile(r'^[A-Za-z0-9À-ÿ\s\-:,\.\'\"]+$'))
            
            for element in subtitle_elements:
                text = element.get_text(strip=True)
                if text and len(text) > 3 and text not in [main_title] + alt_titles:
                    # Filtra testi che sembrano titoli di film
                    if not any(word in text.lower() for word in ['directed', 'starring', 'runtime', 'year', 'genre']):
                        alt_titles.append(text)
            
            # 4. Cerca negli elementi h1, h2, h3 nel container
            title_elements = container.find_all(['h1', 'h2', 'h3', 'h4'])
            for element in title_elements:
                text = element.get_text(strip=True)
                if text and len(text) > 3 and text not in [main_title] + alt_titles:
                    alt_titles.append(text)
            
            # Pulisci e filtra i titoli
            if main_title:
                main_title = self.clean_title(main_title)
                clean_alt_titles = [self.clean_title(title) for title in alt_titles if self.clean_title(title)]
                
                # Rimuovi duplicati e titoli troppo simili
                final_alt_titles = []
                for alt_title in clean_alt_titles:
                    if len(alt_title) > 3 and alt_title != main_title:
                        # Controlla che non sia troppo simile al titolo principale
                        similarity = difflib.SequenceMatcher(None, main_title.lower(), alt_title.lower()).ratio()
                        if similarity < 0.9:  # Se è diverso abbastanza
                            final_alt_titles.append(alt_title)
                
                result = {
                    'title': main_title,
                    'original_title': main_title,
                    'alternative_titles': final_alt_titles[:3],  # Max 3 titoli alternativi
                    'url': watchlist_url
                }
                
                return result
                
        except Exception as e:
            print(f"Warning: Error extracting titles from container: {e}")
        
        return None
    
    def extract_titles_from_context(self, img, alt_text):
        """Estrae titoli dal contesto di un'immagine"""
        try:
            main_title = self.clean_title(alt_text)
            if not main_title or len(main_title) < 3:
                return None
            
            # Cerca nel parent element per sottotitoli
            alt_titles = []
            parent = img.parent
            if parent:
                # Cerca testo nelle vicinanze che potrebbe essere un titolo alternativo
                for sibling in parent.find_all(string=True):
                    text = sibling.strip()
                    if text and len(text) > 3 and text != main_title:
                        clean_text = self.clean_title(text)
                        if clean_text and clean_text != main_title:
                            alt_titles.append(clean_text)
            
            return {
                'title': main_title,
                'original_title': main_title,
                'alternative_titles': alt_titles[:2],
                'url': watchlist_url
            }
            
        except Exception as e:
            print(f"Warning: Error extracting from context: {e}")
            return None
    
    def extract_titles_from_link_context(self, link):
        """Estrae titoli dal contesto di un link"""
        try:
            main_title = self.clean_title(link.get_text(strip=True))
            if not main_title or len(main_title) < 3:
                return None
            
            # Cerca nel data attributes del link o parent
            alt_titles = []
            
            # Cerca negli attributi data-*
            for attr_name, attr_value in link.attrs.items():
                if attr_name.startswith('data-') and isinstance(attr_value, str):
                    potential_title = self.clean_title(attr_value)
                    if potential_title and potential_title != main_title and len(potential_title) > 3:
                        alt_titles.append(potential_title)
            
            return {
                'title': main_title,
                'original_title': main_title,
                'alternative_titles': alt_titles[:2],
                'url': watchlist_url
            }
            
        except Exception as e:
            print(f"Warning: Error extracting from link context: {e}")
            return None
    
    def clean_title(self, title):
        """Pulisce un titolo rimuovendo info extra"""
        if not title:
            return ""
            
        # Rimuovi anno
        clean = re.sub(r'\s+\(\d{4}\).*$', '', title)
        # Rimuovi info extra dopo trattini
        clean = re.sub(r'\s*[–—-]\s*(directed|starring|runtime).*$', '', clean, flags=re.I)
        # Rimuovi spazi multipli
        clean = re.sub(r'\s+', ' ', clean)
        
        return clean.strip()
    
    def get_roma_cinema_films(self):
        """Scrapa i film in programmazione a Roma da ComingSoon.it"""
        all_films = []
        
        # ComingSoon.it - fonte principale
        cinema_sources = [
            'https://www.comingsoon.it/cinema/roma/',
            'https://www.comingsoon.it/cinema/roma/versione-originale/',  # Se esiste
        ]
        
        for url in cinema_sources:
            try:
                print(f"📡 Scraping {url}...")
                
                # Headers per ComingSoon.it
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://www.comingsoon.it/',
                }
                
                response = requests.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                films_from_source = self.extract_comingsoon_films(soup, url)
                
                print(f"✅ Found {len(films_from_source)} films from {url}")
                all_films.extend(films_from_source)
                
            except requests.exceptions.RequestException as e:
                print(f"❌ Network error scraping {url}: {e}")
                continue
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
        
        final_films = unique_films[:150]  # ComingSoon ha molti film
        print(f"🎬 Total unique films from Roma (ComingSoon): {len(final_films)}")
        
        # Mostra alcuni film trovati per debug
        if final_films:
            sample_titles = [f['title'] for f in final_films[:20]]
            print(f"📋 Sample Roma films: {sample_titles}")
        else:
            print("⚠️ No films found - trying fallback extraction methods...")
            # Se nessun film trovato, prova metodi più generici
            all_films = self.extract_generic_films_comingsoon(soup, cinema_sources[0])
            if all_films:
                print(f"📋 Fallback found {len(all_films)} films")
                return all_films[:50]
        
        return final_films
    
    def extract_comingsoon_films(self, soup, source_url):
        """Estrae film specificamente da ComingSoon.it"""
        films = []
        
        try:
            # Pattern 1: Cerca link ai film (ComingSoon ha structure tipica)
            film_links = soup.find_all('a', href=re.compile(r'(/film/|/cinema/)', re.I))
            
            for link in film_links:
                title_text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if title_text and len(title_text) > 3 and len(title_text) < 100:
                    # Evita link di navigazione
                    skip_words = ['home', 'contatti', 'cinema', 'orari', 'prezzi', 'info', 'roma', 'tutti i film']
                    if not any(word in title_text.lower() for word in skip_words):
                        # Pulisci il titolo
                        clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title_text)
                        clean_title = re.sub(r'\s*-\s*.*$', '', clean_title)
                        clean_title = re.sub(r'\s*(al cinema|cinema|trailer|recensione).*$', '', clean_title, flags=re.I)
                        
                        if len(clean_title) > 3:
                            # Crea URL completo se necessario
                            film_url = href if href.startswith('http') else f"https://www.comingsoon.it{href}"
                            
                            films.append({
                                'title': clean_title.strip(),
                                'source': source_url,
                                'cinema_info': {
                                    'search_url': source_url,
                                    'film_url': film_url,
                                    'source_name': 'ComingSoon'
                                }
                            })
            
            # Pattern 2: Cerca in elementi specifici per film
            film_containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'(film|movie|title)', re.I))
            
            for container in film_containers:
                title_text = container.get_text(strip=True)
                if title_text and 5 < len(title_text) < 80:
                    clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title_text)
                    clean_title = re.sub(r'\s*-\s*.*$', '', clean_title)
                    
                    if len(clean_title) > 3:
                        films.append({
                            'title': clean_title.strip(),
                            'source': source_url,
                            'cinema_info': {
                                'search_url': source_url,
                                'source_name': 'ComingSoon'
                            }
                        })
            
            # Pattern 3: Cerca nei tag title e h1-h3
            title_elements = soup.find_all(['h1', 'h2', 'h3', 'h4'], string=re.compile(r'^[A-Za-z0-9À-ÿ\s\-:\.]+$'))
            
            for element in title_elements:
                title_text = element.get_text(strip=True)
                if title_text and 5 < len(title_text) < 100:
                    skip_words = ['programmazione', 'cinema', 'roma', 'orari', 'coming soon', 'film', 'oggi']
                    if not any(word in title_text.lower() for word in skip_words):
                        clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title_text)
                        
                        if len(clean_title) > 3:
                            films.append({
                                'title': clean_title.strip(),
                                'source': source_url,
                                'cinema_info': {
                                    'search_url': source_url,
                                    'source_name': 'ComingSoon'
                                }
                            })
                            
        except Exception as e:
            print(f"Error extracting from ComingSoon: {e}")
        
        return films
    
    def extract_generic_films_comingsoon(self, soup, source_url):
        """Metodo fallback per estrarre film da ComingSoon"""
        films = []
        
        try:
            # Cerca tutti i link che potrebbero essere film
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                title_text = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Filtri più permissivi per fallback
                if title_text and 4 < len(title_text) < 120:
                    # Lista più specifica di parole da evitare
                    skip_words = ['home', 'contatti', 'privacy', 'cookie', 'login', 'registrati', 'newsletter', 'pubblicità']
                    if not any(word in title_text.lower() for word in skip_words):
                        clean_title = re.sub(r'\s*\(\d{4}\).*$', '', title_text)
                        clean_title = re.sub(r'\s*[–—]\s*.*$', '', clean_title)  # Remove em/en dashes and everything after
                        
                        if len(clean_title) > 3:
                            films.append({
                                'title': clean_title.strip(),
                                'source': source_url,
                                'cinema_info': {
                                    'search_url': source_url,
                                    'source_name': 'ComingSoon (Fallback)'
                                }
                            })
                            
  