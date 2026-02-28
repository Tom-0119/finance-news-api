# app.py - 修改版（直接爬取并返回，不存数据库）
from flask import Flask, jsonify
import crawler  # 导入你写好的爬虫类
import threading
import time

app = Flask(__name__)

# 全局变量存储数据（注意：生产环境不能这么用，但作业演示够了）
current_news_data = []

def update_data_periodically():
    """后台线程：每隔一段时间自动更新数据"""
    while True:
        print("正在后台更新数据...")
        try:
            # 实例化你的爬虫
            crawler_instance = crawler.FinanceNewsCrawler()
            # 调用 crawl 方法，这个方法会返回数据或者更新内部状态
            # 注意：你需要稍微修改一下 crawler.py 的 crawl 方法，让它返回数据列表
            data = crawler_instance.crawl_for_api() # 我们稍后修改 crawler.py
            global current_news_data
            current_news_data = data
            print(f"数据更新成功，共 {len(data)} 条")
        except Exception as e:
            print(f"更新失败: {e}")
        # 休息 30 分钟（1800秒），避免过于频繁
        time.sleep(1800)

@app.route('/api/news')
def get_news():
    """API 接口：供小程序调用"""
    # 如果没有数据，先强制更新一次
    if not current_news_data:
        # 这里调用一次更新（为了首次启动）
        # 实际上应该用上面的线程，这里简化处理
        pass
    return jsonify(current_news_data)

if __name__ == '__main__':
    # 启动后台更新线程
    thread = threading.Thread(target=update_data_periodically)
    thread.daemon = True # 主程序退出时，线程也退出
    thread.start()
    
    # 运行 Flask
    app.run(host='0.0.0.0', port=5000)

