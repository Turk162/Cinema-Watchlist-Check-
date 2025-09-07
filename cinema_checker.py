#!/usr/bin/env python3
"""
Script debug semplificato per testare lo scraping di ComingSoon.it
Cerca solo due film specifici: "Warfare" e "I roses"
"""
import requests
from bs4 import BeautifulSoup
import difflib

def debug_comingsoon_scraping():
    """Debug dello scraping di ComingSoon.it"""
    
    # Film che stiamo cercando
    target_films = ["Warfare", "I roses"]
    
    print("=== DEBUG COMINGSOON SCRAPING ===")
    print(f"Cerco questi film: {target_films}")
    print()
    
    url = 'https://www.comingsoon.it/cinema/roma/'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
        'Referer': 'https://www.comingsoon.it/',
    }
    
    try:
        print(f"Scarico: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.content)} bytes")
        print()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # METODO 1: Cerca con la struttura HTML specifica
        print("=== METODO 1: Struttura HTML specifica ===")
        film_containers = soup.find_all('div', class_='header-scheda streaming min no-bg container-fluid pbm')
        print(f"Container trovati: {len(film_containers)}")
        
        films_method1 = []
        for i, container in enumerate(film_containers):
            title_link = container.find('a', class_='tit_olo h1')
            if title_link:
                title = title_link.get_text(strip=True)
                films_method1.append(title)
                print(f"  {i+1}. {title}")
        
        print(f"Totale film metodo 1: {len(films_method1)}")
        print()
        
        # METODO 2: Cerca tutti gli H1, H2, H3
        print("=== METODO 2: Tutti gli heading ===")
        films_method2 = []
        for tag in ['h1', 'h2', 'h3']:
            headings = soup.find_all(tag)
            print(f"Tag {tag.upper()}: {len(headings)} trovati")
            for heading in headings[:10]:  # Mostra solo primi 10
                text = heading.get_text(strip=True)
                if text and 3 < len(text) < 100:
                    films_method2.append(text)
                    print(f"  - {text}")
        
        print(f"Totale film metodo 2: {len(films_method2)}")
        print()
        
        # METODO 3: Cerca tutti i link con "/film/" 
        print("=== METODO 3: Link con /film/ ===")
        film_links = soup.find_all('a', href=lambda href: href and '/film/' in href)
        print(f"Link /film/ trovati: {len(film_links)}")
        
        films_method3 = []
        for link in film_links[:20]:  # Mostra solo primi 20
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text and len(text) > 3:
                films_method3.append(text)
                print(f"  - {text} -> {href}")
        
        print(f"Totale film metodo 3: {len(films_method3)}")
        print()
        
        # METODO 4: Cerca nelle immagini con alt text
        print("=== METODO 4: Immagini con alt text ===")
        images = soup.find_all('img', alt=True)
        print(f"Immagini con alt trovate: {len(images)}")
        
        films_method4 = []
        for img in images:
            alt_text = img.get('alt', '').strip()
            if alt_text and len(alt_text) > 3 and alt_text != 'Poster':
                films_method4.append(alt_text)
                print(f"  - {alt_text}")
        
        print(f"Totale film metodo 4: {len(films_method4[:20])}")
        print()
        
        # Combina tutti i film trovati
        all_films = list(set(films_method1 + films_method2 + films_method3 + films_method4))
        print(f"=== TOTALE FILM UNICI TROVATI: {len(all_films)} ===")
        
        # Ora cerca i nostri film target
        print("\n=== RICERCA FILM TARGET ===")
        for target in target_films:
            print(f"\nCerco: '{target}'")
            
            # Cerca match esatti
            exact_matches = [film for film in all_films if target.lower() in film.lower()]
            if exact_matches:
                print(f"  MATCH ESATTI:")
                for match in exact_matches:
                    print(f"    - {match}")
            
            # Cerca match simili
            similar_matches = []
            for film in all_films:
                similarity = difflib.SequenceMatcher(None, target.lower(), film.lower()).ratio()
                if similarity > 0.5:  # Soglia bassa per vedere tutto
                    similar_matches.append((film, similarity))
            
            if similar_matches:
                print(f"  MATCH SIMILI (>50%):")
                for film, score in sorted(similar_matches, key=lambda x: x[1], reverse=True)[:5]:
                    print(f"    - {film} ({score:.0%})")
            
            if not exact_matches and not similar_matches:
                print(f"  NESSUN MATCH trovato per '{target}'")
        
        print("\n=== SAMPLE DI TUTTI I FILM TROVATI ===")
        for i, film in enumerate(sorted(all_films)[:30]):
            print(f"{i+1:2d}. {film}")
        
        if len(all_films) > 30:
            print(f"... e altri {len(all_films) - 30} film")
            
    except Exception as e:
        print(f"ERRORE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_comingsoon_scraping()
