from pyrfc3339 import parse

import MySQLdb as mdb
import MySQLdb.cursors as cursors

import logging

from .config import DATABASE, DEBUG

log = logging.getLogger()
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.ERROR)

DEFAULT_HOST = DATABASE['host']
DEFAULT_USER = DATABASE['user']
DEFAULT_PASS = DATABASE['pass'] 
DEFAULT_NAME = DATABASE['name']


SQLDATE_FMT = '%Y-%m-%d %H:%M:%S'

def EscapeString(value):
    #value = value.encode('unicode-escape').replace('"', '\\"')
    value = value.replace('"', '\\"')
    return '"{}"'.format(value)

def SQLdatetime(pydatetime_or_string):
    if hasattr(pydatetime_or_string, 'strftime'):
        dtobj = pydatetime_or_string
    else:
        # assume pyrfc3339 string
        dtobj = parse(pydatetime_or_string)
    return dtobj.strftime(SQLDATE_FMT)

class SQLData(object):
    """
    MySQL base class for config, select, insert, update, and delete in MySQL databases.
    """
    def __init__(self, *args, **kwargs):
        self._db_host = kwargs.get('host', None) or DEFAULT_HOST
        self._db_user = kwargs.get('user', None) or DEFAULT_USER
        self._db_pass = kwargs.get('pass', None) or DEFAULT_PASS
        self._db_name = kwargs.get('name', None) or DEFAULT_NAME

    def connect(self):
        return MySQLdb.getNewConnection(username=self._db_user, 
                password=self._db_pass, host=self._db_host, db=self._db_name,
		charset='utf8', use_unicode=True)

    def cursor(self, execute_sql=None):
        conn = self.connect()
        cursor = conn.cursor(cursors.DictCursor)

        if execute_sql is not None:
            cursor.execute(execute_sql)

        return [conn, cursor]

    def fetchall(self, select_sql):
        try:
            return self.execute(select_sql).record
        #except mdb.Error, e:
        #    log.warn(e)
        #    return None
        except TypeError:
            # no results
            return None

    def fetchrow(self, select_sql):
        results = self.fetchall(select_sql)
        return results[0] if results else None

    def fetchID(self, select_sql, id_colname='ID'):
        try:
            return self.fetchrow(select_sql)[id_colname]
        except TypeError:
            return None

    def results2set(self, select_sql, col):
        things = set()
        for row in self.fetchall(select_sql):
            things.add(str(row[col]))
        return things

    def insert(self, tablename, field_value_dict):
        '''
        :param: tablename: name of table to receive new row
        :param: field_value_dict: map of field=value
        :return: row_id (integer) (returns 0 if insert failed)
        '''
        fields = []
        values = []

        for k,v in field_value_dict.items():
            if v==None:
                continue
            fields.append(k)
            # surround strings and datetimes with quotation marks
            if hasattr(v, 'strftime'):
                v = '"%s"' % v.strftime(SQLDATE_FMT)
            elif hasattr(v, 'lower'):
                v = '%s' % EscapeString(v)
            else:
                v = str(v)

            values.append(v)

        sql = 'insert into %s (%s) values (%s);' % (tablename, ','.join(fields), ','.join(values)) 
        queryobj = self.execute(sql)
        # retrieve and return the row id of the insert. returns 0 if insert failed.
        return queryobj.lastInsertID

    def drop_table(self, tablename):
        return self.execute(' drop table if exists ' + tablename)

    def truncate(self, tablename):
        return self.execute(" truncate " + tablename)

    def execute(self, sql):
        log.debug('SQL.execute ' + sql)
        log.debug('#######')
        queryobj = MySQLdb.getNewQuery(self.connect(), commitOnEnd=True)
        queryobj.Query(sql)
        return queryobj

    def ping(self):
        """
        Same effect as calling 'mysql> call mem'
        :returns::self.schema_info(()
        """
        try:
            return self.schema_info()

        except mdb.Error as error:
            log.error("DB connection is dead %d: %s" % (error.args[0], error.args[1]))
            return False

    def schema_info(self):
        header = ['schema', 'engine', 'table', 'rows', 'million', 'data length', 'MB', 'index']
        return {'header': header, 'tables': self.fetchall('call mem')}

