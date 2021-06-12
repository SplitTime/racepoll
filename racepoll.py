#!/usr/bin/python3

import requests
import smtplib
import sys
import datetime
import hashlib
from os import environ as env
from time import sleep

# TODO: These should also be parameterized
pollingIntervalSeconds = 30
authRefreshLoopCount = 4

logFilePath = env['RACEPOLL_LOG']

ostUsername = env['OST_USER']
ostPassword = env['OST_PASSWORD']
ostLoginPayload = "user[email]=%s&user[password]=%s" % ( ostUsername, ostPassword )
ostLoginUrl = "https://www.opensplittime.org/api/v1/auth"

rrEventId = env['RR_EVENT_ID']
rrApiKey = env['RR_API_KEY']
rrDataUrl = "https://api.raceresult.com/%s/%s" % ( rrEventId, rrApiKey )

ostEventId = env['OST_EVENT_ID']
ostDataUrl = "https://www.opensplittime.org/api/v1/events/%s/import?data_format=race_result_api_times" % ostEventId

global oldhash
oldhash = None

token = ""
def authRefresh():
    global token
    ostLoginResponse = requests.post(url = ostLoginUrl, data = ostLoginPayload)
    if ostLoginResponse.status_code // 100 != 2:
        with open(logFilePath, "a+") as f:
            f.write("%s  Failed to authenticate with OST. Status code: %d\n" % (datetime.datetime.now(), ostLoginResponse.status_code))
        return
    token = ostLoginResponse.json()['token']


firstIteration = True
authRefreshLoop = 0
while True:
    if not firstIteration:
        sleep(pollingIntervalSeconds)

    firstIteration = False

    if authRefreshLoop <= 0:
        authRefresh()
        authRefreshLoop = authRefreshLoopCount
    else:
        authRefreshLoop -= 1

    rrDataResponse = requests.get(url = rrDataUrl)
    if rrDataResponse.status_code // 100 != 2:
        with open(logFilePath, "a+") as f:
            f.write("%s  Failed to get third party data. Status code: %d\n" % (datetime.datetime.now(), rrDataResponse.status_code))
        continue

    newhash = hashlib.sha256(rrDataResponse.content).hexdigest()
    if newhash == oldhash:
        with open(logFilePath, "a+") as f:
            f.write("%s  No change\n" % datetime.datetime.now())
        continue
    else:
        oldhash = newhash

    ostDataHeaders = { "Content-Type": "application/json", "Authorization": "bearer %s" % token }
    ostDataResponse = requests.post(url = ostDataUrl, headers = ostDataHeaders, json = { "data": rrDataResponse.json() })
    if ostDataResponse.status_code // 100 != 2:
        with open(logFilePath, "a+") as f:
            f.write("%s  Failed to post data to OST. Status code: %d\n" % (datetime.datetime.now(), ostDataResponse.status_code))
        continue
    with open(logFilePath, "a+") as f:
        f.write("%s  Successful sync\n" % datetime.datetime.now())

