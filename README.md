TGMai.top 网站项目

部署到 GitHub

方案一：SSH（推荐）
1. 生成密钥：ssh-keygen -t ed25519 -C "你的邮箱"
2. 将 ~/.ssh/id_ed25519.pub 添加到 GitHub → Settings → SSH and GPG keys
3. 推送：bash scripts/push.sh

方案二：HTTPS（PAT）
1. 在 GitHub 创建 Personal Access Token（至少 repo 权限）
2. 执行：export GITHUB_TOKEN="你的PAT"
3. 推送：bash scripts/push.sh

部署到 Vercel
1. 在 Vercel 导入此 GitHub 仓库（Framework: Other）
2. 绑定自定义域名
3. 将 og/url 与 sitemap.xml 的 URL 更新为生产域名的绝对地址

站点地图与抓取
- Sitemap: /sitemap.xml
- Robots: /robots.txt

联盟链接
- 所有购买类 CTA 已指向 https://accboyytbxmdh.acceboy.com/zh-cn-cny/buy-tg，并使用 rel="sponsored noopener noreferrer" 与 target="_blank"
