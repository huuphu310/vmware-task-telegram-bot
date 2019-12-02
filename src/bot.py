#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
import time
import logging
import yaml
from os import path
from threading import Thread
from functools import wraps
from vmware import vCenter
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram import ChatAction
from pytz import timezone
from db import DB


cfg = None
vc = None
db = None
sender = None
updater = None
logger = None


def get_config(path):
    try:
        with open(path, 'r') as ymlfile:
            cfg = yaml.load(ymlfile)
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
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id

        if user_id not in cfg['telegram']['allow_user']:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Ой! Вы не авторизованы для этого типа запросов.'
            )
            return
        return func(bot, update, *args, **kwargs)
    return wrapped


@run_async
def error(bot, update, error):
    global logger
    logger.error('Update "%s" caused error "%s"' % (update, '{}({})'.format(type(error).__name__, error)))


@run_async
@restricted
def start(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text=u'Добро пожаловать.'
    )


@run_async
@restricted
def help(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text=u'vm-list-task - показать активные задачи'
    )


@run_async
@restricted
def unknown(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text=u'Простите, я не поддерживаю этот тип запросов.'
    )


@run_async
@restricted
def list_running_task(bot, update):
    bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global vc
        tasks = vc.list_running_task()
    except Exception as exc:
        error(bot, update, exc)
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
        )
    else:
        if tasks:
            for task in tasks:
                try:
                    response = u'ID: {}\r\nОписание: {}\r\nОбъект: {}\r\nПользователь: {}\r\nСтатус: {}\r\nПроцент выполнения: {}\r\nНачало работы: {}\r\n'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['progress'], task['startTime'].astimezone(timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M'))
                except Exception as exc:
                    error(bot, update, exc)
                    bot.sendMessage(
                        chat_id=update.message.chat_id,
                        text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
                    )

                bot.sendMessage(
                    chat_id=update.message.chat_id,
                    text=response
                )
        else:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Активных задач нет.'
            )


@run_async
@restricted
def subscribe_all_task(bot, update):
    subscribe_task(bot, update, ['all'])


@run_async
@restricted
def subscribe_task(bot, update, args):
    bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global vc
        if args[0] == 'all':
            tasks = vc.list_running_task()
        else:
            tasks = vc.check_task_exist(args[0])

    except Exception as exc:
        error(bot, update, exc)
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
        )

    else:
        if tasks:
            try:
                db = DB(cfg['db']['path'])
            except Exception as exc:
                logger.error('SQLite DB connection error: {}'.format(exc))
            else:
                try:
                    if args[0] == 'all':
                        new_subscription_flag = False
                        for task in tasks:
                            if not db.get_subsciption(update.message.chat_id, task['eventChainId']):
                                new_subscription_flag = True
                                db.add_subscription(update.message.chat_id, task['eventChainId'])
                                bot.sendMessage(
                                    chat_id=update.message.chat_id,
                                    text=u'Вы подписаны на оповещения об окончании задачи {}.'.format(task['eventChainId'])
                                )
                        if not new_subscription_flag:
                            bot.sendMessage(
                                chat_id=update.message.chat_id,
                                text=u'Вы уже подписаны на оповещения об окончании всех текущих активных задач.'
                            )

                    else:
                        db.add_subscription(update.message.chat_id, args[0])
                        bot.sendMessage(
                            chat_id=update.message.chat_id,
                            text=u'Вы подписаны на оповещения об окончании задачи {}.'.format(args[0])
                        )

                except Exception as exc:
                    error(bot, update, exc)
                    bot.sendMessage(
                        chat_id=update.message.chat_id,
                        text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
                    )
        else:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Активных задач с таким идентификатором не найдено.'
            )


@run_async
@restricted
def unsubscribe_all_task(bot, update):
    unsubscribe_task(bot, update, ['all'])


@run_async
@restricted
def unsubscribe_task(bot, update, args):
    bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        global vc
        if args[0] == 'all':
            tasks = True
        else:
            tasks = vc.check_task_exist(args[0])
    except Exception as exc:
        error(bot, update, exc)
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
        )
    else:
        if tasks:
            try:
                db = DB(cfg['db']['path'])
            except Exception as exc:
                logger.error('SQLite DB connection error: {}'.format(exc))
            else:
                try:
                    if args[0] == 'all':
                        if db.get_subsciption_by_uid(update.message.chat_id):
                            db.remove_subscription_by_uid(update.message.chat_id)
                            bot.sendMessage(
                                chat_id=update.message.chat_id,
                                text=u'Все подписки на оповещения об окончании задач отменены.'
                            )
                        else:
                            bot.sendMessage(
                                chat_id=update.message.chat_id,
                                text=u'Вы не подписаны на оповещения об окончании задач.'
                            )
                    else:
                        if db.get_subsciption(update.message.chat_id, args[0]):
                            db.remove_subscription(update.message.chat_id, args[0])
                            bot.sendMessage(
                                chat_id=update.message.chat_id,
                                text=u'Подписка на оповещения об окончании задачи {} отменена.'.format(args[0])
                            )
                        else:
                            bot.sendMessage(
                                chat_id=update.message.chat_id,
                                text=u'Вы не подписаны на оповещения об окончании задачи {}.'.format(args[0])
                            )

                except Exception as exc:
                    error(bot, update, exc)
                    bot.sendMessage(
                        chat_id=update.message.chat_id,
                        text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
                    )
        else:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Активных задач с таким идентификатором не найдено.'
            )


@run_async
@restricted
def list_subscription(bot, update):
    bot.sendChatAction(update.message.chat_id, action=ChatAction.TYPING)
    try:
        db = DB(cfg['db']['path'])
    except Exception as exc:
        logger.error('SQLite DB connection error: {}'.format(exc))
    else:
        try:
            subscriptions = db.get_subsciption_by_uid(update.message.chat_id)
        except Exception as exc:
            error(bot, update, exc)
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
            )
        else:
            if subscriptions:
                try:
                    global vc
                    for subscription in subscriptions:
                        task = vc.get_task(subscription[1])
                        try:
                            response = u'ID: {}\r\nОписание: {}\r\nОбъект: {}\r\nПользователь: {}\r\nСтатус: {}\r\nПрогресс выполнения: {} %\r\nНачало работы: {}\r\n'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['progress'], task['startTime'].astimezone(timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M'))
                        except Exception as exc:
                            error(bot, update, exc)
                            bot.sendMessage(
                                chat_id=update.message.chat_id,
                                text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
                            )
                        else:
                            bot.sendMessage(
                                chat_id=update.message.chat_id,
                                text=response
                            )
                except Exception as exc:
                    error(bot, update, exc)
                    bot.sendMessage(
                        chat_id=update.message.chat_id,
                        text=u'Ой! Произошла ошибка. Попробуйте еще раз позже.'
                    )
            else:
                bot.sendMessage(
                    chat_id=update.message.chat_id,
                    text=u'У вас нет активных подписок.'
                )


def check_subscriptions():
    logger.info('Start subscriptions checking')
    try:
        db = DB(cfg['db']['path'])
    except Exception as exc:
        logger.error('%s' % ('{}({})'.format(type(error).__name__, error)))
    else:
        try:
            subscriptions = db.list_subscriptions()
        except Exception as exc:
            logger.error('%s' % ('{}({})'.format(type(error).__name__, error)))
        else:
            if subscriptions:
                    global vc
                    for subscription in subscriptions:
                        try:
                            task = vc.get_task(subscription[1])
                        except Exception as exc:
                            logger.error('%s' % ('{}({})'.format(type(exc).__name__, exc)))
                        else:
                            try:
                                if task['state'] == 'success':
                                    response = u'Задача успешно завершена\r\nID: {}\r\nОписание: {}\r\nОбъект: {}\r\nПользователь: {}\r\nСтатус: {}\r\nНачало работы: {}\r\nОкончание работы: {}'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['startTime'].astimezone(timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M'), task['completeTime'].astimezone(timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M'))
                                    db.remove_subscription(subscription[0], subscription[1])
                                elif task['state'] == 'error':
                                        response = u'Задача завершена с ошибкой\r\nID: {}\r\nОписание: {}\r\nОбъект: {}\r\nПользователь: {}\r\nСтатус: {}\r\Описание ошибки: {}\r\nНачало работы: {}\r\nОкончание работы: {}'.format(task['eventChainId'], task['descriptionId'], task['entityName'], task['username'], task['state'], task['error'], task['startTime'].astimezone(timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M'), task['completeTime'].astimezone(timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M'))
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
    return True in [t.isAlive() for t in threads]


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
            time.sleep(10)


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
        updater = Updater(token=cfg['telegram']['token'], request_kwargs=REQUEST_KWARGS)
    else:
        updater = Updater(token=cfg['telegram']['token'])

    dp = updater.dispatcher
    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help)
    list_handler = CommandHandler('vmlisttask', list_running_task)
    subscribe_all_handler = CommandHandler('vmsuball', subscribe_all_task, pass_args=False)
    subscribe_handler = CommandHandler('vmsub', subscribe_task, pass_args=True)
    unsubscribe_all_handler = CommandHandler('vmunsuball', unsubscribe_all_task, pass_args=False)
    unsubscribe_handler = CommandHandler('vmunsub', unsubscribe_task, pass_args=True)
    list_subscription_handler = CommandHandler('vmlistsub', list_subscription)
    unknown_handler = MessageHandler(Filters.command, unknown)

    dp.add_handler(start_handler)
    dp.add_handler(help_handler)
    dp.add_handler(list_handler)
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
            [t.join(1) for t in threads if t is not None and t.isAlive()]
        except KeyboardInterrupt:
            t2.kill_received = True
            try:
                updater.stop()
                t1.join()
            except:
                continue
    print('Exited')
    sys.exit(0)


if __name__ == '__main__':
    main()
