import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime
import logging
import io
import sys
import time

OPTIONSFILE = 'optionsData.txt'
# OPTIONSFILE = 'optionsDataTest.txt'  #test file
OPTIONSFILETEST = 'optionsDataTest.txt'  # test file
# Retrieve the logger instance
logger = logging.getLogger()

logger.setLevel(logging.INFO)
# logger.setLevel(logging.DEBUG)
#PERF = True
PERF = False

HEADER = "   Stock DTE CurrPrice OptsPrice Type Status %OTM Prem"
date_format = "%Y/%m/%d"
today = datetime.today()
logging.debug(today)
isAWS = True
yPrice = {}
spanReCompile = re.compile(r'[><]')


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

    r = run2()
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
    logging.debug("yScrape2 enter")
    url = "https://finance.yahoo.com/quote/" + stock
    response = requests.get(url)
    if PERF:
        logging.info("PERFM: request: " + str(time.time() - enter))

    soup = BeautifulSoup(response.text, "lxml")
    #soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup.find_all('span'):
        logging.debug(tag)
        z = re.search(r"data-reactid=\"14\"", str(tag))
        # logging.debug("re: " + str(z))
        if z:
            # logging.debug("z: " + str(z))
            if PERF:
                end = time.time()
                delta = end - enter
                logging.info("PERFM: yScrape2: " + str(delta))

            return str(tag)
            break

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


def run2():
    # TODO fix duplicate code

    # load from db
    data = getFromDynamo()
    stockOptionsList = []

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


if __name__ == '__main__':
    isAWS = False
    requestJson = False
    if len(sys.argv) == 2:
        if sys.argv[1] == '-json':
            logging.debug("request for json output")
            requestJson = True
    r = run(requestJson)
    if requestJson:
        # logging.debug("r: " + str(len(r)))
        print(json.dumps(r))
    else:
        print(r)
