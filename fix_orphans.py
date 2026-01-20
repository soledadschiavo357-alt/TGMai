from bs4 import BeautifulSoup
import os

def fix_index_links():
    filepath = 'index.html'
    if not os.path.exists(filepath):
        print("index.html not found")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    soup = BeautifulSoup(content, 'html.parser')
    
    changed = False
    for a in soup.find_all('a'):
        href = a.get('href')
        text = a.get_text(strip=True)
        # print(f"Link: {href} Text: {text}")
        
        if href == '#products':
            if '立即购买' in text or '立即选号' in text:
                print(f"Updating CTA button '{text}' to /go/buy")
                a['href'] = '/go/buy'
                changed = True
    
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        print("index.html updated")
    else:
        print("No CTA button found")

if __name__ == "__main__":
    fix_index_links()
