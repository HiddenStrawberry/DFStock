# encoding=utf8
import threading
import re
import requests
import time
import json
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from flask import Flask, render_template, session, redirect, url_for, flash
import sys

default_encoding = 'utf-8'
if sys.getdefaultencoding() != default_encoding:
    reload(sys)
    sys.setdefaultencoding(default_encoding)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'JDILOVEYOU'


class SQLForm(FlaskForm):
    ddurl = StringField('URL', validators=[DataRequired()])
    submit = SubmitField('Submit')


@app.route('/', methods=['GET', 'POST'])
def setup():

    form = SQLForm()
    try:
        from config import ddurl
    except:
        ddurl = ''
        flash('请输入钉钉机器人地址！'.decode('utf8'))
    if form.validate_on_submit():

        ddurl = form.ddurl.data

        try:
            a = 'ddurl=\'' + ddurl + '\''
            open('config.py', 'w').write(a)
            flash('config.py写入成功！'.decode('utf8'))
            time.sleep(5)
            threading.Thread(target=proj_thread).start()
        except Exception as err:
            print err
            flash('config.py写入失败！'.decode('utf8'))
        return redirect(url_for('setup'))
    return render_template('config.html',form=form,ddurl=ddurl)


cwjs = 0
cwys = 0
save = []


def estimate(a):
    # 仓位预估函数
    dict = []
    if len(a) < 2:
        return False
    xz = 0
    while not dict:
        for x in range(10000, 800000):
            stockamount = {}
            k = 0
            for each in range(len(a)):
                stockamount[each] = x * a[each][1] / a[each][0]
            for each in stockamount:
                if int(stockamount[each] % 100) <= xz or int(stockamount[each] % 100) >= 100 - xz:
                    k = k + 1

            if k == len(a):
                dict.append(x)
        xz = xz + 1
    return [min(dict), max(dict)]


def average_cw(url):
    html = requests.get(url).text
    url = re.findall('otherGroup.html\?zjzh=(.*?)"', html, re.S)
    cw_total = 0
    for x in range(20):
        userjson = 'http://spdsqry.eastmoney.com/rtcs1?type=rtcs_zuhe_home&zh=' + str(
            url[x]) + '&khqz=128&recCnt=6&reqUserid=&cb=jQuery1113014730422553502032_1495081469690&_=1495081469691'
        json_str = json.loads(re.findall('\((.*?)\)', requests.get(userjson).text, re.S)[0])
        cw = json_str['data']['detail']['cw']
        cw_total = cw_total + float(cw)
    return cw_total / 20


def update_cw():
    global cwjs
    global cwys
    while 1 == 1:
        try:
            cwjs = average_cw('http://contest.eastmoney.com/dmjs/rank.html')
            cwys = average_cw('http://contest.eastmoney.com/dmys/rank.html')
        except:
            pass


class Stock:
    def __init__(self):
        print 'Init'

    def load_user_stock(self, userid):
        userjson = 'http://spdsqry.eastmoney.com/rtcs1?type=rtcs_zuhe_detail&zh=' + userid + '&khqz=127&reqUserid=&userId=null&cb=jQuery111302980358468440536_1493981741883&_=1493981741884'
        json_str = json.loads(re.findall('\((.*?)\)', requests.get(userjson).text, re.S)[0])
        stockhold = json_str['data']['stkhold']
        stocklist = []
        for am in range(len(stockhold)):
            try:
                rate = float(stockhold[am]['webYkRate'])
            except:
                rate = ''
            stock_dict = {
                'code': stockhold[am]['__code'],  # 股票代码
                'name': stockhold[am]['__name'],  # 股票名字
                'price': stockhold[am]['__zxjg'],  # 股票现价
                'per': float(stockhold[am]['holdPos']) / 100,  # 股票盈亏比例
                'rate': rate  # 股票仓位
            }
            stocklist.append(stock_dict)
        return stocklist

    def get_rank(self, rankurl, low_rank, args):
        rank_list = []
        html = requests.get(rankurl).text
        t = re.findall('<div class="deta deta2" id="data_gaoshou">(.*?)</a></li></ul></div>', html, re.S)[0]
        ul = re.findall('<ul class(.*?)</ul>', t, re.S)
        for each in ul:
            rank = re.findall('<span>(.*?)</span>', each, re.S)[2]
            if int(rank) < low_rank:
                action = re.findall('<span class="(.*?)"', each, re.S)[0]
                if action == 'red':
                    action = '买入'
                if action == 'green':
                    action = '卖出'
                rank_dict = {
                    'date': re.findall('"margin-right: 5px;">(.*?)</span>', each, re.S)[0],
                    'time': re.findall('<span>(.*?)</span>', each, re.S)[0],
                    'userid': re.findall('zjzh=(.*?)"', each, re.S)[0],
                    'userurl': 'http://contest.eastmoney.com/dmjs/otherGroupDetail.html?zjzh=' +
                               re.findall('zjzh=(.*?)"', each, re.S)[0],
                    'username': re.findall('target="_blank">(.*?)</a>', each, re.S)[0],
                    'action': action.decode('utf8'),
                    'args': args.decode('utf8'),
                    'rank': rank,
                    'stock': re.findall('data-client="true">(.*?)</a>', each, re.S)[0],
                    'price': re.findall('<span>(.*?)</span>', each, re.S)[1]
                }
                rank_list.append(rank_dict)
        return rank_list

    def rank_msg_dd(self, rank_list, url):
        a = {}
        for each in rank_list:
            a = threading.Thread(target=self.rank_msg_dd_each, args=(each, url,))
            a.start()
            a.join()

    def rank_msg_dd_each(self, each, url):
        text = '### ' + each['date'] + ' ' + each['time'] + '\n' + '##### ' + each['args'] + '排名:'.decode(
            'utf8') + each['rank'] + ' **' + each['action'] + '** **' + each['stock'] + '** **' + each[
                   'price'] + '** ' + each['username'] + '\n'
        usr_stock = self.load_user_stock(each['userid'])
        for each_stock in usr_stock:
            msg = '当前持仓股票代码 :'.decode('utf8') + each_stock['code'] + '\n' + \
                  '> ' + '持仓股票名 :'.decode('utf8') + each_stock['name'] + '\n' + \
                  '> ' + '**最新价** :'.decode('utf8') + each_stock['price'] + '\n' + \
                  '> ' + '**仓位百分比** :'.decode('utf8') + str(each_stock['per']) + '\n' + \
                  '> ' + '**盈亏比例** :'.decode('utf8') + str(each_stock['rate']) + '\n\n'
            text = text + msg
        try:

            result = [each['date'], each['time'], each['args'], each['rank'], each['action'], each['stock'],
                      each['price'], each['username'], str(usr_stock), each['userurl'], each['userid']]
            self.write_msg_list('Thanks for using', result)
            gs = str(estimate(self.holdPos(usr_stock)))
            if gs == 'False':
                gs = '仓位过低无法估算'.decode('utf8')

            gstext = '**预估资金量范围** :'.decode('utf8') + gs + '\n\n' + \
                     '当前决赛前20名平均仓位百分比：'.decode('utf8') + str(cwjs) + '\n\n' + \
                     '当前预赛前20名平均仓位百分比：'.decode('utf8') + str(cwys) + '\n\n'
            text = text + gstext + '[查看个人信息]'.decode('utf8') + '(' + each['userurl'] + ')'
            self.dd_msg(url, each['args'] + '排名'.decode('utf8') + each['rank'] + '名的新交易信息！'.decode('utf8'), text)
        except Exception as err:
            print '钉钉机器人设置错误！'

    def holdPos(self, stocklist):
        k = {}
        p = 0
        for each in stocklist:
            k[p] = [float(each['price']), each['per']]
            p = p + 1
        return k

    def write_msg_list(self, query, list):
        global save
        if list in save:
            raise Exception('error')
        else:
            save.append(list)

    def dd_msg(self, url, title, text):
        headers = {"Content-Type": "application/json; charset=utf-8"}
        datax = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text
            }
        }
        print requests.post(url, data=json.dumps(datax), headers=headers).text


def proj_thread():
    from config import ddurl
    t = Stock()
    time.sleep(10)
    while 1 == 1:
        try:
            for x in range(5):
                print x
                t.rank_msg_dd(
                    t.get_rank('http://contest.eastmoney.com/dmys/rank_gs_' + str(x) + '.html', 15, '预赛'),
                    ddurl
                )
                t.rank_msg_dd(
                    t.get_rank('http://contest.eastmoney.com/dmjs/rank_gs_' + str(x) + '.html', 15, '决赛'),
                    ddurl
                )
        except Exception as err:
            print err


if __name__ == '__main__':
    threading.Thread(target=update_cw).start()
    app.run()
