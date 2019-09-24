#from bs4 import BeautifulSoup
#import time
#import requests
#import re

PERF = True

def yScrape2(stock):
    if PERF:
        enter = time.time()
    #logging.debug("yScrape2 enter")
    url = "https://finance.yahoo.com/quote/" + stock
    response = requests.get(url)
    if PERF:
        print("PERFM: request: " + str(time.time() - enter))

    soup = BeautifulSoup(response.text, "lxml")
    #soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup.find_all('span'):
        z = re.search(r"data-reactid=\"14\"", str(tag))
        if z:
            # logging.debug("z: " + str(z))
            if PERF:
                end = time.time()
                delta = end - enter
                print("PERFM: yScrape2: " + str(delta))

            return str(tag)
            break

    return "---"

#r = yScrape2("GOOG")
#print("r: " , r)

from multiprocessing import Process, Pipe, Semaphore
import time
import logging
import requests
from bs4 import BeautifulSoup
import re

data = (
    ['a', '2'], ['b', '4'], ['c', '6'], ['d', '8'],
    ['e', '1'], ['f', '3'], ['g', '5'], ['h', '7']
)

spanReCompile = re.compile(r'[><]')
logger = logging.getLogger()
#logger.setLevel(logging.INFO)
logger.setLevel(logging.DEBUG)
PERF = True
#PERF = False

def yScrape2(stock):
    if PERF:
        enter = time.time()
    logging.debug("yScrape2 enter")
    url = "https://finance.yahoo.com/quote/" + stock
    response = requests.get(url)
    if PERF:
        logging.info("PERFM: request: " + str(time.time() - enter))
        enter = time.time()

    soup = BeautifulSoup(response.text, "lxml")
    #soup = BeautifulSoup(response.text, "html.parser")

    #tag = soup.find_all('span', attr={"data-reactid": "14"})
    tag = soup.find_all('span', class_="Trsdu(0.3s) Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(b)")
    if PERF:
        logging.info("PERFM: delta " + str(time.time()-enter))
    logging.debug("tag::>")
    logging.debug(tag)
    if tag:
        return str(tag)
    #ERROR
        return "ERROR"

    for tag in soup.find_all('span', class_="Trsdu(0.3s) Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(b)"):
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
        ret = float(q[2].replace(",", ""))
        if PERF:
            logging.info("PERFM: parseBid2: " + str(time.time() - enter))
        # return float(b[0].replace(",", ""))
        return ret
    except ValueError:
        logging.error("Could not convert bid: " + str(b))
        raise Exception("parsebid2: could not convert bid for " + b)
        # return 9999



def bid_worker(name, conn):
    print("bid_worker entered for " + name)
    r = yScrape2(name)
    print("scraped " + name)
    conn.send([name + ":" + str(parseBid2(r))])
    conn.close()
    #return [name, parseBid2(r)]

def mp_worker(inputs):
    print( " Processs %s\tWaiting %s seconds",  inputs[0], inputs[1])
    time.sleep(int(inputs[1]))
    return inputs[0] + ":" + inputs[1]

def chunks(l,n):
    start = 0
    #ret = []
    for i in range(0, len(l), n):
        yield l[i:i+n]
        #ret.append(l[i:i+n])
    #print("returning::")
    #print(ret)
    #return ret

def mp_handler():
    #p = multiprocessing.Pool(4)
    #start = time.time()
    #r = p.map(bid_worker, stockName)
    #print("time: " + str(time.time()-start))
    #print("r::>")
    #print(r)
    starttime = time.time()
    processes = []
    parentConnections = []
    #regions = ['us-east-1', 'us-east-2', 'eu-west-1']
    stockName = ['GOOG']
    #stockName = ['GOOG', 'AMZN', 'MSFT', 'WORK']
    concurrency = 1
    for stock in stockName:
        parent_conn, child_conn = Pipe()
        parentConnections.append(parent_conn)
        p = Process(target=bid_worker, args=(stock,child_conn,))
        processes.append(p)

    for i in chunks(processes, concurrency):
        for j in i:
            j.start()
        for j in i:
            j.join()

    bids = {}
    for parentConnection in parentConnections:
        recv = parentConnection.recv()[0]
        #print(recv)
        a = recv.split(':')
        bids[a[0]] = float(a[1])

    print("recv: " )
    print (bids)
    output = 'That took {} seconds'.format(time.time() - starttime)
    print(output)
    return output

if __name__ == '__main__':
    #sharedOut = Value(array.typecode, [])
    mp_handler()
