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
