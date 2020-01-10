# -*- coding: utf-8 -*-
import sqlite3


class DBException(RuntimeError):
    """An SQLite DB error occured."""


class DB(object):
    def __init__(self, db_path):
        try:
            self.conn = sqlite3.connect(db_path)
            self.cur = self.conn.cursor()
        except Exception as exc:
            raise DBException(exc)
        else:
            self.create_table()

    def create_table(self):
        sql = 'CREATE TABLE IF NOT EXISTS subscription (uid VARCHAR, taskid VARCHAR)'
        try:
            self.cur.execute(sql)
        except Exception as exc:
            self.cur.rollback()
            raise DBException(exc)
        else:
            self.conn.commit()

    def add_subscription(self, uid, task_id):
        sql = 'INSERT INTO subscription (uid, taskid) VALUES (?,?)'
        try:
            self.cur.execute(sql, (uid, task_id))
        except Exception as exc:
            self.conn.rollback()
            raise DBException(exc)
        else:
            self.conn.commit()

    def list_subscriptions(self):
        sql = 'SELECT * FROM subscription'
        try:
            data = self.cur.execute(sql).fetchall()
        except Exception as exc:
            raise DBException(exc)
        else:
            return data

    def get_subsciption(self, uid, task_id):
        sql = 'SELECT * FROM subscription WHERE uid = ? AND taskid=?'
        try:
            data = self.cur.execute(sql, (uid, task_id)).fetchall()
        except Exception as exc:
            raise DBException(exc)
        else:
            if data:
                return True
            else:
                return False

    def get_subsciption_by_uid(self, uid):
        sql = 'SELECT * FROM subscription WHERE uid = ?'
        try:
            data = self.cur.execute(sql, (uid,)).fetchall()
        except Exception as exc:
            raise DBException(exc)
        else:
            return data

    def remove_subscription(self, uid, task_id):
        sql = 'DELETE FROM subscription WHERE uid = ? AND taskid = ?'
        try:
            self.cur.execute(sql, (uid, task_id))
        except Exception as exc:
            self.cur.rollback()
            raise DBException(exc)
        else:
            self.conn.commit()
            self.vacuum_db()

    def remove_subscription_by_uid(self, uid):
        sql = 'DELETE FROM subscription WHERE uid = ?'
        try:
            self.cur.execute(sql, (uid,))
        except Exception as exc:
            self.cur.rollback()
            raise DBException(exc)
        else:
            self.conn.commit()
            self.vacuum_db()

    def vacuum_db(self):
        try:
            self.conn.execute('VACUUM')
        except Exception as exc:
            raise DBException(exc)
