#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import emoji
import sys
import time
import logging
import yaml
from functools import wraps
from os import path
from pytz import timezone
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ChatAction
from threading import Thread
from vmware_task_telegram_bot.db import DB
from vmware_task_telegram_bot.vmware import vCenter


cfg = None
vc = None
db = None
sender = None
updater = None
logger = None


def get_config(path):
    try:
        with open(path, 'r') as ymlfile:
            cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    except Exception as exc:
        logger.error('Config file error: {}'.format(exc))
        sys.exit(1)
    else:
        return cfg


def init_log(debug=None):
    if debug:
        consolelog_level = logging.DEBUG
        # filelog_level = logging.DEBUG
    else:
        consolelog_level = logging.INFO
        # filelog_level = logging.INFO

    logger = logging.getLogger('cit-telegram-bot')
    logger.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    consolelog = logging.StreamHandler()
    consolelog.setLevel(consolelog_level)

    # create file handler which logs even debug messages
    # filelog = logging.FileHandler('ecoline.log')
    # filelog.setLevel(filelog_level)

    # create formatter and add it to the handlers
    formatter = logging.Formatter(u'%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s')
    # filelog.setFormatter(formatter)
    consolelog.setFormatter(formatter)

    # add the handlers to logger
    logger.addHandler(consolelog)
    # logger.addHandler(filelog)

    return logger


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id

        if user_id not in cfg['telegram']['allow_user']:
            context.bot.sendMessage(chat_id=update.message.chat_id,
                                    text=u'Oh! You are not authorized for this type of request.')
            return
        return func(update, context, *args, **kwargs)
    return wrapped



async def error(update, exc):
    global logger
    logger.error('Update "%s" caused error "%s"' % (update, '{}({})'.format(type(exc).__name__, exc)))


@restricted
async def start(update, context):
    context.bot.sendMessage(chat_id=update.message.chat_id,
                            text=u'Welcome.')



@restricted
async def help(update, context):
    context.bot.sendMessage(chat_id=update.message.chat_id,
                            text=u'vm-list-task - show active tasks')



@restricted
async def unknown(update, context):
    context.bot.sendMessage(chat_id=update.message.chat_id,
                            text=u'Sorry, I dont support this type of request.')



@restricted
async def list_running_task(update, context):
    context.bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global vc
        tasks = vc.list_running_task()
    except Exception as exc:
        error(update, exc)
        context.bot.sendMessage(chat_id=update.message.chat_id,
                                text=u'Oh! An error has occurred. Please try again later.')
    else:
        if tasks:
            for task in tasks:
                try:
                    response = u'ID: {}\r\nDescription: {}\r\nAn object: {}\r\nUser: {}\r\nStatus: {}\r\nCompletion percentage: {}\r\nBeginning of work: {}\r\n'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['progress'], task['startTime'].astimezone(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M'))
                except Exception as exc:
                    error(update, exc)
                    context.bot.sendMessage(chat_id=update.message.chat_id,
                                            text=u'Oh! An error has occurred. Please try again later.')

                context.bot.sendMessage(chat_id=update.message.chat_id,
                                        text=response)
        else:
            context.bot.sendMessage(chat_id=update.message.chat_id,
                                    text=u'There are no active tasks.')



@restricted
async def list_active_alarm(update, context):
    alarm_status_emoji = {'gray': emoji.emojize(':gray_circle:'),
                          'green': emoji.emojize(':green_circle:'),
                          'yellow': emoji.emojize(':yellow_circle:'),
                          'red': emoji.emojize(':red_circle:')}
    context.bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global vc
        alarms = vc.list_active_alarm()
    except Exception as exc:
        error(update, exc)
        context.bot.sendMessage(chat_id=update.message.chat_id,
                                text=u'Oh! An error has occurred. Please try again later.')
    else:
        if alarms:
            for alarm in sorted(alarms, key=lambda i: i['time'], reverse=True):
                try:
                    response = u'Description: {}\r\nAn object: {}\r\nImportance: {}\r\nTime: {}\r\n'.format(alarm['description'],
                                                                                                     alarm['entityName'],
                                                                                                     alarm_status_emoji[alarm['status']],
                                                                                                     alarm['time'].astimezone(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M'))
                except Exception as exc:
                    error(update, exc)
                    context.bot.sendMessage(chat_id=update.message.chat_id,
                                            text=u'Oh! An error has occurred. Please try again later.')

                context.bot.sendMessage(chat_id=update.message.chat_id,
                                        text=response)
        else:
            context.bot.sendMessage(chat_id=update.message.chat_id,
                                    text=u'There are no active triggers.')



@restricted
async def subscribe_all_task(update, context):
    context.args.append('all')
    subscribe_task(update, context)



@restricted
async def subscribe_task(update, context):
    context.bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global vc
        if context.args[0] == 'all':
            tasks = vc.list_running_task()
        else:
            tasks = vc.check_task_exist(context.args[0])

    except Exception as exc:
        error(update, exc)
        context.bot.sendMessage(chat_id=update.message.chat_id,
                                text=u'Oh! An error has occurred. Try again later.')

    else:
        if tasks:
            try:
                db = DB(cfg['db']['path'])
            except Exception as exc:
                logger.error('SQLite DB connection error: {}'.format(exc))
            else:
                try:
                    if context.args[0] == 'all':
                        new_subscription_flag = False
                        for task in tasks:
                            if not db.get_subsciption(update.message.chat_id, task['eventChainId']):
                                new_subscription_flag = True
                                db.add_subscription(update.message.chat_id, task['eventChainId'])
                                context.bot.sendMessage(chat_id=update.message.chat_id,
                                                        text=u'You are subscribed to task completion alerts {}.'.format(task['eventChainId']))
                        if not new_subscription_flag:
                            context.bot.sendMessage(chat_id=update.message.chat_id,
                                                    text=u'You are already subscribed to notifications about the completion of all currently active tasks.')

                    else:
                        db.add_subscription(update.message.chat_id, context.args[0])
                        context.bot.sendMessage(chat_id=update.message.chat_id,
                                                text=u'You are subscribed to task completion notifications {}.'.format(context.args[0]))

                except Exception as exc:
                    error(update, exc)
                    context.bot.sendMessage(chat_id=update.message.chat_id,
                                            text=u'Oh! An error has occurred. Please try again later.')
        else:
            context.bot.sendMessage(chat_id=update.message.chat_id,
                                    text=u'No active tasks with this ID were found.')



@restricted
async def unsubscribe_all_task(update, context):
    context.args.append('all')
    unsubscribe_task(update, context)



@restricted
async def unsubscribe_task(update, context):
    context.bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global vc
        if context.args[0] == 'all':
            tasks = True
        else:
            tasks = vc.check_task_exist(context.args[0])
    except Exception as exc:
        error(update, exc)
        context.bot.sendMessage(chat_id=update.message.chat_id,
                                text=u'Oh! An error has occurred. Please try again later.')
    else:
        if tasks:
            try:
                db = DB(cfg['db']['path'])
            except Exception as exc:
                logger.error('SQLite DB connection error: {}'.format(exc))
            else:
                try:
                    if context.args[0] == 'all':
                        if db.get_subsciption_by_uid(update.message.chat_id):
                            db.remove_subscription_by_uid(update.message.chat_id)
                            context.bot.sendMessage(chat_id=update.message.chat_id,
                                                    text=u'All subscriptions to task completion notifications have been cancelled.')
                        else:
                            context.bot.sendMessage(chat_id=update.message.chat_id,
                                                    text=u'You are not subscribed to task completion notifications.')
                    else:
                        if db.get_subsciption(update.message.chat_id, context.args[0]):
                            db.remove_subscription(update.message.chat_id, context.args[0])
                            context.bot.sendMessage(chat_id=update.message.chat_id,
                                                    text=u'You have unsubscribed from task completion notifications {}.'.format(context.args[0]))
                        else:
                            context.bot.sendMessage(chat_id=update.message.chat_id,
                                                    text=u'You are not subscribed to task completion notifications {}.'.format(context.args[0]))

                except Exception as exc:
                    error(update, exc)
                    context.bot.sendMessage(chat_id=update.message.chat_id,
                                            text=u'Oh! An error has occurred. Please try again later.')
        else:
            context.bot.sendMessage(chat_id=update.message.chat_id,
                                    text=u'No active tasks with this ID were found.')



@restricted
async def list_subscription(update, context):
    context.bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        db = DB(cfg['db']['path'])
    except Exception as exc:
        logger.error('SQLite DB connection error: {}'.format(exc))
    else:
        try:
            subscriptions = db.get_subsciption_by_uid(update.message.chat_id)
        except Exception as exc:
            error(update, exc)
            context.bot.sendMessage(chat_id=update.message.chat_id,
                                    text=u'Oh! An error has occurred. Please try again later.')
        else:
            if subscriptions:
                try:
                    global vc
                    for subscription in subscriptions:
                        task = vc.get_task(subscription[1])
                        task = task[0]
                        try:
                            response = u'ID: {}\r\nDescription: {}\r\nAn object: {}\r\nUser: {}\r\nStatus: {}\r\nExecution progress: {} %\r\nBeginning of work: {}\r\n'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['progress'], task['startTime'].astimezone(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M'))
                        except Exception as exc:
                            error(update, exc)
                            context.bot.sendMessage(chat_id=update.message.chat_id,
                                                    text=u'Oh! An error has occurred. Please try again later.')
                        else:
                            context.bot.sendMessage(chat_id=update.message.chat_id,
                                                    text=response)
                except Exception as exc:
                    error(update, exc)
                    context.bot.sendMessage(chat_id=update.message.chat_id,
                                            text=u'Oh! An error has occurred. Please try again later.')
            else:
                context.bot.sendMessage(chat_id=update.message.chat_id,
                                        text=u'You have no active subscriptions.')


def check_subscriptions():
    logger.info('Start subscriptions checking')
    try:
        db = DB(cfg['db']['path'])
    except Exception as exc:
        logger.error('%s' % ('{}({})'.format(type(exc).__name__, error)))
    else:
        try:
            subscriptions = db.list_subscriptions()
        except Exception as exc:
            logger.error('%s' % ('{}({})'.format(type(exc).__name__, error)))
        else:
            if subscriptions:
                global vc
                for subscription in subscriptions:
                    try:
                        task = vc.get_task(subscription[1])
                        task = task[0]
                    except Exception as exc:
                        logger.error('%s' % ('{}({})'.format(type(exc).__name__, exc)))
                    else:
                        try:
                            if task['state'] == 'success':
                                response = u'Task completed successfully\r\nID: {}\r\nDescription: {}\r\nAn object: {}\r\nUser: {}\r\nStatus: {}\r\nBeginning of work: {}\r\nEnd of work: {}'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['startTime'].astimezone(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M'), task['completeTime'].astimezone(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M'))
                                db.remove_subscription(subscription[0], subscription[1])
                            elif task['state'] == 'error':
                                response = u'Task completed successfully\r\nID: {}\r\nDescription: {}\r\nAn object: {}\r\nUser: {}\r\nStatus: {}\r\nDescription of the error: {}\r\nBeginning of work: {}\r\nEnd of work: {}'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['error'], task['startTime'].astimezone(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M'), task['completeTime'].astimezone(timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M'))
                                db.remove_subscription(subscription[0], subscription[1])
                        except Exception as exc:
                            logger.error('%s' % ('{}({})'.format(type(exc).__name__, exc)))
                        else:
                            if task['state'] == 'success' or task['state'] == 'error':
                                global updater
                                try:
                                    updater.bot.sendMessage(
                                        chat_id=subscription[0],
                                        text=response
                                    )
                                except Exception as exc:
                                    logger.error('%s' % ('{}({})'.format(type(exc).__name__, exc)))


def has_live_threads(threads):
    return True in [t.is_alive() for t in threads]


def start_bot():
    global updater
    updater.start_polling()


class checker_thread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.kill_received = False

    def run(self):
        while not self.kill_received:
            check_subscriptions()
            time.sleep(60)


def main():
    global cfg
    global vc
    global db
    global sender
    global updater
    global logger

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-c', '--config', required=True,
                           help='configuration file')
    argparser.add_argument('--debug', action='store_true')
    args = argparser.parse_args()

    logger = init_log(debug=args.debug)

    if not path.isfile(args.config):
        print('VMware task notification bot configuration file {} not found'.format(args.config))
        logger.error('VMware task notification bot configuration file {} not found'.format(args.config))
        sys.exit()

    logger.info('Starting vmware task notifier bot')
    cfg = get_config(args.config)
    try:
        vc = vCenter(cfg['vmware']['server'],
                     cfg['vmware']['username'],
                     cfg['vmware']['password'])
    except Exception as exc:
        logger.error('VMWare vCenter connection error: {}'.format(exc))

    try:
        db = DB(cfg['db']['path'])
    except Exception as exc:
        logger.error('SQLite DB connection error: {}'.format(exc))

    if 'proxy' in cfg['telegram']:
        REQUEST_KWARGS = {
            'proxy_url': cfg['telegram']['proxy']['url'],
            'urllib3_proxy_kwargs': {
                'username': cfg['telegram']['proxy']['username'],
                'password': cfg['telegram']['proxy']['password'],
            }
        }
        updater = Updater(token=cfg['telegram']['token'], use_context=True, request_kwargs=REQUEST_KWARGS)
    else:
        updater = Updater(token=cfg['telegram']['token'], use_context=True)

    dp = updater.dispatcher
    start_handler = CommandHandler('start', start, run_async=True)
    help_handler = CommandHandler('help', help, run_async=True)
    list_alarm_handler = CommandHandler('vmlistalarm', list_active_alarm, run_async=True)
    list_handler = CommandHandler('vmlisttask', list_running_task, run_async=True)
    subscribe_all_handler = CommandHandler('vmsuball', subscribe_all_task, run_async=True, pass_args=False)
    subscribe_handler = CommandHandler('vmsub', subscribe_task, run_async=True, pass_args=True)
    unsubscribe_all_handler = CommandHandler('vmunsuball', unsubscribe_all_task, run_async=True, pass_args=False)
    unsubscribe_handler = CommandHandler('vmunsub', unsubscribe_task, run_async=True, pass_args=True)
    list_subscription_handler = CommandHandler('vmlistsub', list_subscription, run_async=True)
    unknown_handler = MessageHandler(Filters.command, unknown, run_async=True)

    dp.add_handler(start_handler)
    dp.add_handler(help_handler)
    dp.add_handler(list_handler)
    dp.add_handler(list_alarm_handler)
    dp.add_handler(subscribe_all_handler)
    dp.add_handler(subscribe_handler)
    dp.add_handler(unsubscribe_all_handler)
    dp.add_handler(unsubscribe_handler)
    dp.add_handler(list_subscription_handler)
    dp.add_handler(unknown_handler)

    t1 = Thread(target=start_bot)
    t1.start()

    t2 = checker_thread()
    t2.start()

    threads = [t1, t2]

    while has_live_threads(threads):
        try:
            [t.join(1) for t in threads if t is not None and t.is_alive()]
        except KeyboardInterrupt:
            t2.kill_received = True
            try:
                updater.stop()
                t1.join()
            except Exception as exc:
                logger.error('%s' % ('{}({})'.format(type(exc).__name__, exc)))
                continue
    print('Exited')
    sys.exit(0)


if __name__ == '__main__':
    main()
