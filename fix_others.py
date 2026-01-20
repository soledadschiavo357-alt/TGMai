import re
import os

def fix_file(filepath):
    print(f"Fixing {filepath}...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. Fix ../index.html -> /
        content = content.replace('../index.html', '/')
        content = content.replace('/index.html', '/')
        
        # 2. Fix specific Clean URL violations
        # href=".../xxx.html" -> href=".../xxx"
        # Be careful with external links
        
        def replace_href(m):
            url = m.group(1)
            if url.startswith('http') and 'tgmai.top' not in url:
                return f'href="{url}"'
            
            # Skip if it is a file download or image? No, mostly .html
            if url.endswith('.html'):
                return f'href="{url[:-5]}"'
            return f'href="{url}"'
        
        content = re.sub(r'href="([^"]+\.html)"', replace_href, content)
        
        # 3. Specific fixes for known paths if regex missed (e.g. fragments)
        # ../index.html#xxx -> /#xxx (handled by step 1 replace)
        
        # 4. Fix specific links mentioned in audit
        content = content.replace('/sitemap.html', '/sitemap')
        content = content.replace('/about.html', '/about')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")
        
    except Exception as e:
        print(f"Error fixing {filepath}: {e}")

if __name__ == "__main__":
    if os.path.exists('blog/index.html'):
        fix_file('blog/index.html')
    if os.path.exists('sitemap.html'):
        fix_file('sitemap.html')
