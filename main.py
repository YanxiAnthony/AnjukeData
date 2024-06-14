from lxml import etree
import requests
from fake_useragent import UserAgent
import csv
import re
import json

# 创建文件对象
f = open('安居客网楼盘信息.csv', 'w', encoding='utf-8-sig', newline="")  # 创建文件对象
csv_write = csv.DictWriter(f, fieldnames=['楼盘名称', '楼盘地址', '楼盘评分', '社区品质', '楼盘户型', '交通出行',
                                          '楼盘售价', '楼盘标签', '经度', '纬度'])
csv_write.writeheader()

# 设置请求头参数：User-Agent, cookie, referer
ua = UserAgent()
headers = {
    # 随机生成User-Agent
    "user-agent": ua.random,
    # "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # 设置从何处跳转过来
    "referer": "https://m.anjuke.com/xm/loupan/?jump=site",
}

ip_count = 0
ip_cache = None


# 从代理IP池，随机获取一个IP，比如必须ProxyPool项目在运行中
def get_proxy(proxy_pool_url):
    global ip_count, ip_cache
    ip_count += 1
    if ip_count % 6 != 0 and ip_cache:
        return ip_cache
    try:
        response = requests.get(proxy_pool_url)
        if response.status_code == 200:
            ip_cache = response.text
            print(f"获取新IP：{response.text}")
            return response.text
    except ConnectionError:
        if ip_cache:
            print("缓存ip：", ip_cache)
            return ip_cache
        else:
            print("警告：无法获取新IP，并且没有可用的缓存")
            return None


# 解析二级页面函数
def parse_message(url, proxies):
    dict_result = {'楼盘名称': '-', '楼盘地址': '-', '楼盘评分': '-', '社区品质': '-',
                   '楼盘户型': '-', '交通出行': '-', '楼盘售价': '-', '楼盘标签': '-',
                   '经度': '-', '纬度': '-'}
    try:
        text = requests.get(url=url, headers=headers, proxies=proxies).text
        # 检查是否被重定向到登录或验证码页面
        if 'https://callback.58.com/antibot/verifycode?' in text or 'https://sh.fang.anjuke.com/xinfang/captchaxf-verify/' in text or "https://m.anjuke.com/xinfang/captchaxf-verify/" in text:
            print("遇到登录或验证码验证，暂停操作，问题链接：", url)
            input("请在浏览器中完成人工操作后，按回车键继续...")
            return url  # 重新尝试抓取当前页面
        html = etree.HTML(text)

        dict_result['楼盘名称'] = html.xpath('.//div[@class="lpbase"]/div[@class="lptitle j-loupan-tlt"]/h1/text()')
        dict_result['楼盘标签'] = html.xpath('.//div[@class="lptags ui-box_group"]/em/text()')
        dict_result['楼盘地址'] = html.xpath('.//a[@class="ui-info adrr "]/p/text()') or html.xpath(
            './/a[@class="ui-info adrr soldout-bottom"]/p/text()')
        dict_result['楼盘售价'] = html.xpath(
            './/div[@class="avg-price-box"]/span[@class="value-info"]/b/text()') or html.xpath(
            './/div[@class="avg-price value-info"]/em/text()')
        dict_result['楼盘评分'] = html.xpath(
            './/div[@class="composite_score_top"]/span[@class="composite_score"]/text()')
        dict_result['社区品质'] = html.xpath(".//div[@class='loupan_evaluation_score_right']/div[1]/span[2]/text()")
        dict_result['楼盘户型'] = html.xpath(".//div[@class='loupan_evaluation_score_right']/div[2]/span[2]/text()")
        dict_result['交通出行'] = html.xpath(".//div[@class='loupan_evaluation_score_right']/div[3]/span[2]/text()")
        lng_lat_regex = r'lat:\s*\'(\d+\.\d+)\',\s*lng:\s*\'(\d+\.\d+)\''
        lng_lat_match = re.findall(lng_lat_regex, text)
        if lng_lat_match:
            lng, lat = lng_lat_match[0]
            dict_result['经度'] = f"{lng}"
            dict_result['纬度'] = f"{lat}"
        else:
            print("未能找到经纬度信息")

        # 对爬取到的数据进行简单预处理
        for key, value in dict_result.items():
            if key == '楼盘标签' or key == '经度' or key == '纬度':
                dict_result[key] = value
            else:
                value = list(map(lambda item: re.sub(r'\s+', '', item), value))  # 去掉换行符制表符
                dict_result[key] = list(filter(None, value))  # 去掉上一步产生的空元素
                if len(dict_result[key]) == 0:
                    dict_result[key] = ''
                else:
                    dict_result[key] = dict_result[key][0]

    except Exception as err:
        print("-----------------------------")
        print(err)
        return dict_result  # 返回默认字典，而不是url

    return dict_result


# 将数据读取到csv文件中
def save_csv(result):
    for row in result:  # 一个小区数据存放到一个字典中
        csv_write.writerow(row)


def get_city_id(city_name='上海'):
    # 读取并解析citylist.ini文件
    with open('citylist.txt', 'r', encoding='utf-8') as f:
        city_data = json.load(f)

    # 在城市数据中查找对应的城市ID
    for city_info in city_data.values():
        if city_info['city_name'] == city_name:
            return city_info['city_id']

    # 如果没有找到对应的城市ID，返回一个错误消息
    return None


def main():
    # 获取输入参数
    inputlist = getinput()

    city_id = inputlist[0]
    proxy = get_proxy(inputlist[1])
    page_num = inputlist[2]
    proxies = {"http": "http://{}".format(proxy)}

    k = 1  # 爬取房源条数
    for i in range(1, page_num):
        print("************************第{}页开始爬取************************".format(i))
        json_args = '{"cid":' + city_id + ',"page":"' + str(i) + '","pageSize":20}'
        url = f"https://m.anjuke.com/xinfang/api/loupan/list/?client_source=2&args={json_args}"
        # 发送HTTP请求并获取JSON数据
        response = requests.get(url=url, headers=headers, proxies=proxies)
        # 检查是否被重定向到登录或验证码页面
        text = response.text
        if 'https://callback.58.com/antibot/verifycode' in text or 'CAPTCHA' in text or "https://m.anjuke.com/xinfang/captchaxf-verify/" in text:
            print("遇到登录或验证码验证，暂停操作，问题链接：", url)
            input("请在浏览器中完成人工操作后，按回车键继续...")
        data = response.json()

        # 提取所有loupan_id
        try:
            loupan_ids = [row['loupan_id'] for row in data['result']['rows']]
        except KeyError as e:
            print(f"JSON响应中缺少键'{e}'，响应数据：{data}")
            loupan_ids = []
        if not loupan_ids:
            break
        list_result = []  # 将字典数据存入到列表中
        for id in loupan_ids:
            try:
                url = "https://m.anjuke.com/xm/loupan/{}/".format(id)
                # 解析二级页面函数，分别传入详情页URL和均价两个参数
                result = parse_message(url, proxies)
                list_result.append(result)
                print(url)
                print("已爬取{}条数据".format(k))
                k = k + 1  # 控制爬取的小区数
            except Exception as err:
                print("-----------------------------")
                print(err)
        # 保存数据到文件中
        save_csv(list_result)
    print("************************爬取成功************************")


def getinput():
    # 获取用户输入的城市名称
    while True:
        city_name = input("请输入城市名称：").strip()
        if not city_name:
            city_id = '46'
            break
        else:
            city_id = get_city_id(city_name)
            if not city_id:
                print("未找到该城市，请重新输入。")
            else:
                break

    proxy = input("请输入代理链接：") or None

    while True:
        page_num_str = input("请输入需要爬取的页数：").strip()  # 去除前后空白字符
        if not page_num_str:
            page_num_str = "0"
        try:
            page_num = int(page_num_str)  # 转换为整数
            if page_num < 0:
                print("页数不能为负数，请重新输入。")
            else:
                break
        except ValueError:
            print("输入的不是整数，请重新输入。")

    if not proxy:
        proxy = 'url'
    return city_id, proxy, page_num + 1


if __name__ == "__main__":
    main()
