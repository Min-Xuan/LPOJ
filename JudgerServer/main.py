# coding=utf-8

import MySQLdb
import Queue
import socket
import json
from time import sleep
import threading


mutex = threading.Lock()  # queue mutex

queue = Queue.Queue()
myjsonfile = open("./setting.json", 'r')
judgerjson = json.loads(myjsonfile.read())

db = MySQLdb.connect(judgerjson["db_ip"], judgerjson["db_user"], judgerjson["db_pass"],
                     judgerjson["db_database"], int(judgerjson["db_port"]), charset='utf8')


def getSubmition():
    global queue, mutex, db

    cursor = db.cursor()
    while True:
        sleep(1)
        if mutex.acquire():
            cursor.execute(
                "SELECT * from judgestatus_judgestatus where result = '-1'")
            data = cursor.fetchall()
            try:
                for d in data:
                    queue.put(d[0])
                    cursor.execute(
                        "UPDATE judgestatus_judgestatus SET result = '-6' WHERE id = '%d'" % d[0])
                db.commit()
            except:
                db.rollback()
            #queue.sort(reverse=True)
            mutex.release()
    db.close()

fir=True
def deal_client(newSocket: socket, addr,first):
    global mutex, queue,fir
    statue = False
    cursor = db.cursor()
    while True:
        sleep(1)
        if mutex.acquire():
            try:
                if statue == True and queue.empty() is not True:
                    id = queue.get()
                    statue = False
                    # 只允许一个测评机测JAVA，否则时间会判断失败
                    
                    cursor.execute(
                        "SELECT language from judgestatus_judgestatus where id = '%d'"%(id))
                    data = cursor.fetchall()
                    print(data[0][0])
                    if data[0][0] == "Java" and first==True:
                        newSocket.send(("judge|%d" % id).encode("utf-8"))
                    elif data[0][0] != "Java":
                        newSocket.send(("judge|%d" % id).encode("utf-8"))
                    else:
                        queue.put(id)
                else:
                    newSocket.send("getstatue".encode("utf-8"))
                    data = newSocket.recv(1024)
                    recv_data = data.decode('utf-8')
                    if recv_data == "ok":
                        statue = True
                    else:
                        statue = False
                    print(addr,statue)

            except socket.error:
                newSocket.close()
                mutex.release()
                if first == True:
                    fir = True
                return
            except:
                print("error!")
                mutex.release()
                if first == True:
                    fir = True
                return
            mutex.release()


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("", judgerjson["server_port"]))
server.listen(20)
print("server is running!")

t = threading.Thread(target=getSubmition, args=())
t.setDaemon(True)
t.start()


# 记得添加contest开始时，自动设置题目为auth=3，比赛结束自动设置auth=1
def changeauth():
    global db,mutex
    curcontest = set()
    cursor = db.cursor()
    while True:
        sleep(2)
        if mutex.acquire():
            cursor.execute("SELECT * from contest_contestinfo where TO_SECONDS(NOW()) - TO_SECONDS(begintime) <= lasttime")
            data = cursor.fetchall()
            getcontest = set()
            for d in data:
                getcontest.add(d[0]) # 用于求结束的比赛
                cursor.execute("SELECT * from contest_contestproblem where contestid=%d" % d[0])
                pros = cursor.fetchall()
                for pid in pros:
                    cursor.execute( "UPDATE  problem_problemdata SET auth = 3 WHERE problem = %s" % pid[2])
                    cursor.execute( "UPDATE  problem_problem SET auth = 3 WHERE problem = %s" % pid[2])
                db.commit()
            
            endcontest = curcontest.difference(getcontest)
            print("curcontest",curcontest)
            for eid in endcontest:
                cursor.execute( "SELECT * from contest_contestproblem where contestid=%d" % eid)
                pros = cursor.fetchall()
                for pid in pros:
                    print(pid[2])
                    cursor.execute("UPDATE  problem_problemdata SET auth = 1 WHERE problem = %s" % pid[2])
                    cursor.execute("UPDATE  problem_problem SET auth = 1 WHERE problem = %s" % pid[2])
                db.commit()
            curcontest = getcontest
            mutex.release()

t1 = threading.Thread(target=changeauth, args=())
t1.setDaemon(True)
t1.start()



while True:
    newSocket, addr = server.accept()
    print("client [%s] is connected!" % str(addr))
    client = threading.Thread(target=deal_client, args=(newSocket, addr,fir))
    fir=False
    client.setDaemon(True)
    client.start()
