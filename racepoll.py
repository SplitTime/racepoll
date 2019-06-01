#!/usr/bin/python3

import requests
import smtplib
import sys
from os import environ as env
from time import sleep

# TODO: These should also be parameterized
pollingIntervalSeconds = 30
authRefreshLoopCount = 4
reportLoopCount = 5

ostUsername = env['OST_USER']
ostPassword = env['OST_PASSWORD']
ostLoginPayload = "user[email]=%s&user[password]=%s" % ( ostUsername, ostPassword )
ostLoginUrl = "https://www.opensplittime.org/api/v1/auth"

rrEventId = env['RR_EVENT_ID']
rrApiKey = env['RR_API_KEY']
rrDataUrl = "https://api.raceresult.com/%s/%s" % ( rrEventId, rrApiKey )

ostEventId = env['OST_EVENT_ID']
ostDataUrl = "https://www.opensplittime.org/api/v1/events/%s/import?data_format=race_result_api_times" % ostEventId

reportFrom = "racepoll.py"
reportRecipients = env['RACEPOLL_REPORT_RECIPIENTS'].split(",")
reportSubject = "racepoll.py Report"

smtpServer = env['RACEPOLL_SMTP_SERVER']
smtpPort = env['RACEPOLL_SMTP_PORT']
smtpSender = env['RACEPOLL_SMTP_SENDER']
smtpPassword = env['RACEPOLL_SMTP_PASSWORD']

token = ""
def authRefresh():
    global token
    print("Refreshing OST authentication token...")
    ostLoginResponse = requests.post(url = ostLoginUrl, data = ostLoginPayload)
    if ostLoginResponse.status_code // 100 != 2:
        print("Failed to authenticate with OST. Status code: %d" % ostLoginResponse.status_code)
        ostAuthFailures += 1
        return
    token = ostLoginResponse.json()['token']
    print("Successfully authenticated.")


successfulUpdates = 0
ostAuthFailures = 0
rrDataFailures = 0
ostDataFailures = 0

def resetStatistics():
    global successfulUpdates, ostAuthFailures, rrDataFailures, ostDataFailures
    successfulUpdates = 0
    ostAuthFailures = 0
    rrDataFailures = 0
    ostDataFailures = 0


def report():
    print("Reporting...")
    smtp = smtplib.SMTP(smtpServer, smtpPort)
    smtp.ehlo()
    smtp.starttls()
    smtp.login(smtpSender, smtpPassword)
    reportBody = "\r\n".join(
            ["From: %s" % reportFrom,
             "Subject: %s" % reportSubject,
             "",
             "STATISTICS (since last report):"
             "",
             "Successful updates: %d" % successfulUpdates,
             "",
             "Authentication failures: %d" % ostAuthFailures,
             "",
             "Third party data download failures: %d" % rrDataFailures,
             "",
             "OST data upload failures: %d" % ostDataFailures
             ])
    smtp.sendmail(smtpSender, reportRecipients, reportBody)
    resetStatistics()
    print("Reporting finished successfully.")
    return


firstIteration = True
authRefreshLoop = 0
reportLoop = reportLoopCount
while True:
    if not firstIteration:
        print("Next activity: Data %ds, Auth %ds, Report %ds" % (
            pollingIntervalSeconds,
            pollingIntervalSeconds * (authRefreshLoop + 1),
            pollingIntervalSeconds * (reportLoop + 1)))
        sleep(pollingIntervalSeconds)

    firstIteration = False

    if authRefreshLoop <= 0:
        authRefresh()
        authRefreshLoop = authRefreshLoopCount
    else:
        authRefreshLoop -= 1

    if reportLoop <= 0:
        try:
            report()
        except:
            e = sys.exc_info()[0]
            print("Failed to report. Error: %s" % e)
        reportLoop = reportLoopCount
    else:
        reportLoop -= 1

    print("Getting third party data...")
    rrDataResponse = requests.get(url = rrDataUrl)
    if rrDataResponse.status_code // 100 != 2:
        print("Failed to get third party data. Status code: %d" % rrDataResponse.status_code)
        rrDataFailures += 1
        continue

    print("Posting data to OST...")
    ostDataHeaders = { "Content-Type": "application/json", "Authorization": "bearer %s" % token }
    ostDataResponse = requests.post(url = ostDataUrl, headers = ostDataHeaders, json = { "data": rrDataResponse.json() })
    if ostDataResponse.status_code // 100 != 2:
        print("Failed to post data to OST. Status code: %d" % ostDataResponse.status_code)
        print("FAILURE BODY")
        print(ostDataResponse.json())
        print("END FAILURE BODY")
        ostDataFailures += 1
        continue
    successfulUpdates += 1
    print("Successfully posted data to OST.")

