"""
第一阶段：数据采集（多城市扩展版）
招聘岗位数据自动化采集 Agent

支持城市：广州 / 北京 / 上海 / 深圳
输出：raw_recruitment_data.csv（含 city 字段）
"""

import csv
import json
import random
import time
import urllib.parse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ══════════════════════════════════════════════════════════════════════════════
#  城市参数设计方案
#  映射关系：城市名（中文） → 51job jobArea 城市代码
#  使用字典统一管理，新增城市只需在此处追加一行，无需改动任何业务逻辑
#
#  常用城市代码（51job 官方标准）：
#    北京  010000  |  上海  020000
#    广州  030200  |  深圳  040000
#    杭州  070200  |  成都  090200
#    武汉  180200  |  南京  070100
# ══════════════════════════════════════════════════════════════════════════════
CITY_CONFIG = {
    "广州": "030200",
    "北京": "010000",
    "上海": "020000",
    "深圳": "040000",
    "杭州": "070200",
    "成都": "090200",
    "武汉": "180200",
    "南京": "070100"
}

# 搜索页 URL 模板（新增 jobArea 参数实现城市过滤）
SEARCH_URL_TEMPLATE = (
    "https://we.51job.com/pc/search"
    "?keyword={keyword}&searchType=2&jobArea={city_code}"
)

# 搜索关键词列表（每个城市都会依次搜索这些关键词）
SEARCH_KEYWORDS = [
    "Python数据分析",
    "数据工程师",
    "机器学习",
    "AI算法",
    "大数据开发",
]

# 每个关键词爬取的页数
MAX_PAGES_PER_KEYWORD = 2

# 每个关键词加载失败时的最大重试次数
MAX_RETRIES_PER_KEYWORD = 3

# Chrome 二进制路径（服务器/本地环境，可按实际路径修改）
CHROME_BINARY_PATH = r"D:\Google\Chrome\Application\chrome.exe"

# 页面加载等待超时（秒）
PAGE_LOAD_TIMEOUT = 20

# 同城市内请求间隔（秒），遵守 robots 协议
REQUEST_DELAY_RANGE = (3, 6)

# 跨城市切换间隔（秒），给服务器更充裕的间隔
CITY_SWITCH_DELAY = (5, 10)


class JobCrawlerAgent:
    """
    招聘岗位数据自动化采集 Agent（多城市 Selenium 版）

    两级采集通道：
    1. Selenium 真实爬取（we.51job.com）—— 默认，支持四城市并行采集
    2. 仿真数据通道 —— 爬取失败时兜底，保障后续清洗/分析/可视化可运行
    """

    def __init__(self, use_simulation=False):
        self.use_simulation = use_simulation
        self.data_store_path = "raw_recruitment_data.csv"

    # ──────────────────────────────────────────────────────────────────────────
    # Selenium 驱动创建
    # ──────────────────────────────────────────────────────────────────────────
    def _create_driver(self) -> webdriver.Chrome:
            """
            创建并返回配置好的 Chrome WebDriver 实例。
            """
            opts = Options()
            opts.binary_location = CHROME_BINARY_PATH
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--lang=zh-CN")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("useAutomationExtension", False) 
            
            # 管理 ChromeDriver
            chromedriver_path = r"C:\Users\12980\.wdm\drivers\chromedriver\win64\148.0.7778.217\chromedriver-win64\chromedriver.exe"
            driver = webdriver.Chrome(
                service=Service(executable_path=chromedriver_path),
                options=opts
            )
        
            # 隐藏 webdriver 属性，绕过反爬检测
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
    
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT * 2)
            return driver
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # 多城市真实爬取核心（改造重点）
    # ──────────────────────────────────────────────────────────────────────────
    def _scrape_with_selenium(self) -> list:
        """
        多城市 - 多关键词双层循环爬取。

        外层循环：遍历 CITY_CONFIG 中的每个城市
           构造含 jobArea 参数的城市专属 URL
           每个城市独立统计采集量

        内层循环：遍历 SEARCH_KEYWORDS 中的每个关键词
           每条记录注入 city 字段，标记数据来源

        设计原则：
           单一 WebDriver 实例贯穿全程，避免重复初始化开销
           城市切换时加入较长间隔，降低反爬风险
           关键词级别的重试逻辑保持不变
        """
        driver = self._create_driver()
        all_records = []

        try:
            # 建立初始会话 Cookie
            print("[INFO] 正在访问 51job 主页建立初始会话...")
            driver.get("https://we.51job.com/pc/search?keyword=Python")
            time.sleep(5)
            print(f"  主页加载完成: {driver.title}")

            total_cities = len(CITY_CONFIG)
            print(f"\n[INFO] 开始多城市采集")
            print(f"  目标城市: {list(CITY_CONFIG.keys())}")
            print(f"  搜索关键词: {SEARCH_KEYWORDS}")
            print(f"  每词最多 {MAX_PAGES_PER_KEYWORD} 页，城市数: {total_cities}")
            print("=" * 65)

            # 外层循环：遍历城市 
            for city_idx, (city_name, city_code) in enumerate(CITY_CONFIG.items()):
                city_records = []
                print(f"\n【城市 {city_idx + 1}/{total_cities}】{city_name} "
                      f"(cityCode={city_code})")
                print("-" * 45)

                # 内层循环：遍历关键词
                for keyword in SEARCH_KEYWORDS:
                    kw_records = self._scrape_keyword(
                        driver, keyword, city_name, city_code
                    )
                    city_records.extend(kw_records)
                    print(f"  ✓ [{keyword}] 获得 {len(kw_records)} 条")

                    # 关键词间随机休眠
                    if keyword != SEARCH_KEYWORDS[-1]:
                        time.sleep(random.uniform(*REQUEST_DELAY_RANGE))

                all_records.extend(city_records)
                print(f"  → {city_name} 合计: {len(city_records)} 条")

                # 城市切换间加入较长休眠，降低反爬风险
                if city_idx < total_cities - 1:
                    delay = random.uniform(*CITY_SWITCH_DELAY)
                    print(f"  城市切换等待 {delay:.1f}s...")
                    time.sleep(delay)

            print("\n" + "=" * 65)
            print(f"[INFO] 多城市采集完成，原始记录总计: {len(all_records)} 条")

        except Exception as e:
            print(f"[ERROR] Selenium 爬取异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            driver.quit()

        return all_records

    def _scrape_keyword(
        self,
        driver,
        keyword: str,
        city_name: str,
        city_code: str,
    ) -> list:
        """
        爬取单个城市 × 单个关键词的搜索结果，支持翻页与重试。

        URL 构造方式：
          SEARCH_URL_TEMPLATE.format(
              keyword = URL编码的关键词,
              city_code = 51job城市代码（如 "030200" 代表广州）
          )
          示例：https://we.51job.com/pc/search?keyword=Python数据分析
                &searchType=2&jobArea=030200

        Args:
            driver:    Chrome WebDriver 实例
            keyword:   搜索关键词
            city_name: 城市名称（注入到每条记录的 city 字段）
            city_code: 51job 城市代码（注入到搜索 URL）

        Returns:
            该城市 × 该关键词下所有页的职位记录列表（每条含 city 字段）
        """
        records = []
        encoded_kw = urllib.parse.quote(keyword)

        # ── 城市 URL 构造（核心改动：jobArea 参数） ───────────────────────────
        search_url = SEARCH_URL_TEMPLATE.format(
            keyword=encoded_kw,
            city_code=city_code,
        )

        # 带重试的页面加载
        loaded = False
        for attempt in range(1, MAX_RETRIES_PER_KEYWORD + 1):
            try:
                driver.get(search_url)
                try:
                    WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".joblist-item")
                        )
                    )
                    loaded = True
                    break
                except Exception:
                    try:
                        WebDriverWait(driver, 8).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, ".jname")
                            )
                        )
                        loaded = True
                        break
                    except Exception:
                        pass

                if not loaded and attempt < MAX_RETRIES_PER_KEYWORD:
                    time.sleep(random.uniform(5, 8))
                    driver.get("https://we.51job.com/pc/search?keyword=Python")
                    time.sleep(3)

            except Exception as e:
                if attempt < MAX_RETRIES_PER_KEYWORD:
                    time.sleep(random.uniform(5, 8))

        if not loaded:
            return records

        # 解析第 1 页
        time.sleep(2)
        page_records = self._parse_current_page(driver, city_name)
        records.extend(page_records)

        # 翻页
        for page_num in range(2, MAX_PAGES_PER_KEYWORD + 1):
            try:
                page_buttons = driver.find_elements(
                    By.CSS_SELECTOR, ".el-pager .number"
                )
                if not page_buttons:
                    break

                target_btn = None
                for btn in page_buttons:
                    if btn.text.strip() == str(page_num):
                        target_btn = btn
                        break

                if target_btn is None:
                    next_btns = driver.find_elements(
                        By.CSS_SELECTOR, ".btn-next"
                    )
                    if next_btns:
                        target_btn = next_btns[0]
                    else:
                        break

                driver.execute_script("arguments[0].click();", target_btn)
                time.sleep(4)

                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".joblist-item")
                        )
                    )
                except Exception:
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, ".jname")
                            )
                        )
                    except Exception:
                        break

                time.sleep(2)
                page_records = self._parse_current_page(driver, city_name)
                if not page_records:
                    break
                records.extend(page_records)

            except Exception:
                break

        return records

    def _parse_current_page(self, driver, city_name: str) -> list:
        """解析当前页面的职位列表，传入 city_name 注入到每条记录。"""
        records = []
        items = driver.find_elements(By.CSS_SELECTOR, ".joblist-item")
        for item in items:
            try:
                record = self._extract_job_record(item, city_name)
                if record and record.get("job_title"):
                    records.append(record)
            except Exception:
                continue
        return records

    def _extract_job_record(self, item, city_name: str) -> dict:
        """
        从单个职位元素提取数据，并注入 city 字段。

        优先使用 sensorsdata 属性（JSON 格式，字段最完整），
        回退到 CSS 选择器提取基本字段。
        """
        # ── 策略1：sensorsdata JSON 属性 ─────────────────────────────────────
        inner = item.find_elements(By.CSS_SELECTOR, ".joblist-item-job")
        if inner:
            sdata = inner[0].get_attribute("sensorsdata")
            if sdata:
                try:
                    data = json.loads(sdata)
                    job_title  = data.get("jobTitle", "")
                    salary     = data.get("jobSalary", "")
                    location   = data.get("jobArea", "")
                    experience = data.get("jobYear", "")
                    education  = data.get("jobDegree", "")

                    company = ""
                    cname_els = item.find_elements(By.CSS_SELECTOR, ".cname")
                    if cname_els:
                        company = (
                            cname_els[0].get_attribute("title")
                            or cname_els[0].text
                        ).strip()

                    industry = ""
                    dc_els = item.find_elements(By.CSS_SELECTOR, ".dc")
                    if dc_els:
                        industry = dc_els[0].text.strip()

                    if job_title:
                        return {
                            "city":       city_name,           # ← 新增城市字段
                            "job_title":  job_title.strip(),
                            "company":    company,
                            "salary":     salary.strip(),
                            "location":   self._clean_location(location),
                            "experience": experience.strip(),
                            "education":  education.strip(),
                            "industry":   industry.strip(),
                        }
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

        # ── 策略2：CSS 选择器回退 ─────────────────────────────────────────────
        job_title = ""
        jname_els = item.find_elements(By.CSS_SELECTOR, ".jname")
        if jname_els:
            job_title = jname_els[0].get_attribute("title") or jname_els[0].text

        salary = ""
        sal_els = item.find_elements(By.CSS_SELECTOR, ".sal")
        if sal_els:
            salary = sal_els[0].text.strip()

        company = ""
        cname_els = item.find_elements(By.CSS_SELECTOR, ".cname")
        if cname_els:
            company = (
                cname_els[0].get_attribute("title") or cname_els[0].text
            ).strip()

        location = ""
        area_els = item.find_elements(By.CSS_SELECTOR, ".area")
        if area_els:
            location = area_els[0].text.strip()

        industry = ""
        dc_els = item.find_elements(By.CSS_SELECTOR, ".dc")
        if dc_els:
            industry = dc_els[0].text.strip()

        if job_title:
            return {
                "city":       city_name,           # ← 新增城市字段
                "job_title":  job_title.strip(),
                "company":    company,
                "salary":     salary,
                "location":   self._clean_location(location),
                "experience": "",
                "education":  "",
                "industry":   industry,
            }
        return {}

    @staticmethod
    def _clean_location(location: str) -> str:
        """清洗地区字段，提取城市名（去除区县后缀）。"""
        if not location:
            return ""
        if "·" in location:
            return location.split("·")[0].strip()
        return location.strip()

    # ──────────────────────────────────────────────────────────────────────────
    # 仿真降级通道（多城市扩展版）
    # ──────────────────────────────────────────────────────────────────────────
    def _generate_simulated_dataset(self) -> list:
        """
        生成覆盖四城市的高仿真测试数据。

        各城市薪资特征：
          北京 —— AI/大厂聚集，薪资最高（系数 1.15）
          上海 —— 金融科技/外资，薪资次高（系数 1.10）
          深圳 —— 硬件/通信/创业，薪资中等偏高（系数 1.05）
          广州 —— 互联网/外贸/制造，薪资适中（系数 0.90）
        """
        # 基础职位数据池（salary 字段为北京基准值）
        jobs_pool = [
            ("高级数据分析师", "字节跳动",  "18k-30k",  "1-3年",  "本科", "互联网"),
            ("AI算法研究员",   "腾讯科技",  "35k-65k",  "3-5年",  "硕士", "人工智能"),
            ("大模型科学家",   "百度网讯",  "50k-90k",  "5-10年", "博士", "人工智能"),
            ("数据产品经理",   "网易游戏",  "15k-28k",  "3-5年",  "本科", "游戏开发"),
            ("Python工程师",   "极客软件",  "8k-15k",   "1-3年",  "本科", "软件外包"),
            ("初级数据专员",   "创新科技",  "5k-9k",    "无经验", "大专", "软件外包"),
            ("机器学习架构师", "阿里巴巴",  "40k-70k",  "5-10年", "博士", "云计算"),
            ("大数据开发工程师","京东科技", "20k-35k",  "3-5年",  "本科", "电子商务"),
            ("金融定量分析师", "平安科技",  "22k-42k",  "3-5年",  "硕士", "金融科技"),
            ("系统运维工程师", "中兴通讯",  "10k-18k",  "1-3年",  "本科", "通信设备"),
            ("算法工程师",     "华为技术",  "25k-50k",  "3-5年",  "硕士", "通信设备"),
            ("数据仓库工程师", "美团点评",  "18k-32k",  "1-3年",  "本科", "生活服务"),
            ("NLP工程师",      "科大讯飞",  "20k-38k",  "3-5年",  "硕士", "人工智能"),
            ("CV算法工程师",   "商汤科技",  "30k-55k",  "3-5年",  "硕士", "人工智能"),
            ("BI数据分析师",   "顺丰速运",  "12k-22k",  "1-3年",  "本科", "物流仓储"),
        ]

        # 各城市相对薪资系数与典型雇主
        city_profiles = {
            "广州": {
                "factor": 0.90,
                "companies": ["腾讯音乐", "广汽研究院", "唯品会", "YY直播",
                              "网易互娱", "OPPO", "TCL科技", "微盟集团"],
            },
            "北京": {
                "factor": 1.15,
                "companies": ["字节跳动", "百度网讯", "京东科技", "美团点评",
                              "滴滴出行", "小米科技", "快手科技", "旷视科技"],
            },
            "上海": {
                "factor": 1.10,
                "companies": ["蚂蚁集团", "拼多多", "携程网络", "上汽集团",
                              "陆金所", "喜马拉雅", "哔哩哔哩", "复星集团"],
            },
            "深圳": {
                "factor": 1.05,
                "companies": ["华为技术", "腾讯科技", "大疆创新", "平安科技",
                              "中兴通讯", "比亚迪", "微众银行", "欢聚集团"],
            },
        }

        random.seed(42)
        all_records = []

        for city_name, profile in city_profiles.items():
            factor = profile["factor"]
            companies = profile["companies"]

            for _ in range(40):          # 每城市生成 40 条，合计 160 条
                base = random.choice(jobs_pool)
                # 薪资乘以城市系数后重构字符串
                try:
                    parts = base[2].replace("k", "").split("-")
                    lo = round(float(parts[0]) * factor, 1)
                    hi = round(float(parts[1]) * factor, 1)
                    salary_str = f"{lo}k-{hi}k"
                except Exception:
                    salary_str = base[2]

                # 随机注入少量噪点（约 8%）
                if random.random() < 0.08:
                    salary_str = "暂无数据"

                all_records.append({
                    "city":       city_name,
                    "job_title":  base[0],
                    "company":    random.choice(companies),
                    "salary":     salary_str,
                    "location":   city_name,
                    "experience": base[3],
                    "education":  base[4],
                    "industry":   base[5],
                })

        random.shuffle(all_records)
        return all_records

    # ──────────────────────────────────────────────────────────────────────────
    # 统一入口
    # ──────────────────────────────────────────────────────────────────────────
    def scrape_data(self) -> int:
        """
        爬虫控制核心，含两级降级保障。
        use_simulation=False（默认）→ Selenium 真实爬取四城市
        use_simulation=True       → 直接使用高仿真数据（离线调试）
        """
        try:
            if self.use_simulation:
                print("[INFO] 仿真模式，使用内置四城市测试数据。")
                dataset = self._generate_simulated_dataset()
            else:
                dataset = self._scrape_with_selenium()
                if not dataset:
                    print("\n[WARN] 真实爬取未获得数据，自动降级至仿真通道。")
                    print("  常见原因：① IP 被封禁 ② 网络白名单限制 ③ 页面结构变更")
                    dataset = self._generate_simulated_dataset()

            self.save_to_csv(dataset)
            source = "仿真" if (self.use_simulation or not dataset) else "真实"
            print(f"\n[完成] 共写入 {len(dataset)} 条{source}职位数据 → "
                  f"{self.data_store_path}")
            return len(dataset)

        except Exception as e:
            print(f"[ERROR] 抓取程序执行中断: {e}")
            import traceback
            traceback.print_exc()
            return 0

    def save_to_csv(self, dataset: list) -> None:
        """持久化至 CSV（UTF-8 BOM，兼容 Excel 直接打开）。"""
        # city 字段排在首列，便于数据浏览时一眼识别来源城市
        keys = [
            "city", "job_title", "company", "salary",
            "location", "experience", "education", "industry",
        ]
        with open(self.data_store_path, "w", newline="",
                  encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dataset)
        print(f"[INFO] 已写入 → {self.data_store_path}")


# ── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 网络受限的沙箱/CI 环境请改为 use_simulation=True
    agent = JobCrawlerAgent(use_simulation=False)
    count = agent.scrape_data()
    print(f"[完成] 原始招聘数据 {count} 条，已存入 raw_recruitment_data.csv")