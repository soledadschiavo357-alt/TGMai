import os
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

# 配置
HOST = "tgmai.top"
KEY = "7755e297b53646acaa29d35367f9a4a7"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
# 获取脚本所在目录的上级目录的 sitemap.xml
SITEMAP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sitemap.xml")
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

def get_urls_from_sitemap(sitemap_path):
    """从 sitemap.xml 解析 URL"""
    if not os.path.exists(sitemap_path):
        print(f"Error: Sitemap not found at {sitemap_path}")
        return []
    
    try:
        tree = ET.parse(sitemap_path)
        root = tree.getroot()
        # sitemap 标准命名空间
        namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        # 尝试查找带命名空间的
        urls = [elem.text for elem in root.findall('ns:url/ns:loc', namespaces)]
        
        # 如果没找到，尝试不带命名空间的（兼容某些非标准写法）
        if not urls:
             urls = [elem.text for elem in root.findall('url/loc')]
        
        # 过滤掉 None 和空字符串，并确保去除空白字符
        urls = [url.strip() for url in urls if url and url.strip()]
        return urls
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
        return []

def push_to_indexnow(urls):
    """推送 URL 到 IndexNow"""
    if not urls:
        print("No URLs to push.")
        return

    data = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls
    }
    
    json_data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT, 
        data=json_data, 
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )

    try:
        print(f"Pushing {len(urls)} URLs to IndexNow...")
        print(f"Endpoint: {INDEXNOW_ENDPOINT}")
        print(f"Host: {HOST}")
        
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            if status_code in [200, 202]:
                print(f"Success! Status code: {status_code}")
                print("URLs successfully submitted to IndexNow.")
            else:
                print(f"Received status code: {status_code}")
                print(response.read().decode('utf-8'))
            
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        try:
            print(e.read().decode('utf-8'))
        except:
            pass
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
    except Exception as e:
        print(f"Error sending request: {e}")

if __name__ == "__main__":
    print("--- Starting IndexNow Push Script ---")
    urls = get_urls_from_sitemap(SITEMAP_PATH)
    if urls:
        print(f"Found {len(urls)} URLs in sitemap.")
        # 打印前几个 URL 用于确认
        if len(urls) > 0:
            print("First few URLs:")
            for url in urls[:3]:
                print(f" - {url}")
        
        push_to_indexnow(urls)
    else:
        print("No URLs found or error reading sitemap.")
    print("--- Done ---")
