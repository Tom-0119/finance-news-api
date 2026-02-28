import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import random
from datetime import datetime
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FinanceNewsCrawler:
    def __init__(self):
        # 财经新闻网站URL (只保留东方财富)
        self.urls = [
            'https://finance.eastmoney.com/' # 东方财富
        ]
        
        # 请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def init_database(self):
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect('eastmoney_hot_news.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    source TEXT NOT NULL,
                    publish_time TEXT, -- 这里存储 "2026-02-19 10:03 来源：界面新闻"
                    content TEXT,
                    summary TEXT,
                    category TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON news(url)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON news(source)')
            conn.commit()
            conn.close()
            logger.info("数据库初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    def get_db_connection(self):
        """创建一个新的数据库连接"""
        return sqlite3.connect('eastmoney_hot_news.db', check_same_thread=True)

    def get_page_content(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = response.apparent_encoding
            if response.status_code == 200:
                return response.text
            else:
                logger.error(f"请求失败: {response.status_code} - {url}")
                return None
        except Exception as e:
            logger.error(f"请求异常: {e} - {url}")
            return None

    def parse_eastmoney(self, html):
        """解析东方财富（优化版）"""
        news_list = []
        if not html:
            return news_list
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # 策略1: 抓取主要新闻列表 (class="list" 或 "news-list")
        for ul_selector in ['ul.list', 'ul.news-list', '.leftContent ul']:
            ul_tags = soup.select(ul_selector)
            for ul in ul_tags:
                for li in ul.select('li'):
                    a_tag = li.select_one('a')
                    if a_tag and a_tag.get('href'):
                        href = a_tag['href']
                        title = a_tag.get_text().strip()
                        
                        # 补全URL
                        if href.startswith('//'):
                            href = 'https:' + href
                        elif href.startswith('/'):
                            href = 'https://finance.eastmoney.com' + href
                            
                        # 过滤无效链接和标题
                        if ('http' in href and 
                            len(title) > 5 and 
                            not title.startswith('查看更多') and
                            '广告' not in title):
                            news_list.append({
                                'title': title,
                                'url': href,
                                'source': '东方财富',
                                'category': '股票/基金'
                            })

        # 策略2: 去重 (基于URL)
        seen = set()
        unique_news = []
        for item in news_list:
            if item['url'] not in seen:
                seen.add(item['url'])
                unique_news.append(item)
                
        logger.info(f"解析到 {len(unique_news)} 条新闻")
        return unique_news

    def get_news_content(self, url):
        """获取新闻详细内容（升级版：精准提取时间与来源）"""
        html = self.get_page_content(url)
        if not html:
            return None, None
        
        soup = BeautifulSoup(html, 'html.parser')
    
        # 移除不需要的标签
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside']):
            tag.decompose()
        
        # 提取正文 (保持不变)
        content_selectors = [
            '.article-body', '.content', '.text', '#ContentBody',
            '.news-content', '.post-content', '.article-content'
        ]
        content = ""
        for sel in content_selectors:
            elements = soup.select(sel)
            for el in elements:
                text = el.get_text(strip=False)
                if len(text) > 100:
                    content = text
                    break
            if content:
                break

        # --- 核心升级：精准提取时间与来源 ---
        # 1. 提取时间 (根据你提供的结构：class=" item" 或 "item")
        # 使用正则匹配 class，兼容 " item" 和 "item"
        time_div = soup.find('div', class_=re.compile(r'\bitem\b'))
        time_text = ""
        if time_div:
            raw_time = time_div.get_text(strip=True)
            # 使用正则提取标准时间格式 (支持 "2026年02月11日 13:25")
            time_match = re.search(r'\d{4}年\d{2}月\d{2}日\s+\d{2}:\d{2}', raw_time)
            if time_match:
                time_text = time_match.group(0) # 提取纯时间
    
        # 2. 提取来源 (根据你提供的结构：包含“来源：”的 div)
        # 寻找包含“来源”文本的 div.item
        source_div = soup.find('div', class_='item', string=re.compile(r'来源'))
        source_text = ""
        if source_div:
            raw_source = source_div.get_text(strip=True)
            # 确保格式为“来源：XXX”
            if '来源' in raw_source:
                source_text = raw_source
            else:
            # 如果文本里没有“来源”二字但被抓到了，加上前缀
                source_text = f"来源：{raw_source}"

        # 3. 拼接结果 (例如: "2026年02月11日 13:25 来源：东方财富网")
        # 优先使用提取到的时间和来源
        if time_text and source_text:
            publish_time = f"{time_text} {source_text}"
        elif time_text:
            publish_time = time_text
        elif source_text:
            publish_time = source_text
        else:
            publish_time = "未知时间/来源"
        
        # --- 结束升级 ---

        return content.strip(), publish_time

    def save_news(self, news_data):
        """保存新闻到数据库（每次新建连接）"""
        if not news_data:
            return False
            
        conn = None
        try:
            # 1. 检查是否已存在 (新建连接)
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM news WHERE url = ?', (news_data['url'],))
            if cursor.fetchone():
                logger.info(f"已存在，跳过: {news_data['title']}")
                return False
                
            # 2. 插入新数据
            cursor.execute(''' 
                INSERT INTO news 
                (title, url, source, publish_time, content, summary, category, tags) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                news_data['title'],
                news_data['url'],
                news_data['source'],
                news_data.get('publish_time'), # 这里存入的是拼接后的字符串
                news_data.get('content', '')[:5000],
                news_data.get('summary', '')[:200],
                news_data.get('category'),
                news_data.get('tags')
            ))
            conn.commit()
            logger.info(f"✅ 成功保存: {news_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"💾 保存失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def crawl(self):
        """执行爬取任务"""
        logger.info("开始财经新闻爬取...")
        
        # 确保表存在
        self.init_database()
        
        all_news = []
        for url in self.urls:
            logger.info(f"正在爬取: {url}")
            html = self.get_page_content(url)
            news_list = self.parse_eastmoney(html)
            all_news.extend(news_list)
            time.sleep(random.uniform(1, 2)) # 随机延时

        logger.info(f"共发现 {len(all_news)} 条新闻，开始获取详情...")
        
        success_count = 0
        for news in all_news:
            content, publish_time = self.get_news_content(news['url'])
            news['content'] = content
            news['publish_time'] = publish_time # 赋值给 news_data
            news['summary'] = content[:200] + "..." if content and len(content) > 200 else (content or "暂无摘要")
            
            if self.save_news(news):
                success_count += 1
            time.sleep(random.uniform(0.1, 0.3))
            
        logger.info(f"爬取任务完成，成功保存 {success_count} 条新闻")
        return success_count

# 测试代码
if __name__ == "__main__":
    crawler = FinanceNewsCrawler()
    crawler.crawl()

# 在 crawler.py 的 crawl 函数最后
def crawl_for_api(self):
    # ... (前面的代码不变) ...
    # 找到 all_news = [] ... 等逻辑
    # 在最后：
    result = []
    for news in all_news:
        # 构造符合 API 格式的数据
        item = {
            "id": hash(news['url']) % 100000, # 简单生成一个 ID
            "title": news['title'],
            "url": news['url'],
            "source": news['source'],
            "publish_time": "未知", # 这里需要你完善
            "summary": news['title'][:50] + "..." # 简单截取摘要
        }
        result.append(item)
    return result

