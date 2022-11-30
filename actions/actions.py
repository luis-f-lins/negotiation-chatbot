# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from dis import dis
from typing import Any, Text, Dict, List, Union, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

import re
import requests

processKey = 'negotiation_car'

available_cars = [{
    "brand": "Toyota",
    "name": "Prius",
    "price": "17,000.00",
    "year": "2015",
    "demand": "low"
},
{
    "brand": "Kia",
    "name": "Sorento",
    "price": "35,000.00",
    "year": "2021",
    "demand": "high"
},
{
    "brand": "Ford",
    "name": "Escape",
    "price": "20,000.00",
    "year": "2017",
    "demand": "very_low"
}
]

def first(iterable, default=None):
  for item in iterable:
    return item
  return default


def start_camunda_process():
    global taskGetUrl
    global processInstanceGetUrl
    global processInstanceId

    url = 'http://localhost:8080/engine-rest/process-definition/key/' + processKey + '/start'
    postPayload = {"variables": {
        "requested_car": {"value": {}},
        "payment_method": {"value": ''},
        "requested_discount": {"value": 0.0}
    },
    }

    response = requests.post(url, json=postPayload)

    processInstanceId = response.json()['id']
    taskGetUrl = 'http://localhost:8080/engine-rest/task?processInstanceId=' + processInstanceId
    processInstanceGetUrl = 'http://localhost:8080/engine-rest/process-instance/' + \
        processInstanceId


def utter_next_available(dispatcher, utterMessageVariables = {}):
    afterCompletionJsonObj = requests.get(taskGetUrl).json()
    print(afterCompletionJsonObj)

    if len(afterCompletionJsonObj) > 0:
        print(afterCompletionJsonObj[0])
        print(afterCompletionJsonObj[0]["taskDefinitionKey"])
        next_utter_action = "utter_%s" % (afterCompletionJsonObj[0]["taskDefinitionKey"])
        dispatcher.utter_message(response=next_utter_action, **utterMessageVariables)


def complete_task(taskName, dispatcher, postPayload = {}, utterMessageVariables = {}):
    jsonObj = requests.get(taskGetUrl).json()

    print(jsonObj)
    print(taskName)

    currentTaskId = None

    for i in jsonObj:
        if i['taskDefinitionKey'] == taskName:
            currentTaskId = i['id']
    
    if currentTaskId == None:
        dispatcher.utter_message(
            text='I\'m sorry, but this task is not available.')
        return

    url = 'http://localhost:8080/engine-rest/task/' + currentTaskId + '/complete'
    response = requests.post(url, json=postPayload)

    utter_next_available(dispatcher, utterMessageVariables)

    return [FollowupAction("action_listen")]



class which_car(Action):

    def name(self) -> Text:
        return "action_which_car"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        requested_car_name = tracker.get_slot("requested_car")

        found_car = first(obj for obj in available_cars \
            if obj['name'] == requested_car_name or obj['brand'] == requested_car_name)

        if (found_car == None):
            dispatcher.utter_message(text="Sorry, we don't have that car available right now")
        
        else:
            dispatcher.utter_message(text="Okay! So here I have a %s %s %s. \
                It costs $%s. Can I complete your purchase?" % (found_car['year'], \
                found_car['brand'], found_car['name'], found_car['price']))

        return [FollowupAction("action_listen")]


class calculate_discount(Action):

    def name(self) -> Text:
        return "action_calculate_discount"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_camunda_process()

        all_user_messages = [obj for obj in tracker.events if obj["event"] == 'user']
        last_message = all_user_messages[-1].get("text")
        print(last_message)

        requested_car_name = tracker.get_slot("requested_car")

        found_car = first(obj for obj in available_cars \
            if obj['name'] == requested_car_name or obj['brand'] == requested_car_name)

        discount = None
        discount_type = None

        abs_regex = re.compile(r"\$[-0-9.,]+[-0-9.,]*\b")
        abs_result = abs_regex.findall(last_message)
        print(abs_result)

        car_price = float(found_car["price"].replace(",",""))

        if abs_result:
            discount_type = 'absolute'
            discount = int(re.sub('[^0-9]+', '', abs_result[0])) / car_price
        else:
            pc_regex = re.compile(r"\b(?<!\.)(?!0+(?:\.0+)?%)(?:\d|[1-9]\d|100)(?:(?<!100)\.\d+)?%")
            pc_result = pc_regex.findall(last_message)

            if pc_result:
                discount_type = 'percentage'
                discount = int(re.sub('[^0-9]+', '', pc_result[0])) / 100

        complete_task("calculate_discount", dispatcher, {"variables": {
                "requested_discount": {"value": discount},
                "requested_car": {"value": found_car},
            }}
        )

        return [SlotSet("requested_discount", discount), FollowupAction("action_listen")]


class set_payment_method(Action):

    def name(self) -> Text:
        return "action_set_payment_method"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        payment_method = None

        user_chosen_method = tracker.get_intent_of_latest_message()

        requested_car_name = tracker.get_slot("requested_car")

        found_car = first(obj for obj in available_cars \
            if obj['name'] == requested_car_name or obj['brand'] == requested_car_name)

        print(user_chosen_method)

        if user_chosen_method == 'finance_car':
            payment_method = 'financing'
        elif user_chosen_method == 'pay_cash':
            payment_method = 'cash'

        print(payment_method)

        print(tracker.get_slot("requested_discount"))

        total_pc_discount_offered = min(0.05, float(tracker.get_slot("requested_discount"))) \
            if found_car["demand"] == 'low' \
            else min(0.1, float(tracker.get_slot("requested_discount")))

        car_price = float(found_car["price"].replace(",",""))

        abs_discount = total_pc_discount_offered * car_price

        complete_task("ask_payment_method", dispatcher, {"variables": {
                "payment_method": {"value": payment_method},
            }}, {"discount": "$%s" % ("{:.2f}".format(abs_discount)), \
            "discount_pc": str(round(total_pc_discount_offered*100)) + '%'}
        )

        return [FollowupAction("action_listen")]
