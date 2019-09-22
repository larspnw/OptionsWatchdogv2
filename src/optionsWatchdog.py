import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime
import logging
import io
import sys
import time
from multiprocessing import Process, Pipe
import os


OPTIONSFILE = 'optionsData.txt'
# OPTIONSFILE = 'optionsDataTest.txt'  #test file
OPTIONSFILETEST = 'optionsDataTest.txt'  # test file
# Retrieve the logger instance
logger = logging.getLogger()
logger.setLevel(logging.INFO)
#logger.setLevel(logging.DEBUG)
#PERF = False
PERF = True
HEADER = "   Stock DTE CurrPrice OptsPrice Type Status %OTM Prem"
date_format = "%Y/%m/%d"
today = datetime.today()
logging.debug(today)
isAWS = True
yPrice = {}
spanReCompile = re.compile(r'[><]')

#concurrency: increasing lambda memory made multi thread possible. Env var set at 10
CONCURRENCY_SIZE = os.environ['CONCURRENCY_SIZE']
if CONCURRENCY_SIZE is None:
    CONCURRENCY_SIZE = 2
else:
    CONCURRENCY_SIZE = int(CONCURRENCY_SIZE)
    logging.info("Read CONCURRENCY_SIZE")
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
    requestJson = False
    # try:
    if 'queryStringParameters' in event and 'getIndexes' in event['queryStringParameters']:
        r = runIndexes()
        return {
            'statusCode': 200,
            'body': json.dumps(r)
        }

    if 'queryStringParameters' in event and 'requestJson' in event['queryStringParameters']:
        rj = event["queryStringParameters"]["requestJson"]
        if str(rj) == "true":
            # logging.info("setting request for json")
            requestJson = True
    if 'queryStringParameters' in event and 'test' in event['queryStringParameters']:
        OPTIONSFILE = OPTIONSFILETEST
        logging.info("using test options file")

    r = runMP()
    if requestJson:
        return {
            'statusCode': 200,
            'body': json.dumps(r)

            # 'statusCode': 200,
            # 'body': r
        }


# except Exception as e:
# logging.error("Exiting with failure: " + e.message)
# respondWithError("Failure occurred: " + e.message)

def runIndexes():
    # TODO create array and loop thru array for indexes

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

    #for tag in soup.find_all('span'):
        #logging.debug(tag)
        #z = re.search(r"data-reactid=\"14\"", str(tag))
        ## logging.debug("re: " + str(z))
        #if z:
            ## logging.debug("z: " + str(z))
            #if PERF:
                #end = time.time()
                #delta = end - enter
                #logging.info("PERFM: bs scrape: " + str(delta))

            #return str(tag)
            #break
    #TODO ERROR handling
    logging.debug("no last price found")
    return "---"

# looks for Bid in span then reads price
def yScrape(stock):
    logging.debug("yScrape enter")
    bid = ""
    url = "https://finance.yahoo.com/quote/" + stock
    response = requests.get(url)

    soup = BeautifulSoup(response.text, "html.parser")

    isBid = False

    for tag in soup.find_all('span'):
        # logging.debug(tag)
        if isBid:
            bid = str(tag)
            isBid = False
            # that's all we're looking for - now
            logging.debug("Found bid: " + bid)
            break

        z = re.search(r"Bid", str(tag))
        if z:
            isBid = True;

    logging.debug("bid: " + stock + " -- " + bid)
    return bid


def loadOptionsData():
    if isAWS == True:
        import boto3
        s3 = boto3.client('s3')
        try:
            data = s3.get_object(Bucket='larsbucket1', Key=OPTIONSFILE)
            json_data = json.load(data['Body'])
            # json_data = json.load(data['Body'].read())
            return json_data
        except Exception as e:
            logging.critical(e)
            raise e

    else:
        logging.debug("loadOptionsData enter")
        try:
            with open(OPTIONSFILE) as json_file:
                data = json.load(json_file)
        except FileNotFoundError:
            print("Error: file not found: " + filename)
            logging.critical("Error: file not found: " + filename)
            exit(1)
        return data


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


def parseBid(b):
    try:
        a = b.split('>')
        b = a[1].split(' ')
        return float(b[0].replace(",", ""))
    except ValueError:
        logging.warning("Could not convert bid: " + str(b))
        return 9999


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

    #logging.debug("processes started")
    #for process in processes:
        #process.join()
    #logging.debug("processes joined")

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
        stockOptionsList.append(so)
        logging.debug(so)
        #TODO add breakeven obj here

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

def run2():
    # TODO fix duplicate code

    # load from db
    data = getFromDynamo()
    stockOptionsList = []

    #TODO - get all the stock symbols, multiproc the scrape and parse, build price map
    #then build SO objects

    for d in data:
        if PERF:
            dStart = time.time()
        logging.debug("d: ", d)
        stock = d.get("name", "***")
        optionsType = d.get("type", "")
        optionsPrice = float(d.get("optionsPrice", 9999))
        expDate = d.get("expirationDate", "1970/1/1")
        premium = d.get("premium", 0)

        try:
            if stock in yPrice:
                bid = yPrice[stock]
            else:
                r = yScrape2(stock)
                bid = parseBid2(r)
                yPrice[stock] = bid
        except:
            logging.warning("scrape and parsing failure for " + stock)
            return (respondWithError("scrape and parsing failure for " + stock))

        so = StockOpt()
        so.name = stock
        so.optType = optionsType
        so.currentPrice = bid
        so.optsPrice = optionsPrice
        so.expirationDate = expDate
        so.premium = premium
        a = datetime.strptime(expDate, date_format)
        so.DTE = (a - today).days + 1
        [so.IOTM, so.pctIOTM] = so.calcPct(bid)

        stockOptionsList.append(so)
        if PERF:
            logging.info("PERFM: stock=" + stock + " time: " + str(time.time() - dStart))

    if PERF:
        sortStart = time.time()
    # enumerate list
    list = []
    # sort by ITM then DTE
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.pctIOTM)
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.DTE)
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.IOTM)

    if PERF:
        sortDelta = time.time() - sortStart
        logging.info("PERFM sort: " + str(sortDelta))

    for e in stockOptionsList:
        list.append(e.toJson())
    return list


def run(requestJson):
    # read file into list
    data = loadOptionsData()
    logging.debug(json.dumps(data, indent=4))

    stockOptionsList = []

    for d in data["stock"]:
        stock = d.get("name", "***")
        optionsType = d.get("type", "")
        optionsPrice = float(d.get("price", 9999))
        expDate = d.get("date", "1/1/1970")
        premium = d.get("premium", 0)

        if stock in yPrice:
            bid = yPrice[stock]
        else:
            r = yScrape2(stock)
            bid = parseBid2(r)
            yPrice[stock] = bid

        so = StockOpt()
        so.name = stock
        so.optType = optionsType
        so.currentPrice = bid
        so.optsPrice = optionsPrice
        so.expirationDate = expDate
        so.premium = premium
        a = datetime.strptime(expDate, date_format)
        so.DTE = (a - today).days
        [so.IOTM, so.pctIOTM] = so.calcPct(bid)

        stockOptionsList.append(so)

    # enumerate list

    if requestJson == False:
        logger.info("no json response")
        # report stock, price, options, in/OTM, %OTM, DTE - sort by ITM, DTE
        output = io.StringIO()
        output.write(HEADER + "\n")
    list = []
    # sort by ITM then DTE
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.pctIOTM)
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.DTE)
    stockOptionsList.sort(key=lambda stockOptions: stockOptions.IOTM)
    # logging.debug("sorted: " + soSorted)
    for e in stockOptionsList:
        if requestJson:
            list.append(e.toJson())
        else:
            output.write(e.toString() + "\n")

    if requestJson:
        return list
    else:
        return output.getvalue()

def bid_worker(name, conn):
    logging.debug("bid_worker entered for " + name)
    r = yScrape2(name)
    logging.debug("bid_worker scraped " + name)
    conn.send([name + ":" + str(parseBid2(r))])
    conn.close()

if __name__ == '__main__':
    runMP()
    #stockName = ['GOOG', 'AMZN', 'MSFT', 'WORK']
    #p = multiprocessing.Pool(4)
    #start = time.time()
    #r = p.map(bid_worker, stockName)
    #print("time: " + str(time.time()-start))
    #print("r::>")
    #print(r)


