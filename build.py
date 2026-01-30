import os
import re
import glob
import json
import random
from datetime import datetime
from bs4 import BeautifulSoup, Comment

# ================= Configuration =================
DOMAIN = "https://tgmai.top"
BLOG_DIR = "blog"
INDEX_FILE = "index.html"
BLOG_INDEX_FILE = os.path.join(BLOG_DIR, "index.html")
TEMPLATE_FILE = "layout_template.html"

# Colors and Categories Configuration
CATEGORY_CONFIG = {
    'guide': {
        'icon': 'fa-book',
        'color': 'blue',
        'bg_gradient': 'from-blue-900/20 to-slate-900',
        'icon_color': 'text-blue-500/30',
        'label': '使用教程',
        'label_bg': 'bg-blue-600'
    },
    'security': {
        'icon': 'fa-shield-halved',
        'color': 'green',
        'bg_gradient': 'from-green-900/20 to-slate-900',
        'icon_color': 'text-green-500/30',
        'label': '安全指南',
        'label_bg': 'bg-green-600'
    },
    'fault': {
        'icon': 'fa-circle-exclamation',
        'color': 'red',
        'bg_gradient': 'from-red-900/20 to-slate-900',
        'icon_color': 'text-red-500/30',
        'label': '故障排查',
        'label_bg': 'bg-red-600'
    },
    'news': {
        'icon': 'fa-newspaper',
        'color': 'cyan',
        'bg_gradient': 'from-cyan-900/20 to-slate-900',
        'icon_color': 'text-cyan-500/30',
        'label': '最新资讯',
        'label_bg': 'bg-cyan-600'
    },
    'default': {
        'icon': 'fa-pen-to-square',
        'color': 'slate',
        'bg_gradient': 'from-slate-800 to-slate-900',
        'icon_color': 'text-slate-500/30',
        'label': '精选文章',
        'label_bg': 'bg-slate-600'
    }
}

CATEGORY_MAPPING = {
    'guide': 'guide', 'tutorial': 'guide', 'usage': 'guide', 'pack': 'guide',
    'security': 'security', 'banned': 'security', 'passkey': 'security', '2fa': 'security',
    'issue': 'fault', 'login': 'fault', 'code': 'fault', 'verification': 'fault',
    'news': 'news', 'update': 'news'
}

def get_category_from_filename(filename):
    name = filename.lower()
    for keyword, category in CATEGORY_MAPPING.items():
        if keyword in name:
            return category
    return 'default'

def clean_url(url):
    """
    Convert URL to root-relative and remove .html suffix.
    """
    if not url:
        return url
        
    # Skip non-http protocols (javascript, tel, mailto, tg, etc)
    if any(url.startswith(p) for p in ['javascript:', 'mailto:', 'tel:', 'tg:', 'data:']):
        return url

    # External links - keep as is, but if it points to our domain, clean it
    if url.startswith('http'):
        if DOMAIN in url:
            url = url.replace(DOMAIN, '')
        else:
            return url

    # Remove .html
    if url.endswith('.html'):
        url = url[:-5]
    
    # Handle index
    if url.endswith('/index'):
        url = url[:-6]
    if url == '/index':
        url = '/'
    
    # Handle relative paths ../
    # Only replace if it's a local path
    if '../' in url and not url.startswith('http'):
        # This is tricky without knowing base, but we assume we want absolute paths for everything
        # If we are in /blog/, ../index.html means /index.html -> /
        url = url.replace('../', '/') 
    
    return url

def resolve_anchor_to_root(url):
    """
    Clean URL and ensure it is an absolute path from root.
    """
    url = clean_url(url)
    if not url:
        return url
        
    if any(url.startswith(p) for p in ['http', 'mailto:', 'tel:', 'tg:', 'javascript:', 'data:']):
        return url

    # If it's an anchor, prepend /
    if url.startswith('#'):
        return '/' + url
        
    # If it's a relative path (not starting with /), prepend /
    if not url.startswith('/'):
        return '/' + url
        
    return url

def fix_relative_links_in_post(soup):
    """
    Fix relative links in blog posts (e.g. href="foo.html" -> href="/blog/foo")
    """
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href or href.startswith(('http', '/', '#', 'mailto:', 'tel:', 'tg:')):
            continue
        
        # Relative link found
        if href.endswith('.html'):
            clean = href[:-5]
            a['href'] = f"/blog/{clean}"
        elif not '.' in href: 
            # e.g. href="tg-account-banned"
            a['href'] = f"/blog/{href}"
        # Leave assets (with extension) alone unless we want to enforce /assets/ path?
        # Assuming images are absolute or correctly handled.

def get_layout_components():
    """Extract Header (Nav), Footer, and Favicon assets from index.html"""
    if not os.path.exists(INDEX_FILE):
        print(f"Error: {INDEX_FILE} not found.")
        return None, None, None

    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    nav = soup.find('nav')
    footer = soup.find('footer')
    
    # Extract Brand Assets (Favicons)
    favicons = []
    # <link rel="icon">, <link rel="shortcut icon">, <link rel="apple-touch-icon">
    for tag in soup.head.find_all('link'):
        rel = tag.get('rel', [])
        if isinstance(rel, list):
            rel_set = set(rel)
        else:
            rel_set = {rel}
            
        if rel_set & {'icon', 'shortcut', 'apple-touch-icon'}:
            # Clean path to ensure absolute root-relative
            if tag.get('href'):
                href = tag['href']
                if not href.startswith('http') and not href.startswith('/'):
                    # relative path like "assets/logo.png" -> "/assets/logo.png"
                    # Assuming index.html is at root
                    tag['href'] = '/' + href
                elif href.startswith('http') and DOMAIN in href:
                    tag['href'] = href.replace(DOMAIN, '')
                
                favicons.append(tag)
    
    return nav, footer, favicons

def generate_recommendations(posts, current_filename):
    """Generate HTML for recommended reading (random 2 posts excluding current)"""
    others = [p for p in posts if p['filename'] != current_filename]
    if not others:
        return ""
    
    recs = random.sample(others, min(4, len(others)))
    
    html = '<div class="mt-8 recommendation-section">\n'
    html += '  <h2 class="text-sm font-bold text-slate-300 mb-3">相关文章</h2>\n'
    html += '  <div class="grid md:grid-cols-2 gap-4">\n'
    
    for post in recs:
        cat = post['category_obj']
        html += f'''    <a href="{post['url']}" class="block rounded-xl bg-slate-800 border border-white/10 p-4 hover:border-[#24A1DE] transition">
      <div class="font-semibold text-white">{post['title']}</div>
      <div class="text-xs text-slate-400 mt-1">{cat['label']}</div>
    </a>\n'''
    
    html += '  </div>\n</div>'
    return html

def reconstruct_head(soup, metadata, favicons):
    """
    Phase 2: Head Reconstruction Engine
    Groups:
    A: Basic SEO (Title, Desc, Keywords, Canonical)
    B: Indexing & Geo (Robots, Lang, Hreflang)
    C: Schema (JSON-LD)
    D: Resources (Favicon, CSS, JS)
    """
    head = soup.head
    if not head:
        head = soup.new_tag('head')
        soup.html.insert(0, head)
    
    # 1. Preserve scripts and styles (Resources)
    # We'll collect them and re-insert them at the end (Group D)
    # Also preserve charset and viewport
    preserved_resources = []
    charset = soup.new_tag('meta', charset='utf-8')
    viewport = soup.new_tag('meta', attrs={'name': 'viewport', 'content': 'width=device-width, initial-scale=1'})
    
    for tag in head.find_all(['link', 'script', 'style']):
        # Filter out canonical, hreflang which we will regenerate
        if tag.name == 'link' and tag.get('rel') in [['canonical'], ['alternate']]:
            continue
        # Filter out old schema
        if tag.name == 'script' and tag.get('type') == 'application/ld+json':
            continue
        # Filter out old favicons (we will sync from index)
        if tag.name == 'link':
            rel = tag.get('rel', [])
            if isinstance(rel, str): rel = [rel]
            if set(rel) & {'icon', 'shortcut', 'apple-touch-icon'}:
                continue
                
        preserved_resources.append(tag)
        
    # Clear head
    head.clear()
    
    # Helper to append with newline
    def append_tag(tag):
        head.append(tag)
        head.append('\n')

    # --- Start Injection ---
    
    # Group A: Basic Meta
    append_tag(charset)
    append_tag(viewport)
    
    # Title
    title_tag = soup.new_tag('title')
    title_tag.string = f"{metadata['title']} - TGMai Blog"
    append_tag(title_tag)
    head.append('\n')

    # Group B: SEO Core
    # Desc
    desc_tag = soup.new_tag('meta', attrs={'name': 'description', 'content': metadata['description']})
    append_tag(desc_tag)
    
    # Keywords
    if metadata.get('keywords'):
        kw_tag = soup.new_tag('meta', attrs={'name': 'keywords', 'content': metadata['keywords']})
        append_tag(kw_tag)
        
    # Canonical
    canon_tag = soup.new_tag('link', rel='canonical', href=metadata['canonical_url'])
    append_tag(canon_tag)
    head.append('\n')
    
    # Group C: Indexing & Geo
    robots_tag = soup.new_tag('meta', attrs={'name': 'robots', 'content': 'index, follow'})
    append_tag(robots_tag)
    
    # Content-Language (Optional but good)
    # lang_tag = soup.new_tag('meta', attrs={'http-equiv': 'content-language', 'content': 'zh-CN'})
    # append_tag(lang_tag)
    
    # Hreflang Matrix
    href_zh = soup.new_tag('link', rel='alternate', hreflang='zh', href=metadata['canonical_url'])
    href_def = soup.new_tag('link', rel='alternate', hreflang='x-default', href=metadata['canonical_url'])
    append_tag(href_zh)
    append_tag(href_def)
    head.append('\n')
    
    # Group D: Branding & Resources
    # Favicons (Synced from Index)
    if favicons:
        for icon in favicons:
            # Create a copy to insert
            import copy
            new_icon = copy.copy(icon)
            append_tag(new_icon)
    
    # Preserved Resources (CSS, JS)
    for tag in preserved_resources:
        append_tag(tag)
    head.append('\n')
    
    # Group E: Schema
    # BlogPosting
    schema_blog = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": metadata['title'],
        "description": metadata['description'],
        "datePublished": metadata['date'],
        "dateModified": metadata.get('date_modified', datetime.now().strftime("%Y-%m-%d")),
        "author": {"@type": "Organization", "name": "TGMai"},
        "publisher": {
            "@type": "Organization", 
            "name": "TGMai.top", 
            "logo": {"@type": "ImageObject", "url": "/assets/logo.svg"}
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": metadata['canonical_url']}
    }
    if metadata.get('image'):
        schema_blog['image'] = metadata['image']
        
    script_blog = soup.new_tag('script', type="application/ld+json")
    script_blog.string = json.dumps(schema_blog, ensure_ascii=False, indent=2)
    append_tag(script_blog)
    
    # BreadcrumbList
    schema_bread = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": f"{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": "博客", "item": f"{DOMAIN}/blog/"},
            {"@type": "ListItem", "position": 3, "name": metadata['title'], "item": metadata['canonical_url']}
        ]
    }
    script_bread = soup.new_tag('script', type="application/ld+json")
    script_bread.string = json.dumps(schema_bread, ensure_ascii=False, indent=2)
    append_tag(script_bread)

def generate_breadcrumb_html(title):
    """Generate Visual Breadcrumb HTML"""
    return f"""
    <nav aria-label="Breadcrumb" class="relative z-10 overflow-x-auto whitespace-nowrap mb-6 text-sm">
      <ol class="flex items-center gap-2 text-slate-400">
       <li>
        <a class="hover:text-white transition-colors flex items-center gap-1 cursor-pointer" href="/">
         <i class="fa-solid fa-house text-xs"></i>
         首页
        </a>
       </li>
       <li><span class="mx-1 text-slate-600">/</span></li>
       <li>
        <a class="hover:text-white transition-colors cursor-pointer" href="/blog/">
         教程资源
        </a>
       </li>
       <li><span class="mx-1 text-slate-600">/</span></li>
       <li aria-current="page" class="text-slate-500 font-medium truncate max-w-[150px] md:max-w-xs select-none">
        {title}
       </li>
      </ol>
    </nav>"""

def generate_toc(main_tag):
    """Generate Table of Contents and inject into id='toc'"""
    toc_div = main_tag.find('div', id='toc')
    if not toc_div:
        return

    article = main_tag.find('article')
    if not article:
        return

    headings = article.find_all(['h2', 'h3'])
    
    if not headings:
        # Optional: Hide TOC container if empty
        # toc_div.parent.decompose() 
        return

    toc_html = ""
    for i, tag in enumerate(headings):
        # Generate ID
        anchor_id = f"section-{i+1}"
        tag['id'] = anchor_id
        
        # Style logic
        text = tag.get_text(strip=True)
        # Indent and style
        if tag.name == 'h2':
            base_class = "block hover:text-[#24A1DE] transition-colors py-1"
        else:
            base_class = "block hover:text-[#24A1DE] transition-colors py-1 pl-4 text-xs text-slate-400"
            
        toc_html += f'<a href="#{anchor_id}" class="{base_class}">{text}</a>\n'
        
    # Inject
    toc_soup = BeautifulSoup(toc_html, 'html.parser')
    toc_div.clear()
    toc_div.append(toc_soup)

def process_posts():
    print("Starting Build Process...")
    
    # 1. Get Layout & Favicons from Index
    nav_component, footer_component, favicons = get_layout_components()
    if not nav_component or not footer_component:
        print("Failed to extract layout.")
        return

    # 2. Scan posts
    posts = []
    files = glob.glob(os.path.join(BLOG_DIR, "*.html"))
    
    # First pass: Parse all metadata to have a list for recommendations and index
    for filepath in files:
        filename = os.path.basename(filepath)
        if filename in ['index.html', 'template.html', 'layout_template.html']:
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            
        # Get Title from H1 (Preferred) or Title Tag
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(" ", strip=True)
        elif soup.title and soup.title.string:
            title = soup.title.string.split(' - ')[0].strip()
        else:
            title = "无标题"
        
        # Get description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        description = desc_tag['content'] if desc_tag else ""
        
        # Get Date
        time_tag = soup.find('time')
        date_str = time_tag['datetime'] if time_tag else "2025-01-01"
        
        # Get Keywords
        kw_tag = soup.find('meta', attrs={'name': 'keywords'})
        keywords = kw_tag['content'] if kw_tag else ""
        
        # Category
        cat_key = get_category_from_filename(filename)
        category = CATEGORY_CONFIG.get(cat_key, CATEGORY_CONFIG['default'])
        
        clean_slug = filename.replace('.html', '')
        url = f"/blog/{clean_slug}"
        full_url = f"{DOMAIN}{url}"
        
        posts.append({
            'title': title,
            'description': description,
            'date': date_str,
            'date_modified': datetime.now().strftime("%Y-%m-%d"),
            'keywords': keywords,
            'filename': filename,
            'filepath': filepath,
            'url': url,
            'canonical_url': full_url,
            'category': cat_key,
            'category_obj': category,
            'image': '/assets/og-cover.svg' # Default
        })
        
    # Sort posts
    posts.sort(key=lambda x: (x['date'], x['filename']), reverse=True)
    
    # 3. Process each post (Write phase)
    for post in posts:
        print(f"Processing {post['filename']}...")
        with open(post['filepath'], 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            
        # --- Phase 3: Content Aggregation ---
        
        # Sync Layout: Replace Nav and Footer
        # We need to find the <main> tag of the post
        main_tag = soup.find('main')
        if not main_tag:
            print(f"Warning: No <main> tag in {post['filename']}")
            continue
            
        # Create new body structure
        new_body = soup.new_tag('body', attrs={'class': 'min-h-screen bg-slate-900 text-white'})
        
        # Inject Nav (Clone it)
        import copy
        new_nav = copy.copy(nav_component)
        
        # Fix Nav links in component (relative to root)
        # Since they come from index.html (root), they should be fine as absolute paths /...
        # But we need to ensure they are clean and anchors point to root
        for a in new_nav.find_all('a', href=True):
            a['href'] = resolve_anchor_to_root(a['href'])
        # Fix images in Nav
        for img in new_nav.find_all('img', src=True):
            img['src'] = resolve_anchor_to_root(img['src'])
            
        new_body.append(new_nav)
        new_body.append('\n')
        
        # Inject Main
        # Clean links in Main
        fix_relative_links_in_post(main_tag)
        generate_toc(main_tag)
        for a in main_tag.find_all('a', href=True):
            a['href'] = clean_url(a['href'])
        for img in main_tag.find_all('img', src=True):
            # Images in posts should also be absolute
            img['src'] = resolve_anchor_to_root(img['src'])
            
        # Inject/Update Visual Breadcrumb
        # Find existing breadcrumb to remove/update or prepend
        existing_bread = main_tag.find('nav', attrs={'aria-label': 'Breadcrumb'})
        if existing_bread:
            existing_bread.decompose()
        
        # We need to insert it at the top of the main content area
        # Assuming the main structure is <div class="grid..."><div class="lg:col-span-2">...
        # We look for the col-span-2 container or just insert at top of main if simpler structure
        content_container = main_tag.find('div', class_='lg:col-span-2')
        if not content_container:
            # Fallback: try to find the first H1 and insert before it
            h1 = main_tag.find('h1')
            if h1:
                content_container = h1.parent
            else:
                content_container = main_tag # Worst case
        
        bread_html = generate_breadcrumb_html(post['title'])
        bread_soup = BeautifulSoup(bread_html, 'html.parser')
        
        if content_container:
             # Insert at the beginning of content container
             content_container.insert(0, bread_soup)
        
            
        # Inject Recommendation
        # Find </article> (it's inside main)
        article = main_tag.find('article')
        if article:
            # Remove existing recommendations
            # Heuristic 1: Div with class recommendation-section (added by us)
            for div in article.find_all('div', class_='recommendation-section'):
                div.decompose()
                
            # Heuristic 2: Div with h2 text "相关文章" (legacy)
            for div in article.find_all('div', recursive=False):
                h2 = div.find('h2')
                if h2 and "相关文章" in h2.get_text():
                    div.decompose()
            
            # Append new
            rec_html = generate_recommendations(posts, post['filename'])
            rec_soup = BeautifulSoup(rec_html, 'html.parser')
            article.append(rec_soup)
            
        new_body.append(main_tag)
        new_body.append('\n')
        
        # Inject Footer
        new_footer = copy.copy(footer_component)
        for a in new_footer.find_all('a', href=True):
            a['href'] = resolve_anchor_to_root(a['href'])
        new_body.append(new_footer)
        
        # Replace Body
        if soup.body:
            soup.body.replace_with(new_body)
        else:
            soup.append(new_body)
            
        # --- Phase 2: Head Reconstruction ---
        reconstruct_head(soup, post, favicons)
        
        # --- Phase 1: Clean URL (Global) ---
        # We already cleaned specific parts, but let's do a final pass on all tags just in case
        for tag in soup.find_all(['a', 'link'], href=True):
            # Skip SEO tags (canonical, alternate/hreflang)
            rel = tag.get('rel', [])
            if isinstance(rel, str): rel = [rel]
            if set(rel) & {'canonical', 'alternate'}:
                continue
            
            # Skip icons in global clean if they are files (logic inside clean_url handles .html)
            # But we want to ensure favicons are not touched if they are absolute.
            # clean_url mostly handles .html removal and domain stripping.
            tag['href'] = clean_url(tag['href'])
        for tag in soup.find_all(['script', 'img'], src=True):
            tag['src'] = clean_url(tag['src'])
            
        # SEO Link Processing
        process_seo_links(soup, is_index=False)
            
        # Write back
        with open(post['filepath'], 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify())) # Prettify handles indentation
            
    # 4. Update Index HTML
    update_index_html(posts)
    
    # 5. Update Blog Index HTML
    update_blog_index_html(posts)
    
    # 5.1 Update other static pages
    update_static_page("sitemap.html")
    update_static_page("privacy-terms.html")
    update_static_page("about.html")
    
    # 5.2 Update Sitemap HTML Content
    update_sitemap_html_content(posts)
    
    # 6. Generate Sitemap
    generate_sitemap(posts)
    
    print("Build Complete.")

def fix_seo_tags(soup, full_url):
    """Ensure canonical and hreflang tags use absolute URLs"""
    # Canonical
    canon = soup.find('link', rel='canonical')
    if canon:
        canon['href'] = full_url
    
    # Hreflang
    for link in soup.find_all('link', rel='alternate'):
        if link.get('hreflang'):
            link['href'] = full_url

def process_seo_links(soup, is_index=False):
    """
    1. /go/buy on Index -> rel="nofollow sponsored noopener noreferrer"
    2. /go/buy on Others -> href="/#products" (Internal Anchor)
    3. External Links -> rel="nofollow noopener noreferrer"
    """
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href:
            continue
            
        # Check for /go/buy variations
        is_buy_link = False
        if '/go/buy' in href:
             # Check for exact match or path match
             if href == '/go/buy' or href == '/go/buy/' or href.endswith('/go/buy') or href.endswith('/go/buy/'):
                 is_buy_link = True
        
        if is_buy_link:
            if is_index:
                # Add attributes
                rel = a.get('rel', [])
                if isinstance(rel, str): rel = rel.split()
                new_rel = set(rel)
                new_rel.update(['nofollow', 'sponsored', 'noopener', 'noreferrer'])
                a['rel'] = list(new_rel)
            else:
                # Change to internal anchor
                a['href'] = '/#products'
                # Remove nofollow/sponsored if present to pass weight internally
                rel = a.get('rel', [])
                if isinstance(rel, str): rel = rel.split()
                if rel:
                    for x in ['nofollow', 'sponsored']:
                        if x in rel:
                            rel.remove(x)
                    a['rel'] = rel
                    
        # External Links
        elif href.startswith('http') and DOMAIN not in href and 'tgmai.top' not in href:
            rel = a.get('rel', [])
            if isinstance(rel, str): rel = rel.split()
            new_rel = set(rel)
            new_rel.update(['nofollow', 'noopener', 'noreferrer'])
            a['rel'] = list(new_rel)


def update_index_html(posts):
    print(f"Updating {INDEX_FILE}...")
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        
    # Generate Cards
    target_class = "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8"
    grid_div = soup.find('div', class_=target_class)
    
    if grid_div:
        grid_div.clear()
        for post in posts[:4]: # Top 4
            cat = post['category_obj']
            card_html = f"""
            <a href="{post['url']}" title="{post['title']}" class="group flex flex-col h-full bg-slate-800 rounded-2xl border border-white/10 overflow-hidden hover:border-[#24A1DE]/50 transition-all duration-300 hover:-translate-y-1">
                <div class="h-48 bg-slate-700/50 relative overflow-hidden">
                    <div class="absolute inset-0 flex items-center justify-center bg-gradient-to-br {cat['bg_gradient']}">
                        <i class="fa-solid {cat['icon']} text-6xl {cat['icon_color']} group-hover:scale-110 transition duration-500"></i>
                    </div>
                    <div class="absolute top-4 left-4 {cat['label_bg']} text-white text-xs font-bold px-2 py-1 rounded">{cat['label']}</div>
                </div>
                <div class="p-6 flex-1 flex flex-col">
                    <div class="text-xs text-slate-500 mb-3"><i class="fa-regular fa-calendar mr-2"></i><time datetime="{post['date']}">{post['date']}</time></div>
                    <h3 class="text-xl font-bold text-white mb-3 group-hover:text-[#24A1DE] transition">{post['title']}</h3>
                    <p class="text-sm text-slate-400 line-clamp-2 mb-4">
                        {post['description']}
                    </p>
                    <div class="mt-auto flex items-center text-[#24A1DE] text-sm font-medium">
                        阅读全文 <i class="fa-solid fa-angle-right ml-2 group-hover:translate-x-1 transition"></i>
                    </div>
                </div>
            </a>"""
            grid_div.append(BeautifulSoup(card_html, 'html.parser'))
            
    # Clean URLs in Index
    for tag in soup.find_all(['a', 'link'], href=True):
        # Skip SEO tags (canonical, alternate/hreflang)
        rel = tag.get('rel', [])
        if isinstance(rel, str): rel = [rel]
        if set(rel) & {'canonical', 'alternate'}:
            continue
        tag['href'] = clean_url(tag['href'])
    
    # Fix SEO tags explicitly
    fix_seo_tags(soup, f"{DOMAIN}/")
    
    # SEO Link Processing (Index Mode)
    process_seo_links(soup, is_index=True)
            
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(str(soup.prettify()))

def update_static_page(filename, title=None, breadcrumb_name=None):
    """Update static pages like sitemap.html, privacy-terms.html, about.html with new Nav/Footer"""
    if not os.path.exists(filename):
        print(f"Warning: {filename} not found.")
        return

    print(f"Updating {filename}...")
    
    # Sync Layout from Index
    nav_component, footer_component, _ = get_layout_components()
    
    with open(filename, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    import copy
    
    # Update Nav
    if nav_component:
        old_nav = soup.find('nav')
        if old_nav:
            new_nav = copy.copy(nav_component)
            # Ensure links are clean
            for a in new_nav.find_all('a', href=True):
                a['href'] = resolve_anchor_to_root(a['href'])
            for img in new_nav.find_all('img', src=True):
                img['src'] = resolve_anchor_to_root(img['src'])
            old_nav.replace_with(new_nav)
            
    # Update Footer
    if footer_component:
        old_footer = soup.find('footer')
        if old_footer:
            new_footer = copy.copy(footer_component)
            for a in new_footer.find_all('a', href=True):
                a['href'] = resolve_anchor_to_root(a['href'])
            for img in new_footer.find_all('img', src=True):
                img['src'] = resolve_anchor_to_root(img['src'])
            old_footer.replace_with(new_footer)
            
    # Inject JSON-LD Schema
    head = soup.head
    if head and title and breadcrumb_name:
        # Remove old schema
        for s in head.find_all('script', type="application/ld+json"):
            s.decompose()
            
        # BreadcrumbList Schema
        schema_bread = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "首页", "item": f"{DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": breadcrumb_name, "item": f"{DOMAIN}/{filename.replace('.html', '')}"}
            ]
        }
        script_bread = soup.new_tag('script', type="application/ld+json")
        script_bread.string = json.dumps(schema_bread, ensure_ascii=False, indent=2)
        head.append(script_bread)
        head.append('\n')

    # Inject Visual Breadcrumb (if main exists)
    main_tag = soup.find('main')
    if main_tag and breadcrumb_name:
        # Check if we need to insert breadcrumb
        # We usually insert it at the very top of main, inside a container if possible
        # Or check if there is an existing one to replace?
        # For static pages, let's just assume we want to ensure it exists or replace it.
        
        existing_bread = main_tag.find('nav', attrs={'aria-label': 'Breadcrumb'})
        if existing_bread:
            existing_bread.decompose()
            
        # Generate new breadcrumb HTML
        bread_html = f"""
        <nav aria-label="Breadcrumb" class="mb-6 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
            <ol class="flex items-center space-x-2 text-sm text-slate-400">
                <li><a href="/" class="hover:text-[#24A1DE] transition">首页</a></li>
                <li><span class="text-slate-600">/</span></li>
                <li><span aria-current="page" class="text-[#24A1DE] font-medium">{breadcrumb_name}</span></li>
            </ol>
        </nav>
        """
        bread_soup = BeautifulSoup(bread_html, 'html.parser')
        
        # Insert at top of main
        main_tag.insert(0, bread_soup)

    # Clean URLs in the page
    for tag in soup.find_all(['a', 'link'], href=True):
        # Skip SEO tags (canonical, alternate/hreflang)
        rel = tag.get('rel', [])
        if isinstance(rel, str): rel = [rel]
        if set(rel) & {'canonical', 'alternate'}:
            continue
        tag['href'] = clean_url(tag['href'])
        
    for tag in soup.find_all(['script', 'img'], src=True):
        tag['src'] = clean_url(tag['src'])

    # SEO Link Processing
    process_seo_links(soup, is_index=False)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(str(soup.prettify()))

def update_blog_index_html(posts):
    print(f"Updating {BLOG_INDEX_FILE}...")
    if not os.path.exists(BLOG_INDEX_FILE):
        print(f"Warning: {BLOG_INDEX_FILE} not found.")
        return

    # Sync Layout from Index
    nav_component, footer_component, _ = get_layout_components()
    
    with open(BLOG_INDEX_FILE, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    import copy
    
    # Update Nav
    if nav_component:
        old_nav = soup.find('nav')
        if old_nav:
            new_nav = copy.copy(nav_component)
            # Ensure links are clean
            for a in new_nav.find_all('a', href=True):
                a['href'] = resolve_anchor_to_root(a['href'])
            for img in new_nav.find_all('img', src=True):
                img['src'] = resolve_anchor_to_root(img['src'])
            old_nav.replace_with(new_nav)
            
    # Update Footer
    if footer_component:
        old_footer = soup.find('footer')
        if old_footer:
            new_footer = copy.copy(footer_component)
            for a in new_footer.find_all('a', href=True):
                a['href'] = resolve_anchor_to_root(a['href'])
            for img in new_footer.find_all('img', src=True):
                img['src'] = resolve_anchor_to_root(img['src'])
            old_footer.replace_with(new_footer)
        
    # Generate Cards for ALL posts
    target_id = "blog-posts-container"
    grid_section = soup.find('section', id=target_id)
    
    if grid_section:
        grid_section.clear()
        for post in posts:
            cat = post['category_obj']
            # Using similar card design but maybe adapted for list
            # The blog/index.html uses <article class="h-full"> wrapper
            card_html = f"""
            <article class="h-full"><a href="{post['url']}" class="group flex flex-col h-full bg-slate-800 rounded-2xl border border-white/10 overflow-hidden hover:border-[#24A1DE]/50 transition-all duration-300 hover:-translate-y-1">
                <div class="h-44 bg-slate-700/50 relative overflow-hidden">
                    <div class="absolute inset-0 flex items-center justify-center bg-gradient-to-br {cat['bg_gradient']}">
                        <i class="fa-solid {cat['icon']} text-5xl {cat['icon_color']} group-hover:scale-110 transition duration-500"></i>
                    </div>
                    <div class="absolute top-4 left-4 {cat['label_bg']} text-white text-xs font-bold px-2 py-1 rounded">{cat['label']}</div>
                </div>
                <div class="p-5 flex-1 flex flex-col">
                    <div class="text-xs text-slate-500 mb-2"><i class="fa-regular fa-calendar mr-2"></i><time datetime="{post['date']}">{post['date']}</time></div>
                    <h3 class="text-lg font-bold text-white mb-2 group-hover:text-[#24A1DE] transition">{post['title']}</h3>
                    <p class="text-sm text-slate-400 line-clamp-2 mb-4">
                        {post['description']}
                    </p>
                    <div class="mt-auto flex items-center text-[#24A1DE] text-sm font-medium">
                        阅读更多 <i class="fa-solid fa-angle-right ml-2 group-hover:translate-x-1 transition"></i>
                    </div>
                </div>
            </a></article>"""
            grid_section.append(BeautifulSoup(card_html, 'html.parser'))
            
    # Clean URLs in Blog Index
    for tag in soup.find_all(['a', 'link'], href=True):
        # Skip SEO tags (canonical, alternate/hreflang)
        rel = tag.get('rel', [])
        if isinstance(rel, str): rel = [rel]
        if set(rel) & {'canonical', 'alternate'}:
            continue
        tag['href'] = clean_url(tag['href'])
        
    # Fix SEO tags explicitly
    fix_seo_tags(soup, f"{DOMAIN}/blog/")
    
    # Generate and Inject JSON-LD Schema
    head = soup.head
    if head:
        # Remove old schema
        for s in head.find_all('script', type="application/ld+json"):
            s.decompose()
            
        # Create new schema
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": 1,
                            "name": "首页",
                            "item": f"{DOMAIN}/"
                        },
                        {
                            "@type": "ListItem",
                            "position": 2,
                            "name": "博客",
                            "item": f"{DOMAIN}/blog/"
                        }
                    ]
                },
                {
                    "@type": "CollectionPage",
                    "name": "TGMai 博客 - 使用教程与资讯",
                    "description": "TGMai 博客提供最新的 Telegram 使用教程、账号汉化、防封指南、Premium 会员充值及 Tdata 直登号购买攻略。",
                    "url": f"{DOMAIN}/blog/",
                    "publisher": {
                        "@type": "Organization",
                        "name": "TGMai",
                        "logo": {
                            "@type": "ImageObject",
                            "url": f"{DOMAIN}/assets/logo.png"
                        }
                    },
                    "mainEntity": {
                        "@type": "ItemList",
                        "itemListElement": []
                    }
                }
            ]
        }
        
        # Add posts to ItemList
        for i, post in enumerate(posts):
            schema["@graph"][1]["mainEntity"]["itemListElement"].append({
                "@type": "ListItem",
                "position": i + 1,
                "item": {
                    "@type": "BlogPosting",
                    "headline": post['title'],
                    "description": post['description'],
                    "datePublished": post['date'],
                    "dateModified": post.get('date_modified', post['date']),
                    "url": post['canonical_url'],
                    "image": f"{DOMAIN}/assets/logo.png",
                    "author": {
                        "@type": "Organization",
                        "name": "TGMai"
                    },
                    "mainEntityOfPage": {
                        "@type": "WebPage",
                        "@id": post['canonical_url']
                    }
                }
            })
            
        script_tag = soup.new_tag('script', type="application/ld+json")
        script_tag.string = json.dumps(schema, ensure_ascii=False, indent=2)
        head.append(script_tag)
        head.append('\n')

    # SEO Link Processing
    process_seo_links(soup, is_index=False)
            
    with open(BLOG_INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(str(soup.prettify()))

def update_sitemap_html_content(posts):
    """Update the content list of blog posts in sitemap.html"""
    filename = "sitemap.html"
    print(f"Updating content in {filename}...")
    if not os.path.exists(filename):
        print(f"Warning: {filename} not found.")
        return

    with open(filename, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        
    # Find the Blog section
    # Heuristic: Find h2 with text containing "博客"
    target_ul = None
    for h2 in soup.find_all('h2', class_='section-title'):
        if "博客" in h2.get_text():
            # The ul should be the next sibling or inside the same section
            section = h2.find_parent('section')
            if section:
                target_ul = section.find('ul')
            break
            
    if target_ul:
        target_ul.clear()
        
        # Add "All Posts" link first
        li_all = soup.new_tag('li')
        a_all = soup.new_tag('a', href="/blog/", class_="sitemap-link font-semibold text-white")
        icon_all = soup.new_tag('i', class_="fa-solid fa-list")
        a_all.append(icon_all)
        a_all.append(" 博客首页 (全部文章)")
        li_all.append(a_all)
        target_ul.append(li_all)
        target_ul.append('\n')
        
        # Add each post
        for post in posts:
            li = soup.new_tag('li')
            a = soup.new_tag('a', href=post['url'], class_="sitemap-link")
            icon = soup.new_tag('i', class_="fa-regular fa-file-lines")
            a.append(icon)
            # Use title from post
            a.append(f" {post['title']}")
            li.append(a)
            target_ul.append(li)
            target_ul.append('\n')
            
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(str(soup.prettify()))

def generate_sitemap(posts):
    print("Generating sitemap.xml...")
    # Static Pages
    urls = [
        {"loc": DOMAIN + "/", "changefreq": "monthly", "priority": "1.0"},
        {"loc": DOMAIN + "/blog/", "changefreq": "monthly", "priority": "0.9"},
        {"loc": DOMAIN + "/about", "changefreq": "monthly", "priority": "0.5"},
        {"loc": DOMAIN + "/privacy-terms", "changefreq": "yearly", "priority": "0.3"},
        {"loc": DOMAIN + "/sitemap", "changefreq": "weekly", "priority": "0.5"}
    ]
    
    # Add Blog Posts
    for post in posts:
        urls.append({
            "loc": post['canonical_url'],
            "changefreq": "weekly",
            "priority": "0.8"
        })
        
    sitemap_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for url_data in urls:
        sitemap_content += f'  <url>\n    <loc>{url_data["loc"]}</loc>\n    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>\n    <changefreq>{url_data["changefreq"]}</changefreq>\n    <priority>{url_data["priority"]}</priority>\n  </url>\n'
        
    sitemap_content += '</urlset>'
    
    with open("sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(sitemap_content)

if __name__ == "__main__":
    process_posts()
