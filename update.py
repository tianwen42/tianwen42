# import feedparser
import requests
from lxml import etree
import datetime
from bs4 import BeautifulSoup
import time

token = ''
current_date = datetime.datetime.now().strftime('%Y%m%d')
top_repo_num = 10
recent_repo_num = 10

def update_oneday():
    # 每日一句，一天一次，不要对人家的服务器造成太大压力
    res = requests.get('http://wufazhuce.com/')
    active_img = current_date + "\t" + etree.HTML(res.text).xpath("//*[contains(@class,'fp-one')]//img/@src")[0]
    try:
        with open('one_img.txt', 'a', encoding='utf-8') as f:
            f.write(active_img)
            f.write('\n')
    except Exception as ex:
        print('保存出了点问题哦{}'.format(ex))
    print(active_img)

    active_tile = current_date + "\t" + etree.HTML(res.text).xpath("//*[contains(@class,'fp-one-cita')]//a")[0].text
    try:
        with open('one_title.txt', 'a', encoding='utf-8') as f:
            f.write(active_tile)
            f.write('\n')
    except Exception as ex:
        print('保存出了点问题哦{}'.format(ex))
    print(active_tile)

def main() -> None:
    update_oneday()

if __name__ == '__main__':
    main()

