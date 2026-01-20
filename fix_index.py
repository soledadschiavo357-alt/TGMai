import re

def fix_index_html():
    filepath = 'index.html'
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. Fix index.html references
        # href="index.html" -> href="/"
        content = re.sub(r'href=["\']index\.html["\']', 'href="/"', content)
        # href="../index.html" -> href="/"
        content = re.sub(r'href=["\']\.\./index\.html["\']', 'href="/"', content)
        # href="./index.html" -> href="/"
        content = re.sub(r'href=["\']\./index\.html["\']', 'href="/"', content)
        
        # 2. Fix other .html references (Clean URL)
        # We need to be careful not to break external links or resource links (like .css, .js, .png)
        # We target href="... .html"
        
        def replace_html_ext(match):
            url = match.group(1)
            # Skip if it is a full URL (http/https) unless it is our domain (which is rare in relative links)
            # But the requirement says "links ending with .html"
            
            if url.startswith('http') and 'tgmai.top' not in url:
                return f'href="{url}"'
            
            # Remove .html
            new_url = url.replace('.html', '')
            
            # Special case: /index or index -> /
            if new_url.endswith('/index'):
                new_url = new_url[:-5]
            elif new_url == 'index':
                new_url = '/'
                
            return f'href="{new_url}"'

        # Regex for href="..." where content ends in .html
        # We use a negative lookbehind/lookahead or just simple matching?
        # Let's match href="([^"]+\.html)"
        content = re.sub(r'href="([^"]+\.html)"', replace_html_ext, content)
        
        # 3. Fix specific relative paths like "../index.html#pro-global" which might have been caught by #1 if we are not careful
        # But #1 handled exact matches.
        # Now handle "../index.html#fragment" -> "/#fragment"
        content = re.sub(r'href=["\']\.\./index\.html(#.*?)["\']', r'href="/\1"', content)
        content = re.sub(r'href=["\']index\.html(#.*?)["\']', r'href="/\1"', content)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully updated {filepath}")
        
    except Exception as e:
        print(f"Error updating {filepath}: {e}")

if __name__ == "__main__":
    fix_index_html()
