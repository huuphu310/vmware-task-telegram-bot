# -*- coding: utf-8 -*-
from pyVmomi import vim
from pyVim.connect import SmartConnectNoSSL, Disconnect
import atexit


class vCenterException(RuntimeError):
    """An VMWare vCenter error occured."""


class vCenter(object):
    def __init__(self, server, username, password):
        self.server = server
        self.username = username
        self.password = password
        self.SI = None

        try:
            self.SI = SmartConnectNoSSL(host=self.server,
                                        user=self.username,
                                        pwd=self.password)
            atexit.register(Disconnect, self.SI)
        except IOError as e:
            vCenterException(e)
        pass

        if not self.SI:
            vCenterException("Unable to connect to host with supplied info.")

    def format_task(self, task_info):
        if task_info.state == 'success':
            result = {'entityName': task_info.entityName,
                      'descriptionId': task_info.descriptionId,
                      'state': task_info.state,
                      'startTime': task_info.startTime,
                      'completeTime': task_info.completeTime,
                      'eventChainId': task_info.task.info.eventChainId,
                      'username': task_info.reason.userName}

        elif task_info.state == 'running':
            result = {'entityName': task_info.task.info.entityName,
                      'descriptionId': task_info.task.info.descriptionId,
                      'state': task_info.task.info.state,
                      'progress': task_info.task.info.progress,
                      'startTime': task_info.task.info.startTime,
                      'eventChainId': task_info.task.info.eventChainId,
                      'username': task_info.task.info.reason.userName}

        elif task_info.state == 'queued':
            result = {'entityName': task_info.task.info.entityName,
                      'descriptionId': task_info.task.info.descriptionId,
                      'state': task_info.task.info.state,
                      'progress': task_info.task.info.progress,
                      'startTime': task_info.task.info.startTime,
                      'eventChainId': task_info.task.info.eventChainId,
                      'username': task_info.task.info.reason.userName}

        elif task_info.state == 'error':
            result = {'entityName': task_info.entityName,
                      'descriptionId': task_info.descriptionId,
                      'state': task_info.state,
                      'error': task_info.error,
                      'startTime': task_info.startTime,
                      'completeTime': task_info.completeTime,
                      'username': task_info.reason.userName}

        return result

    def format_alarm(self, alarm):
        result = {'entityName': alarm.entity.name,
                  'description': alarm.alarm.info.name,
                  'status': alarm.overallStatus,
                  'time': alarm.time}
        return result

    def list_active_alarm(self):
        result = []
        try:
            alarms = self.SI.RetrieveContent().rootFolder.triggeredAlarmState
        except Exception as exc:
            raise vCenterException(exc)
        else:
            for alarm in alarms:
                try:
                    item = self.format_alarm(alarm)
                    result.append(item)
                except Exception as exc:
                    raise vCenterException(exc)
        return result

    def list_running_task(self):
        result = []
        taskManager = self.SI.content.taskManager
        tasks = taskManager.CreateCollectorForTasks(vim.TaskFilterSpec(state='running'))
        tasks.ResetCollector()
        try:
            alltasks = tasks.ReadNextTasks(999)
        except Exception as exc:
            raise vCenterException(exc)
        else:
            for task_item in alltasks:
                try:
                    item = self.format_task(task_item)
                    result.append(item)
                except Exception as exc:
                    raise vCenterException(exc)
            tasks.DestroyCollector()
        return result

    def get_task(self, id):
        result = []
        taskManager = self.SI.content.taskManager
        tasks = taskManager.CreateCollectorForTasks(vim.TaskFilterSpec(eventChainId=[int(id)]))
        tasks.ResetCollector()
        try:
            alltasks = tasks.ReadNextTasks(999)
        except Exception as exc:
            raise vCenterException(exc)
        else:
            for task_item in alltasks:
                try:
                    item = self.format_task(task_item)
                    result.append(item)
                except Exception as exc:
                    raise vCenterException(exc)
            tasks.DestroyCollector()
        return result

    def check_task_exist(self, id):
        try:
            alltasks = self.get_task(id)
        except Exception as exc:
            raise vCenterException(exc)
        else:
            try:
                for task_item in alltasks:
                    if task_item['state'] == 'running':
                        return True
            except Exception as exc:
                raise vCenterException(exc)
            return False
