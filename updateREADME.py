# coding:utf-8
import feedparser
import requests
from lxml import etree
from bs4 import BeautifulSoup
import time


class oneday():
    url = 'http://wufazhuce.com/'
    res = ''
    date = ''
    html = ''

    def __init__(self):
        self.res = requests.get(self.url)
        self.date = time.strftime("%y%m%d", time.localtime())
        self.html = etree.HTML(self.res.text)

    def imgSave(self):
        img_src = self.html.xpath("//*[contains(@class,'fp-one')]//img/@src")
        active_img = self.date+"\t"+img_src[0]
        active_img_res = requests.get(img_src[0])
        # download_path = './image/' + time.strftime("%y%m%d", time.localtime()) + '.jpeg'
        try:
            with open('one_img.txt', 'a', encoding='utf-8') as f:
                f.write(active_img)
                f.write('\n')
            # print('{}保存成功！'.format(time.strftime("%y%m%d", time.localtime())))
        except Exception as ex:
            print('保存出了点问题哦{}'.format(ex))
        print(active_img)

    def txtSave(self):
        title = self.html.xpath("//*[contains(@class,'fp-one-cita')]//a")
        active_tile = self.date+"\t"+title[0].text
        print(active_tile)
        try:
            with open('one_title.txt', 'a', encoding='utf-8') as f:
                f.write(active_tile)
                f.write('\n')
            # print('{}保存成功！'.format(time.strftime("%y%m%d", time.localtime())))
        except Exception as ex:
            print('保存出了点问题哦{}'.format(ex))


def fetch_blog_entries():
    entries = feedparser.parse("https://tianwen42.top/atom.xml")["entries"]
    return [
        {
            "title": entry["title"].split(" - ")[0].replace("[原]", ""),
            "url": entry['link'],
            "published": entry["published"].split("T")[0],
        }
        for entry in entries
    ]


if __name__ == '__main__':
    with open('template.md', 'r', encoding='utf-8') as f:
        template = f.read()

    entries = fetch_blog_entries()[:7]
    entries_md = "\n".join(
        ['''- <a href='{url}' target='_blank'><b>{title}</b></a>'''.format(
            **entry) for entry in entries]
    )
    print(entries_md)
    readme = template.replace("$$RecentBlog$$", entries_md)

    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    # 每日一句，一天一次，不要对人家的服务器造成太大压力
    today = oneday()
    today.imgSave()
    today.txtSave()
