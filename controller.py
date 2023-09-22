import os
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification


def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]
    response = lotto.buy_lotto645(authCtrl, cnt, _mode)
    response['balance'] = lotto.get_balance(auth_ctrl=authCtrl)
    return response

def check_winning_lotto645(authCtrl: auth.AuthController) -> dict:
    lotto = lotto645.Lotto645()
    item = lotto.check_winning(authCtrl)
    return item

def buy_win720(authCtrl: auth.AuthController):
    pension = win720.Win720()
    response = pension.buy_Win720(authCtrl)
    response['balance'] = pension.get_balance(auth_ctrl=authCtrl)
    return response

def check_winning_win720(authCtrl: auth.AuthController) -> dict:
    pension = win720.Win720()
    item = pension.check_winning(authCtrl)
    return item

def send_message(mode: int, lottery_type: int, response: dict, webhook_url: str):
    notify = notification.Notification()
    print('hi')
    if mode == 0:
        print('hi 2')
        if lottery_type == 0:
            print('hi 3')
            notify.send_lotto_winning_message(response, webhook_url)
        else:
            print('hi 4')
            notify.send_win720_winning_message(response, webhook_url)
    elif mode == 1: 
        print('hi 5')
        if lottery_type == 0:
            print('hi 6')
            notify.send_lotto_buying_message(response, webhook_url)
        else:
            print('hi 7')
            notify.send_win720_buying_message(response, webhook_url)

def check():
    load_dotenv()

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') 
    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(username, password)
    response = check_winning_lotto645(globalAuthCtrl)
    print('slack_webhook_url', slack_webhook_url)
    print('discord_webhook_url', discord_webhook_url)
    if slack_webhook_url != '':
        send_message(0, 0, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(0, 0, response=response, webhook_url=discord_webhook_url)

    response = check_winning_win720(globalAuthCtrl)
    if slack_webhook_url != '':
        send_message(0, 1, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(0, 1, response=response, webhook_url=discord_webhook_url)

def buy(): 
    
    load_dotenv() 
    print('USERNAME:', os.environ.get('USERNAME'))
    print('PASSWORD:', os.environ.get('PASSWORD'))
    print('COUNT:', os.environ.get('COUNT'))
    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    count = int(os.environ.get('COUNT'))
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') 
    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    mode = "AUTO"

    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(username, password)

    response = buy_lotto645(globalAuthCtrl, count, mode) 
    if slack_webhook_url != '':
        send_message(1, 0, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(1, 0, response=response, webhook_url=discord_webhook_url)

    response = buy_win720(globalAuthCtrl) 
    if slack_webhook_url != '':
        send_message(1, 1, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(1, 1, response=response, webhook_url=discord_webhook_url)

def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check]")
        return

    if sys.argv[1] == "buy":
        buy()
    elif sys.argv[1] == "check":
        check()
  

if __name__ == "__main__":
    run()
