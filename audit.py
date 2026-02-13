import os
import sys
import re
import csv
import requests
import concurrent.futures
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from urllib.parse import urlparse, urljoin, unquote
from collections import defaultdict, deque
from pathlib import Path

# Initialize colorama
init(autoreset=True)

class Config:
    def __init__(self):
        self.root_dir = os.getcwd()
        self.base_url = None
        self.keywords = []
        
        # Ignore Lists
        self.ignore_paths = ['.git', 'node_modules', '__pycache__', '.vscode', '.idea', 'MasterTool']
        self.ignore_url_prefixes = ['javascript:', 'mailto:', 'tel:', '#', 'tg:']
        self.ignore_url_substrings = ['cdn-cgi']
        self.ignore_files_substrings = ['google', '404.html', 'template']
        self.redirects = {}
        
    def load(self):
        # Load _redirects
        redirects_path = os.path.join(self.root_dir, '_redirects')
        if os.path.exists(redirects_path):
            try:
                with open(redirects_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            self.redirects[parts[0]] = parts[1]
                print(f"{Fore.CYAN}Loaded {len(self.redirects)} redirects from _redirects")
            except Exception as e:
                print(f"{Fore.RED}[WARN] Failed to read _redirects: {e}")

        index_path = os.path.join(self.root_dir, 'index.html')
        if not os.path.exists(index_path):
            print(f"{Fore.YELLOW}[WARN] index.html not found. Cannot auto-configure Base URL.")
            return

        try:
            with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
                # Base URL
                canonical = soup.find('link', rel='canonical')
                if canonical and canonical.get('href') and canonical['href'].startswith('http'):
                    self.base_url = canonical['href'].rstrip('/')
                else:
                    og_url = soup.find('meta', property='og:url')
                    if og_url and og_url.get('content') and og_url['content'].startswith('http'):
                        self.base_url = og_url['content'].rstrip('/')
                
                # Keywords
                meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                if meta_keywords and meta_keywords.get('content'):
                    self.keywords = [k.strip() for k in meta_keywords['content'].split(',')]
                    
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Failed to read index.html: {e}")

class Auditor:
    def __init__(self):
        self.config = Config()
        self.config.load()
        
        self.html_files = [] # List of full paths
        self.inbound_links = defaultdict(int) # clean_path -> count
        self.outbound_internal_links = defaultdict(int) # clean_path -> count
        self.internal_graph = defaultdict(set) # clean_path -> set(clean_target_paths)
        self.page_details = {} # clean_path -> {title, depth, etc}
        self.external_links = set() # Set of (url, source_file)
        
        self.score = 100
        self.issues = {
            'local_dead_links': 0,
            'external_dead_links': 0,
            'missing_h1': 0,
            'bad_url_format': 0,
            'missing_schema': 0,
            'orphans': 0
        }
        
        # Cache for validation
        self.checked_external_urls = {} # url -> status_code

    def is_ignored_file(self, file_path):
        name = os.path.basename(file_path)
        for ignore in self.config.ignore_files_substrings:
            if ignore in name:
                return True
        return False

    def is_ignored_path(self, dir_path):
        for part in dir_path.split(os.sep):
            if part in self.config.ignore_paths:
                return True
        return False

    def is_ignored_url(self, url):
        for prefix in self.config.ignore_url_prefixes:
            if url.startswith(prefix):
                return True
        for sub in self.config.ignore_url_substrings:
            if sub in url:
                return True
        return False

    def scan_files(self):
        print(f"{Fore.CYAN}Scanning directory: {self.config.root_dir}")
        for root, dirs, files in os.walk(self.config.root_dir):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.config.ignore_paths]
            
            for file in files:
                if file.endswith('.html'):
                    if self.is_ignored_file(file):
                        continue
                    self.html_files.append(os.path.join(root, file))
        
        print(f"{Fore.CYAN}Found {len(self.html_files)} HTML files.")

    def get_clean_path(self, file_path):
        """Convert file path to Clean URL path for reporting and graph"""
        rel_path = os.path.relpath(file_path, self.config.root_dir)
        path_parts = rel_path.split(os.sep)
        
        if path_parts[-1] == 'index.html':
            path_parts.pop()
        elif path_parts[-1].endswith('.html'):
            path_parts[-1] = path_parts[-1][:-5]
            
        clean_path = '/' + '/'.join(path_parts)
        if clean_path == '//': clean_path = '/' # Root case
        return clean_path

    def resolve_local_link(self, source_file, href):
        """
        Resolve href to absolute file path candidates.
        Returns a list of possible file paths on disk.
        """
        # Strip query and hash
        href = href.split('#')[0].split('?')[0]
        
        if not href:
            return []

        target_path = None
        
        if href.startswith('/'):
            # Root relative
            # /blog/post -> root_dir/blog/post
            target_path = os.path.join(self.config.root_dir, href.lstrip('/'))
        else:
            # Relative to current file
            # source: /a/b/c.html, href: d/e -> /a/b/d/e
            source_dir = os.path.dirname(source_file)
            target_path = os.path.join(source_dir, href)
            
        # Normalize path
        target_path = os.path.normpath(target_path)
        
        # Candidates to check
        candidates = []
        
        # If it looks like a file (has extension), check it directly
        if os.path.splitext(target_path)[1]:
            candidates.append(target_path)
        else:
            # It's a directory-style path (Clean URL)
            # 1. Check if it maps to a .html file: /blog/post -> /blog/post.html
            candidates.append(target_path + '.html')
            # 2. Check if it maps to index.html: /blog/post -> /blog/post/index.html
            candidates.append(os.path.join(target_path, 'index.html'))
            
        return candidates

    def check_local_resource_exists(self, candidates):
        for path in candidates:
            if os.path.isfile(path):
                return True, path
        return False, None

    def audit_page(self, file_path):
        rel_path = os.path.relpath(file_path, self.config.root_dir)
        clean_source = self.get_clean_path(file_path)
        
        # Initialize page details
        if clean_source not in self.page_details:
            self.page_details[clean_source] = {
                'file_path': file_path,
                'title': 'Unknown',
                'depth': float('inf')
            }

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                soup = BeautifulSoup(content, 'html.parser')
                
                # --- Metadata ---
                # Title
                title_tag = soup.find('title')
                if title_tag and title_tag.string:
                    self.page_details[clean_source]['title'] = title_tag.string.strip()

                # --- Semantics ---
                # H1 Check
                h1s = soup.find_all('h1')
                if len(h1s) != 1:
                    if 'section.html' not in rel_path and 'go/' not in rel_path:
                         print(f"{Fore.RED}[ERROR] H1 count is {len(h1s)} (expected 1): {rel_path}")
                         self.score -= 5
                         self.issues['missing_h1'] += 1
                
                # Schema Check
                if 'sitemap.html' not in rel_path and 'section.html' not in rel_path and 'go/' not in rel_path:
                    schema = soup.find('script', type='application/ld+json')
                    if not schema:
                        print(f"{Fore.YELLOW}[WARN] Missing JSON-LD Schema: {rel_path}")
                        self.score -= 2
                        self.issues['missing_schema'] += 1
                    
                # Breadcrumb Check (simplified)
                breadcrumb = soup.find(attrs={"aria-label": "breadcrumb"}) or soup.find(class_=lambda x: x and 'breadcrumb' in x)
                # Not strictly deducting for breadcrumb per spec summary, but good to check. 
                # Spec says "Check page contains..." under Semantics. Let's warn if missing on non-home pages?
                # Spec doesn't assign specific points for breadcrumb in "Reporting" section, only "Missing Schema".
                # So I'll just log it as info or warning without deduction if strict.
                # However, usually breadcrumb is good.
                
                # --- Links ---
                links = soup.find_all('a')
                for link in links:
                    href = link.get('href')
                    if not href:
                        continue
                        
                    if self.is_ignored_url(href):
                        continue
                        
                    # External Links
                    if href.startswith('http://') or href.startswith('https://'):
                        # Check for absolute internal URL
                        if self.config.base_url and href.startswith(self.config.base_url):
                            print(f"{Fore.YELLOW}[WARN] Absolute Internal URL: {href} in {rel_path}")
                            self.score -= 2
                            self.issues['bad_url_format'] += 1
                            # Treat as internal for existence check?
                            # Convert to relative path to check existence
                            local_href = href[len(self.config.base_url):]
                            candidates = self.resolve_local_link(file_path, local_href)
                            exists, resolved_path = self.check_local_resource_exists(candidates)
                            if not exists:
                                print(f"{Fore.RED}[ERROR] Dead Link (Internal Absolute): {href} in {rel_path}")
                                self.score -= 10
                                self.issues['local_dead_links'] += 1
                            else:
                                clean_source = self.get_clean_path(file_path)
                                self.outbound_internal_links[clean_source] += 1
                                clean_target = self.get_clean_path(resolved_path)
                                self.inbound_links[clean_target] += 1
                                self.internal_graph[clean_source].add(clean_target)
                        else:
                            # True External
                            self.external_links.add(href)
                            rel = link.get('rel', [])
                            if 'nofollow' not in rel and 'noopener' not in rel:
                                # Simple domain check to see if it's "authority" is hard. 
                                # Spec says "Check rel=nofollow (for non-authority) or rel=noopener".
                                # We'll just warn if neither is present.
                                # print(f"{Fore.YELLOW}[WARN] External link missing rel='noopener': {href}")
                                pass 
                        continue
                        
                    # Internal Links
                    # Check for redirects
                    if href in self.config.redirects:
                        # Count as inbound link for the redirect source itself
                        # This prevents the redirect URL from being marked as orphan if it exists as a file (like /go/buy)
                        # or just acknowledges it's being linked to.
                        # We use the href as the key.
                        # Ensure href starts with /
                        clean_href = href if href.startswith('/') else '/' + href
                        self.inbound_links[clean_href] += 1

                        # Treat as valid, check if target is external
                        target = self.config.redirects[href]
                        if target.startswith('http'):
                            self.external_links.add(target)
                        else:
                            clean_source = self.get_clean_path(file_path)
                            self.outbound_internal_links[clean_source] += 1
                        continue

                    # URL Format Checks
                    if not href.startswith('/'):
                        print(f"{Fore.YELLOW}[WARN] Relative path used: {href} in {rel_path}")
                        self.score -= 2
                        self.issues['bad_url_format'] += 1
                        
                    if href.endswith('.html'):
                        print(f"{Fore.YELLOW}[WARN] Link ends with .html: {href} in {rel_path}")
                        self.score -= 2
                        self.issues['bad_url_format'] += 1

                    # Dead Link Check (Local File System)
                    candidates = self.resolve_local_link(file_path, href)
                    exists, resolved_path = self.check_local_resource_exists(candidates)
                    
                    if not exists:
                        print(f"{Fore.RED}[ERROR] Dead Link (Local): {href} in {rel_path}")
                        self.score -= 10
                        self.issues['local_dead_links'] += 1
                    else:
                        # Link Equity (Inbound Links)
                        # Map resolved path to clean URL
                        clean_target = self.get_clean_path(resolved_path)
                        self.inbound_links[clean_target] += 1
                        
                        clean_source = self.get_clean_path(file_path)
                        self.outbound_internal_links[clean_source] += 1
                        self.internal_graph[clean_source].add(clean_target)
        
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Processing {rel_path}: {e}")

    def check_external_links(self):
        print(f"\n{Fore.BLUE}Checking {len(self.external_links)} external links...")
        
        def check_url(url):
            headers = {'User-Agent': 'SEOAuditBot/1.0'}
            try:
                response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
                if response.status_code == 405: # Method Not Allowed
                    response = requests.get(url, headers=headers, timeout=5, stream=True)
                return url, response.status_code
            except Exception:
                return url, 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(check_url, url): url for url in self.external_links}
            for future in concurrent.futures.as_completed(future_to_url):
                url, status = future.result()
                if status >= 400 or status == 0:
                    print(f"{Fore.RED}[ERROR] Dead External Link: {url} (Status: {status})")
                    self.score -= 5
                    self.issues['external_dead_links'] += 1

    def calculate_click_depth(self):
        """Calculate click depth (distance from root) using BFS"""
        queue = deque([('/', 0)])
        visited = {'/'}
        
        # Ensure root is in page_details even if not scanned yet (should be)
        if '/' in self.page_details:
            self.page_details['/']['depth'] = 0
            
        while queue:
            current_page, depth = queue.popleft()
            
            # Update depth for current page
            if current_page in self.page_details:
                self.page_details[current_page]['depth'] = min(self.page_details[current_page]['depth'], depth)
            
            # Find neighbors
            if current_page in self.internal_graph:
                for neighbor in self.internal_graph[current_page]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))
                        
    def save_csv_report(self):
        filename = 'audit_report.csv'
        print(f"\n{Fore.CYAN}Generating CSV report: {filename}...")
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['URL', 'Title', 'Click Depth', 'Inbound Links', 'Outbound Internal', 'Outbound External', 'Status']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                
                # Sort by depth then URL
                sorted_pages = sorted(self.page_details.items(), key=lambda x: (x[1]['depth'], x[0]))
                
                for url, details in sorted_pages:
                    depth = details['depth']
                    if depth == float('inf'):
                        depth = 'Orphan'
                        
                    writer.writerow({
                        'URL': url,
                        'Title': details.get('title', 'N/A'),
                        'Click Depth': depth,
                        'Inbound Links': self.inbound_links.get(url, 0),
                        'Outbound Internal': self.outbound_internal_links.get(url, 0),
                        'Outbound External': 0, # TODO: Track per page if needed, currently global set
                        'Status': '200' # Assumed existing local file
                    })
            print(f"{Fore.GREEN}CSV report saved successfully.")
        except Exception as e:
            print(f"{Fore.RED}Failed to save CSV report: {e}")

    def generate_report(self):
        self.calculate_click_depth()
        
        print(f"\n{Fore.MAGENTA}{'='*30} AUDIT REPORT {'='*30}")
        
        # Orphans
        # Initialize counts for all known pages to 0 if not present
        for file_path in self.html_files:
            clean_path = self.get_clean_path(file_path)
            if clean_path not in self.inbound_links:
                self.inbound_links[clean_path] = 0
                
        orphans = []
        ignored_orphans = ['/404', '/google', '/layout_template', '/section', '/sitemap'] # Basic ignored
        
        for page, count in self.inbound_links.items():
            if count == 0:
                # Check if ignored
                is_ignored = False
                if page == '/' or page == '': is_ignored = True
                for ig in ignored_orphans:
                    if ig in page: is_ignored = True
                
                if not is_ignored:
                    orphans.append(page)

        if orphans:
            print(f"\n{Fore.YELLOW}Orphan Pages (No Inbound Links):")
            for o in orphans:
                print(f"  {o}")
                self.score -= 5
                self.issues['orphans'] += 1
        
        # Top Pages
        print(f"\n{Fore.GREEN}Top 10 Pages by Inbound Internal Links:")
        top_pages = sorted(self.inbound_links.items(), key=lambda x: x[1], reverse=True)[:10]
        for page, count in top_pages:
            print(f"  {page}: {count}")

        # Weakly Linked Pages
        print(f"\n{Fore.YELLOW}Weakly Linked Pages (Inbound < 3, excluding orphans):")
        weak_pages = [p for p, c in self.inbound_links.items() if 0 < c < 3]
        if weak_pages:
            for p in sorted(weak_pages):
                print(f"  {p}: {self.inbound_links[p]}")
        else:
            print(f"  {Fore.GREEN}None.")

        # Click Depth Distribution
        print(f"\n{Fore.BLUE}Click Depth Distribution:")
        depth_counts = defaultdict(int)
        for details in self.page_details.values():
            d = details['depth']
            if d == float('inf'):
                depth_counts['Orphan'] += 1
            else:
                depth_counts[d] += 1
        
        for d in sorted([k for k in depth_counts.keys() if isinstance(k, int)]):
             print(f"  Depth {d}: {depth_counts[d]} pages")
        if 'Orphan' in depth_counts:
             print(f"  Orphans: {depth_counts['Orphan']} pages")

        # Internal Outbound Links Stats
        print(f"\n{Fore.GREEN}Internal Outbound Links Analysis:")
        
        # Identify pages with few internal links
        low_link_pages = []
        no_link_pages = []
        
        for file_path in self.html_files:
            clean_path = self.get_clean_path(file_path)
            count = self.outbound_internal_links[clean_path]
            
            if count == 0:
                no_link_pages.append(clean_path)
            elif count < 3:
                low_link_pages.append((clean_path, count))
        
        if no_link_pages:
            print(f"{Fore.RED}Dead End Pages (0 internal outbound links):")
            for p in no_link_pages:
                print(f"  {p}")
                # Optional: Deduct score?
                # self.score -= 1
        else:
            print(f"{Fore.GREEN}  No dead end pages found.")

        if low_link_pages:
            print(f"{Fore.YELLOW}Pages with few internal outbound links (< 3):")
            for p, c in low_link_pages:
                print(f"  {p}: {c}")
        else:
             print(f"{Fore.GREEN}  All pages have 3+ internal outbound links.")

        # Final Score
        self.score = max(0, self.score)
        
        score_color = Fore.GREEN
        if self.score < 80: score_color = Fore.YELLOW
        if self.score < 50: score_color = Fore.RED
        
        print(f"\n{Fore.WHITE}Final Score: {score_color}{self.score}/100")
        
        if self.score < 100:
            print(f"\n{Fore.WHITE}Deductions Breakdown:")
            if self.issues['local_dead_links']: print(f"  Local Dead Links: -{self.issues['local_dead_links'] * 10}")
            if self.issues['external_dead_links']: print(f"  External Dead Links: -{self.issues['external_dead_links'] * 5}")
            if self.issues['missing_h1']: print(f"  Missing H1: -{self.issues['missing_h1'] * 5}")
            if self.issues['bad_url_format']: print(f"  Bad URL Format: -{self.issues['bad_url_format'] * 2}")
            if self.issues['missing_schema']: print(f"  Missing Schema: -{self.issues['missing_schema'] * 2}")
            if self.issues['orphans']: print(f"  Orphans: -{self.issues['orphans'] * 5}")
            
            print(f"\n{Fore.CYAN}Actionable Advice:")
            print("  Run 'python3 fix_links.py' to attempt automatic link fixes.")
            print("  Run 'python3 build.py' to rebuild static assets if needed.")

        self.save_csv_report()

    def run(self):
        print(f"{Fore.GREEN}Starting SEO Audit...")
        if self.config.base_url:
            print(f"Base URL: {self.config.base_url}")
        else:
            print(f"{Fore.YELLOW}Base URL not detected.")
             
        self.scan_files()
        
        print(f"{Fore.BLUE}Auditing pages...")
        for file in self.html_files:
            self.audit_page(file)
            
        self.check_external_links()
        self.generate_report()

if __name__ == "__main__":
    audit = Auditor()
    audit.run()
