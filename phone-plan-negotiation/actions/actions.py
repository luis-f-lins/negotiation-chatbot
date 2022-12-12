# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from dis import dis
from typing import Any, Text, Dict, List, Union, Optional
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

import re
import requests

processKey = 'negotiation_phone_plan'

users = [
    {
        "email": "test1@abc.com",
        "total_minute_qty": "ultd",
        "avg_minute_usage": "300",
        "total_data": 50.0,
        "avg_data_usage": 45.0,
        "plan_price": 99.0,
        "last_discount": None,
        "member_since": "2021-04-04",
    },
    {
        "email": "test2@abc.com",
        "total_minute_qty": "500",
        "avg_minute_usage": "300",
        "total_data": 20.0,
        "avg_data_usage": 10.0,
        "last_discount": "2021-11-03",
        "member_since": "2020-04-04",
    },
    {
        "email": "test3@abc.com",
        "total_minute_qty": "700",
        "avg_minute_usage": "300",
        "total_data": 40.0,
        "avg_data_usage": 30.0,
        "plan_price": 79.0,
        "last_discount": "2018-09-13",
        "member_since": "2017-04-04",
    },
]


def first(iterable, default=None):
    for item in iterable:
        return item
    return default


def start_camunda_process(variables={}):
    global taskGetUrl
    global processInstanceGetUrl
    global processInstanceId

    url = 'http://localhost:8080/engine-rest/process-definition/key/' + processKey + '/start'
    postPayload = {"variables": variables,
                   }

    response = requests.post(url, json=postPayload)

    processInstanceId = response.json()['id']
    taskGetUrl = 'http://localhost:8080/engine-rest/task?processInstanceId=' + processInstanceId
    processInstanceGetUrl = 'http://localhost:8080/engine-rest/process-instance/' + \
        processInstanceId


def utter_next_available(dispatcher, utterMessageVariables={}):
    afterCompletionJsonObj = requests.get(taskGetUrl).json()
    print(afterCompletionJsonObj)

    if len(afterCompletionJsonObj) > 0:
        print(afterCompletionJsonObj[0])
        print(afterCompletionJsonObj[0]["taskDefinitionKey"])
        next_utter_action = "utter_%s" % (
            afterCompletionJsonObj[0]["taskDefinitionKey"])
        dispatcher.utter_message(
            response=next_utter_action, **utterMessageVariables)


class start_process(Action):

    def name(self) -> Text:
        return "action_start_process"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        userEmail = tracker.get_slot("user_email")
        print(userEmail)

        currentUser = first(obj for obj in users
                            if obj['email'] == userEmail)
        print(currentUser)

        if currentUser["last_discount"] == None:
            discountLast24Mo = False
        else:
            lastDiscountDate = datetime.strptime(
                currentUser["last_discount"], "%Y-%m-%d")
            discountLast24Mo = lastDiscountDate >= (
                datetime.now() - relativedelta(months=24))

        memberSinceDate = datetime.strptime(
            currentUser["member_since"], "%Y-%m-%d")
        contractAge = relativedelta(datetime.now(), memberSinceDate).years

        avgDataUsagePc = currentUser["avg_data_usage"] / \
            currentUser["total_data"]

        start_camunda_process({
            "discount_last_24_mo": {"value": discountLast24Mo},
            "contract_age": {"value": contractAge},
            "avg_data_usage": {"value": avgDataUsagePc},
        })

        utter_next_available(dispatcher)

        return [FollowupAction("action_listen")]
