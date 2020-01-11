==================================================================================================================================
vmware-task-telegram-bot - Telegram bot to notify about completion of VMware vCenter tasks and get information about active alarms
==================================================================================================================================


What is this?
*************
``vmware-task-telegram-bot`` provides an executable called ``vmware_task_bot``


Installation
************
*on most UNIX-like systems, you'll probably need to run the following
`install` commands as root or by using sudo*

**from source**

::

  pip install git+http://github.com/verdel/vmware-task-telegram-bot

**or**

::

  git clone git://github.com/verdel/vmware-task-telegram-bot.git
  cd vmware-task-telegram-bot
  python setup.py install

as a result, the ``vmware_task_bot`` executable will be installed into
a system ``bin`` directory

Usage
-----
    usage: vmware_task_bot [-h] [--debug]

    optional arguments:
      -h, --help  show this help message and exit
      -c CONFIG, --config CONFIG
                        configuration file
      --debug
