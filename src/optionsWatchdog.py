import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime
import logging
import io
import time
from multiprocessing import Process, Pipe
import os

DEBUG = os.getenv('DEBUG', default=0)
logger = logging.getLogger()
if DEBUG == "1":
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
PERF = False
#PERF = True
date_format = "%Y/%m/%d"
today = datetime.today()
logging.debug(today)
isAWS = True
yPrice = {}
spanReCompile = re.compile(r'[><]')

#concurrency: increasing lambda memory made multi thread possible. Env var set at 10
CONCURRENCY_SIZE = os.getenv('CONCURRENCY_SIZE', default=2)
CONCURRENCY_SIZE = int(CONCURRENCY_SIZE)
logging.info("CONCURRENCY_SIZE: " + str(CONCURRENCY_SIZE))

class StockIndex:
    name = ""
    price = ""
    change = ""

    def toJson(self):
        j = {}
        j['name'] = self.name
        j['price'] = self.price
        j['change'] = self.change
        return j


class StockOpt:
    name = ""
    currentPrice = 0
    optsPrice = 0
    optType = ""
    IOTM = ""
    pctIOTM = 0
    expirationDate = ""
    DTE = 0
    premium = 0
    alert = "n"
    breakEvenNet = 0
    coveredCall = "n"

    def calcPct(self, bid):
        optionsType = self.optType
        optionsPrice = self.optsPrice
        pctIOTM = 0

        if optionsType == "put":
            if optionsPrice < bid:
                IOTM = "OTM"
                pctIOTM = (1 - optionsPrice / bid) * 100
            else:
                IOTM = "ITM"
        else:
            # calls
            if optionsPrice > bid:
                # OTM
                IOTM = "OTM"
                pctIOTM = (optionsPrice / bid - 1) * 100
            else:
                IOTM = "ITM"
                pctIOTM = (bid / optionsPrice - 1) * 100
        return [IOTM, pctIOTM]

    def alerted(self):
        logging.debug("alerted: IOTM: " + self.IOTM + "; pct: " + str(self.pctIOTM))
        alert = 2
        if self.IOTM == "ITM":
            alert = 0

        if self.IOTM == "OTM":
            if self.pctIOTM < 4:
                alert = 0
            else:
                if self.pctIOTM < 6:
                    alert = 1

        return alert

    def toString(self):
        logging.debug("stockOptions.toString enter")
        alert = alerted(self)
        if alert == 0:
            alert = "***"
        if alert == 1:
            alert = "---"
        else:
            alert = ""

        return "{:3} {:4} {:3} {:>7} {:>7} {:4} {:3} {:>.0f}% {:5}".format(alert, self.name, self.DTE,
                                                                           self.currentPrice, str(self.optsPrice),
                                                                           self.optType, self.IOTM, self.pctIOTM,
                                                                           self.premium)

    def toJson(self):
        logging.debug("stockOptions.toJson enter")

        j = {}
        j['alert'] = self.alerted()
        j['name'] = self.name
        j['DTE'] = self.DTE
        j['price'] = self.currentPrice
        j['optionsPrice'] = self.optsPrice
        j['type'] = self.optType
        j['IOTM'] = self.IOTM
        j['pctIOTM'] = "{:>.0f}%".format(self.pctIOTM)
        j['premium'] = self.premium
        j['expirationDate'] = self.expirationDate
        j['breakEvenNet'] = self.breakEvenNet
        j['coveredCall'] = self.coveredCall
        return j


def respondWithError(message):
    return {
        'statusCode': 503,
        'body': json.dumps(message)
    }

def lambda_handler(event, context):
    logging.debug("lambda_handler enter")
    logger.debug('## EVENT')
    logger.debug(event)
    yPrice.clear()
    #TODO this errors out if requestJson or NO params are sent in URL
    if 'queryStringParameters' in event and 'getIndexes' in event['queryStringParameters']:
        r = runIndexes()
        return {
            'statusCode': 200,
            'body': json.dumps(r)
        }

    r = runMP()
    return {
        'statusCode': 200,
        'body': json.dumps(r)
    }

def runIndexes():
    indexes = ["^VIX", "^GSPC"]
    id = "16"
    ilist = []
    for index in indexes:
        r = yScrape3(index, id)
        r2 = parseBid3(r)
        i = StockIndex()
        i.name = index
        i.price = r2[0]
        i.change = r2[1]
        ilist.append(i.toJson())

    return ilist

def yScrape3(stock, id):
    url = "https://finance.yahoo.com/quote/" + stock
    # url = "https://finance.yahoo.com/quote/^VIX"

    r = requests.get(url)
    # print("status: ", r.status_code)

    soup = BeautifulSoup(r.text, "html.parser")

    for tag in soup.find_all('span'):
        z = re.search(r"data-reactid=\"" + id + "\"", str(tag))
        # print("re: " + str(z))
        if z:
            # print("found it")
            # print(str(tag))
            return (str(tag))
            break


def parseBid3(b):
    # logging.debug("parseBid2: " + b)
    a = b.split('>')
    # logging.debug("a: " + a)
    b = a[1].split('<')
    # logging.debug("parseBid2: " + str(float(b[0])))
    a = b[0].split(" ")
    price = a[0]
    change = a[1].replace("(", "")
    change = change.replace(")", "")
    return [price, change]

# looks for data-reactid based on agent type
def yScrape2(stock):
    if PERF:
        enter = time.time()
    logging.debug("yScrape2 enter for " + stock)
    url = "https://finance.yahoo.com/quote/" + stock
    response = requests.get(url)
    logging.debug("yScrape2 response for " + stock)
    if PERF:
        logging.info("PERFM: request: " + str(time.time() - enter))
        enter = time.time()

    soup = BeautifulSoup(response.text, "lxml")
    #soup = BeautifulSoup(response.text, "html.parser")

    tag = soup.find_all('span', class_="Trsdu(0.3s) Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(b)")
    if PERF:
        logging.info("PERFM: yScrape2: " + str(time.time()-enter))
    if tag:
        return str(tag)

    #TODO ERROR handling
    logging.debug("no last price found")
    return "---"

def parseBid2(b):
    if PERF:
        enter = time.time()

    # logging.debug("parseBid2: " + b)
    try:
        q = spanReCompile.split(b)
        # a = b.split('>')
        # logging.debug("a: " + a)
        # b = a[1].split('<')
        # logging.debug("parseBid2: " + str(float(b[0])))
        if PERF:
            end = time.time()
            delta = end - enter
            logging.info("PERFM: parseBid2: " + str(delta))
        # return float(b[0].replace(",", ""))
        return float(q[2].replace(",", ""))
    except ValueError:
        logging.error("Could not convert bid: " + str(b))
        raise Exception("parsebid2: could not convert bid for " + b)
        # return 9999

def getFromDynamo():
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('Options')

    response = table.scan()
    data = response['Items']
    return data

def chunks(processes, maxThreads):
    for i in range(0, len(processes), maxThreads):
        yield processes[i:i+maxThreads]

#Run multiprocess scrape and parsing
def runMP():
    data = getFromDynamo()
    stockOptionsList = []
    stockList = []
    processes = []
    parentConnections = []
    starttime = time.time()
    #build list of stocks to scrape and parse
    for d in data:
        if d.get("name") not in stockList:
            stockList.append(d.get("name"))
    logger.debug("stockList::>")
    logger.debug(stockList)

    #start multiple processes to work on the list
    for stock in stockList:
        parent_conn, child_conn = Pipe()
        parentConnections.append(parent_conn)
        p = Process(target=bid_worker, args=(stock,child_conn))
        processes.append(p)

    #chunking is not efficient but AWS lambda doesn't support shared mem and associated mp methods
    for procSet in chunks(processes, CONCURRENCY_SIZE):
        logging.debug("procSet::")
        logging.debug(procSet)
        for proc in procSet:
            proc.start()
        logging.debug("chunk started")
        for proc in procSet:
            proc.join()
        logging.debug("chunk joined")
        #p.start()

    #assemble results and profit
    bids = {}
    for parentConnection in parentConnections:
        recv = parentConnection.recv()[0]
        a = recv.split(':')
        bids[a[0]] = float(a[1])

    logging.debug("bid results::>")
    logging.debug(bids)

    for d in data:
        logging.debug("d: ", d)
        so = StockOpt()
        so.name = d.get("name", "***")
        so.optType = d.get("type", "")
        so.optsPrice = float(d.get("optionsPrice", 9999))
        so.expirationDate = d.get("expirationDate", "1970/1/1")
        so.premium = d.get("premium", 0)
        a = datetime.strptime(so.expirationDate, date_format)
        so.DTE = (a - today).days + 1
        [so.IOTM, so.pctIOTM] = so.calcPct(bids[so.name])
        so.currentPrice = bids[so.name]
        if so.optType == "put":
            breakEvenNet = so.currentPrice - so.optsPrice + float(so.premium)
        else:
            breakEvenNet = so.optsPrice - so.currentPrice + float(so.premium)
        so.breakEvenNet = float("{0:.2f}".format(breakEvenNet))
        so.coveredCall = d.get("coveredCall", "n")

        stockOptionsList.append(so)
        logging.debug("so::")
        logging.debug(so)

    if PERF:
        logging.info("PERFM: scrape/parse time: " + str(time.time()-starttime))
    list = []
    # sort by ITM then DTE
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.pctIOTM)
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.DTE)
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.IOTM)

    for e in stockOptionsList:
        list.append(e.toJson())
    return list

def bid_worker(name, conn):
    logging.debug("bid_worker entered for " + name)
    r = yScrape2(name)
    logging.debug("bid_worker scraped " + name)
    conn.send([name + ":" + str(parseBid2(r))])
    conn.close()

if __name__ == '__main__':
    runMP()


