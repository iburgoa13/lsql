# -*- coding: utf-8 -*-
"""
Copyright Enrique Martín <emartinm@ucm.es> 2020

Class to connect to Oracle and execute the different types of problems
"""

# Needed to use cx_Oracle
# export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/home/kike/xDownload/instantclient_19_6

import time
import string
import random
import os
import cx_Oracle
from logzero import logger
import sqlparse

from .exceptions import ExecutorException
from .types import OracleStatusCode


def clean_sql(code, min_stmt=None, max_stmt=None):
    """
    Parses SQL code into statements (removing comments and empty lines).
    :param code: str containing SQL code
    :param min_stmt: minimum number of statements
    :param max_stmt: maximum number of statements
    :return: [str] if code is a sequence between min_stmt and max_stmt correct SQL statements.
    """
    if code is None:
        code = ""
    statements = [sqlparse.format(s, strip_comments=True).rstrip('\n\t ;') for s in sqlparse.split(code)]
    statements = [s for s in statements if len(s) > 0]
    num_sql = len(statements)
    if (min_stmt and num_sql < min_stmt) or (max_stmt and num_sql > max_stmt):
        statements = None
    return statements


def random_str(alphabet, size=8):
    """
    Creates a random string of 'n' letters from 'alphabet'
    :param alphabet: Candidate letters
    :param size: Lenght of the generated random string
    :return: Random string of 'n' letters from 'alphabet'
    """
    ret = ''
    for _ in range(size):
        ret += random.choice(alphabet)
    return ret


def table_from_cursor(cursor):
    """
    Takes a cursor that has executed a SELECT statement and returns all the results
    in a dictionary. It checks if the number of columns in the cursor exceeds
    ORACLE_MAX_COLS or the number of rows exceeds ORACLE_MAX_ROWS. In those cases
    raises an ExecutorException with status code OracleStatusCode.TLE_USER_CODE
    :param cursor: DB cursor
    :return: a dictionary {'header':[[NAME:str, TYPE:str]], 'rows': [list]}
    """
    max_rows = int(os.environ['ORACLE_MAX_ROWS'])
    table = dict()

    if len(cursor.description) > int(os.environ['ORACLE_MAX_COLS']):
        logger.debug('Too many columns in cursor')
        raise ExecutorException(OracleStatusCode.TLE_USER_CODE)
    table['header'] = [[e[0], str(e[1])] for e in cursor.description]

    batch = cursor.fetchmany(numRows=max_rows)  # Takes MAX rows
    if cursor.fetchone():  # There are more rows
        logger.debug('Too many rows in cursor')
        raise ExecutorException(OracleStatusCode.TLE_USER_CODE)
    table['rows'] = [list(e) for e in batch]

    return table


def get_all_tables(conn):
    """
    Returns a dictionary representing all the tables in the DB. It checks if the
    number of tables owned by the user exceeds ORACLE_MAX_TABLES, and raises an
    ExecutorException with status code OracleStatusCode.TLE_USER_CODE
    :param conn: DB connection
    :return: dictionary {table_name: TABLE}, where TABLE is the dictionary
             generated by table_from_cursor
    """
    with conn.cursor() as cursor:
        cursor.execute("SELECT table_name FROM USER_TABLES")
        tables = cursor.fetchmany(int(os.environ['ORACLE_MAX_TABLES']))
        if cursor.fetchone():
            logger.debug('Too many tables in user DB')
            raise ExecutorException(OracleStatusCode.TLE_USER_CODE)
        tb_names = [e[0] for e in tables]
        db_dict = dict()
        for table_name in tb_names:
            table = None
            # https://docs.oracle.com/database/121/SQLRF/sql_elements008.htm#SQLRF51129
            # Quoted names should be embedded with "..." in order to work. We try
            # both versions for table names, ignoring possible exceptions.
            try:
                cursor.execute("SELECT * FROM {}".format(table_name))  # Direct name
            except cx_Oracle.DatabaseError:
                cursor.execute('SELECT * FROM "{}"'.format(table_name))  # Quoted name
            table = table_from_cursor(cursor)
            db_dict[table_name] = table

        return db_dict


def execute_select_statement(conn, statement):
    """
    Given a connection to an Oracle database, executes a string containing exactly ONE statement
    :param conn: Oracle connection
    :param statement: String containing one SQL Select statement
    :return: List with the results of the SELECT statement. It raises an IncorrectNumberOfSentences
             exception if 'statement' contains more than one SQL statement, and a
             cx_Oracle.DatabaseError if the execution of the statements is not correct
    """
    init = time.time()
    statements = clean_sql(statement)
    if len(statements) != 1:
        logger.debug('User %s - <<%s>> contains more than one SQL statement',
                     conn.username, statement)
        raise ExecutorException(OracleStatusCode.NUMBER_STATEMENTS)

    with conn.cursor() as cursor:
        cursor.execute(statements[0])
        # conn.commit()
        logger.debug('User %s - SQL select statement <<%s>> executed in %s seconds',
                     conn.username, statements[0], time.time() - init)
        table = table_from_cursor(cursor)
    return table


def execute_dml_statements(conn, dml, min_stmt=0, max_stmt=float("inf")):
    """
    Given a connection to an Oracle database, executes a string containing DML statements
    :param min_stmt:
    :param max_stmt:
    :param conn: Oracle connection
    :param dml: String containing DML statements
    :return: None
    """
    init = time.time()
    statements = clean_sql(dml, min_stmt, max_stmt)
    with conn.cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)
            logger.debug('User %s - SQL DML statement <<%s>> executed in %s seconds',
                         conn.username, stmt, time.time() - init)
        conn.commit()


def execute_sql_script(conn, script):
    """
    Given an Oracle connection, executes a script formed by one or more statements
    :param conn: Oracle connection
    :param script: String containing one or more SQL statements (DDL, DML, etc)
    :return: None. It raises a cx_Oracle.DatabaseError if the execution of any of the
             statements is not correct.
    """
    init = time.time()
    statements = clean_sql(script)
    if len(statements) > 0:
        with conn.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
            conn.commit()
            logger.debug('User %s - SQL script <<%s>> executed in %s seconds',
                         conn.username, statements, time.time() - init)


# Dropping users will automatically remove all their objects
# I keep this function just in case is useful in the future
# def empty_schema(conn):
#     """
#     Completely empties the current schema in the connection, i.e., drops all user objects.
#     Captures any exception caused by any DROP statement or the SELECT used to find user objects
#     :param conn: open connection to an Oracle DB
#     :return: bool
#     """
#     init = time.time()
#     correct = True
#     try:
#         sql = """
#             select 'DROP '||object_type||' '|| object_name|| DECODE(OBJECT_TYPE,'TABLE',' CASCADE CONSTRAINTS','')
#             from user_objects"""
#         with conn.cursor() as cursor:
#             cursor.execute(sql)
#             drop_statements = [p[0] for p in cursor]
#             for drop in drop_statements:
#                 cursor.execute(drop)
#     except cx_Oracle.DatabaseError:
#         correct = False
#
#     if correct:
#         logger.debug('User %s - Schema deleted in %s seconds',
#                      conn.username, time.time() - init)
#     else:
#         logger.error('User %s - Unable to delete schema', conn.username)
#     return correct


def build_dsn_tns():
    """Build a Data Source Name from values in the environment"""
    dsn_tns = cx_Oracle.makedsn(
        os.environ['ORACLE_SERVER'],
        int(os.environ['ORACLE_PORT']),
        os.environ['ORACLE_SID'])
    return dsn_tns


class OracleExecutor:
    """Class to connecto to Oracle DB and execute problems"""

    __USER_PREFIX = 'lsql_'
    __ALPHABET = string.ascii_lowercase + string.digits
    __CREATE_USER_SCRIPT = ('CREATE USER {} '
                            'IDENTIFIED BY "{}" '
                            'DEFAULT TABLESPACE {} '
                            'TEMPORARY TABLESPACE TEMP QUOTA UNLIMITED ON {}')
    __GRANT_USER_SCRIPT = ('GRANT create table, delete any table, select any dictionary, connect, create session , '
                           'create synonym , create public synonym, create sequence, create view , '
                           'create trigger, alter any trigger, drop any trigger, '
                           'create procedure, alter any procedure, drop any procedure, execute any procedure '
                           'TO {}')
    __DROP_USER_SCRIPT = 'DROP USER {} CASCADE'
    __USER_CONNECTIONS = "select sid, serial# from v$session where username = '{}'"
    __SLEEP_AFTER_TIMEOUT = 100
    # milliseconds to sleep after a timeout when obtaining a
    # a timeout error, so that user connections can be properly
    # closed (otherwise, DROP USER throws an 'ORA-01940: cannot
    # drop a user that is currently connected')

    __DB = None

    @classmethod
    def get(cls):
        """Singleton DB"""
        if cls.__DB is None:
            cls.__DB = OracleExecutor()
        return cls.__DB

    def __init__(self):
        """
        Creates a pool of connections with the admin user, taking the details from
        the configuration file. Throws a cx_Oracle.DatabaseError if it is not
        possible to cretate the pool
        """
        self.dsn_tns = build_dsn_tns()
        self.connection_pool = cx_Oracle.SessionPool(
            os.environ['ORACLE_USER'],
            os.environ['ORACLE_PASS'],
            self.dsn_tns,
            threaded=True,
            encoding='UTF-8', nencoding='UTF-8',
            min=1,
            max=int(os.environ['ORACLE_MAX_GESTOR_CONNECTIONS']),
            getmode=cx_Oracle.SPOOL_ATTRVAL_TIMEDWAIT,
            waitTimeout=int(os.environ['ORACLE_GESTOR_POOL_TIMEOUT_MS'])
        )
        self.version = None
        logger.debug('Created an OracleExecutor to %s with a pool of %s connections with a timeout of %s ms',
                     self.dsn_tns,
                     int(os.environ['ORACLE_MAX_GESTOR_CONNECTIONS']),
                     int(os.environ['ORACLE_GESTOR_POOL_TIMEOUT_MS'])
                     )

    def get_version(self):
        """Returns the version of the Oracle server"""
        if not self.version:
            gestor = self.connection_pool.acquire()
            self.version = f'Oracle {gestor.version}'
            self.connection_pool.release(gestor)
        return self.version

    def create_user(self, connection):
        """
        Creates a new user in the local Oracle DB with a random name and password. The user
        has acces to the TABLESPACE defined in the configuration file, and its username
        starts with a given prefix defined in the configuration file
        :param connection: Connection with privileges for creating users
        :return: A pair (username, password) of the created user
        """
        user_name = self.__USER_PREFIX + random_str(self.__ALPHABET)
        user_passwd = random_str(self.__ALPHABET)
        create_script = self.__CREATE_USER_SCRIPT.format(
            user_name,
            user_passwd,
            os.environ['ORACLE_TABLESPACE'],
            os.environ['ORACLE_TABLESPACE']
        )
        grant_script = self.__GRANT_USER_SCRIPT.format(user_name)

        with connection.cursor() as cursor:
            cursor.execute(create_script)
            logger.debug('User %s - Created user %s', connection.username, user_name)
            cursor.execute(grant_script)
        logger.debug('User %s - Granted privileges to user %s', connection.username, user_name)
        return user_name, user_passwd

    def drop_user(self, user_name, connection):
        """
        Removes a user from the Oracle local DB
        :param user_name: Name of the user to remove
        :param connection: Connection with priviledges to drop users
        :return: None
        """
        user_connections_script = self.__USER_CONNECTIONS.format(user_name)
        with connection.cursor() as cursor:
            cursor.execute(user_connections_script)
            active_connections = cursor.fetchall()
            logger.debug('User %s has %s active connections', user_name, len(active_connections))
            drop_script = self.__DROP_USER_SCRIPT.format(user_name)
            cursor.execute(drop_script)
        logger.debug('User %s - Dropped user %s', connection.username, user_name)

    def create_connection(self, user, passwd):
        """
        Creates an Oracle connection to localhost/xe using UTF-8
        :param user: Name of the Oracle user
        :param passwd: Password of the Oracle user
        :return: Oracle connection
        """
        connection = cx_Oracle.connect(user, passwd, self.dsn_tns, encoding='UTF-8', nencoding='UTF-8')
        return connection

    def execute_select_test(self, creation, insertion, select, output_db=False):
        """
        Using a new fresh user, creates a set of tables ('creation) and inserts some data.
        Then, executes a correct SELECT statement and also a SELECT statement to test
        :param output_db:
        :param creation: (str) Statements to create the tables and other structures
        :param insertion: (str) Statements to insert data into tables
        :param select: (str) One SELECT statement to execute
        :return: {"result": result, "db": db}. result is a dictionary representing the statement result, and db is a
                 dictionary representing all the tables. In case of error, throws a ExecutorException
        """
        conn, gestor, result, user, db = None, None, None, None, None
        state = OracleStatusCode.GET_ADMIN_CONNECTION
        try:
            gestor = self.connection_pool.acquire()

            state = OracleStatusCode.CREATE_USER
            user, passwd = self.create_user(gestor)

            state = OracleStatusCode.GET_USER_CONNECTION
            conn = self.create_connection(user, passwd)

            conn.callTimeout = int(os.environ['ORACLE_STMT_TIMEOUT_MS'])
            state = OracleStatusCode.EXECUTE_CREATE
            execute_sql_script(conn, creation)

            state = OracleStatusCode.EXECUTE_INSERT
            execute_sql_script(conn, insertion)

            state = OracleStatusCode.EXECUTE_USER_CODE
            result = execute_select_statement(conn, select)

            state = OracleStatusCode.GET_ALL_TABLES
            if output_db:
                db = get_all_tables(conn)

            state = OracleStatusCode.CLOSE_USER_CONNECTION
            conn.close()
            conn = None

            state = OracleStatusCode.DROP_USER
            self.drop_user(user, gestor)
            user = None

            state = OracleStatusCode.RELEASE_ADMIN_CONNECTION
            self.connection_pool.release(gestor)
            gestor = None
            return {"result": result, "db": db}
        except cx_Oracle.DatabaseError as excp:
            # Workaround to fix some odd problem when failing to get connections from the pool
            # But now it is not happening and I do not know how to re-produce it.
            # if 'timeout' in str(e):
            #     sleep(self.__SLEEP_AFTER_TIMEOUT / 1000)
            error_msg = str(excp)
            logger.info('Error when testing SELECT statements: %s - %s - %s', state, excp, select)
            if 'ORA-3156' in error_msg and state == OracleStatusCode.EXECUTE_USER_CODE:
                raise ExecutorException(OracleStatusCode.TLE_USER_CODE, error_msg, select) from excp
            raise ExecutorException(state, error_msg, select) from excp
        finally:
            if conn:
                conn.close()
            if user:
                self.drop_user(user, gestor)
            if gestor:
                self.connection_pool.release(gestor)

    def execute_dml_test(self, creation, insertion, dml, pre_db=True, min_stmt=0, max_stmt=float("inf")):
        """
        Using a new fresh user, creates a set of tables ('creation) and inserts some data.
        Then, executes some DML statements
        :param max_stmt:
        :param min_stmt:
        :param pre_db:
        :param creation: (str) Statements to create the tables and other structures
        :param insertion: (str) Statements to insert data into tables
        :param dml: (str) DML statements to execute (insert, delete, update)
        :return: {'pre': DB, 'post': DB} dictionary containing the state of the DB before and after executing dml
        """
        conn, gestor, user, post, stmt = None, None, None, None, None
        state = OracleStatusCode.GET_ADMIN_CONNECTION
        try:
            gestor = self.connection_pool.acquire()

            state = OracleStatusCode.CREATE_USER
            user, passwd = self.create_user(gestor)

            state = OracleStatusCode.GET_USER_CONNECTION
            conn = self.create_connection(user, passwd)

            conn.callTimeout = int(os.environ['ORACLE_STMT_TIMEOUT_MS'])
            state = OracleStatusCode.EXECUTE_CREATE
            execute_sql_script(conn, creation)

            state = OracleStatusCode.EXECUTE_INSERT
            execute_sql_script(conn, insertion)

            pre = dict()
            if pre_db:
                state = OracleStatusCode.GET_ALL_TABLES
                pre = get_all_tables(conn)

            state = OracleStatusCode.EXECUTE_USER_CODE
            init = time.time()
            statements = clean_sql(dml, min_stmt, max_stmt)
            if not statements:
                logger.debug('User %s - <<%s>> contains more unexpected number of statements [%s - %s]',
                             conn.username, statements, min_stmt, max_stmt)
                raise ExecutorException(OracleStatusCode.NUMBER_STATEMENTS)
            with conn.cursor() as cursor:
                for stmt in statements:
                    cursor.execute(stmt)
                conn.commit()

            logger.debug('User %s - SQL DML statements <<%s>> executed in %s seconds',
                         conn.username, statements, time.time() - init)

            state = OracleStatusCode.GET_ALL_TABLES
            post = get_all_tables(conn)

            state = OracleStatusCode.CLOSE_USER_CONNECTION
            conn.close()
            conn = None

            state = OracleStatusCode.DROP_USER
            self.drop_user(user, gestor)
            user = None

            state = OracleStatusCode.RELEASE_ADMIN_CONNECTION
            self.connection_pool.release(gestor)
            gestor = None

            return {'pre': pre, 'post': post}
        except cx_Oracle.DatabaseError as excp:
            # Workaround to fix some odd problem when failing to get connections from the pool
            # But now it is not happening and I do not know how to re-produce it.
            # if 'timeout' in str(e):
            #     sleep(self.__SLEEP_AFTER_TIMEOUT / 1000)
            error_msg = str(excp)
            logger.info('Error when testing DML statements: %s - %s - %s', state, excp, stmt)
            if 'ORA-3156' in error_msg and state == OracleStatusCode.EXECUTE_USER_CODE:
                raise ExecutorException(OracleStatusCode.TLE_USER_CODE, error_msg, stmt) from excp
            raise ExecutorException(state, error_msg, stmt) from excp
        finally:
            if conn:
                conn.close()
            if user:
                self.drop_user(user, gestor)
            if gestor:
                self.connection_pool.release(gestor)

    def execute_function_test(self, creation, insertion, func_creation, tests):
        """
        Using a new fresh user, creates a set of tables ('creation) and inserts some data.
        Then, executes some DML statements
        :param tests: (str) function calls separated by new lines
        :param func_creation:
        :param creation: (str) Statements to create the tables and other structures
        :param insertion: (str) Statements to insert data into tables

        :return: {'pre': DB, 'results': dict} dictionary containing the initial state of the DB and a dictionary
                 {call: result} with the different calls and its expected result
        """
        conn, gestor, user, stmt = None, None, None, None
        state = OracleStatusCode.GET_ADMIN_CONNECTION
        try:
            gestor = self.connection_pool.acquire()

            state = OracleStatusCode.CREATE_USER
            user, passwd = self.create_user(gestor)

            state = OracleStatusCode.GET_USER_CONNECTION
            conn = self.create_connection(user, passwd)

            conn.callTimeout = int(os.environ['ORACLE_STMT_TIMEOUT_MS'])
            state = OracleStatusCode.EXECUTE_CREATE
            execute_sql_script(conn, creation)

            state = OracleStatusCode.EXECUTE_INSERT
            execute_sql_script(conn, insertion)

            state = OracleStatusCode.GET_ALL_TABLES
            db = get_all_tables(conn)

            state = OracleStatusCode.EXECUTE_USER_CODE
            init = time.time()

            # sqlparse does not consider the whole CREATE FUNCTION as a single statement, so we cannot check
            # the minimum and maximum number of statements in this kind of problems :-(

            with conn.cursor() as cursor:
                stmt = func_creation
                cursor.execute(stmt)

                # Stops if there is some compilation error with the function
                # We must handle it manually because executing a FUNCTION creation with failures does not throw
                # any Oracle exception
                cursor.execute('''SELECT NAME "Nombre de función", LINE "Línea", POSITION "Posición",
                                         TEXT "Error detectado", ATTRIBUTE "Criticidad" 
                                  FROM SYS.USER_ERRORS 
                                  WHERE TYPE = \'FUNCTION\'''')
                errors = table_from_cursor(cursor)
                if len(errors['rows']) > 0:
                    raise ExecutorException(OracleStatusCode.COMPILATION_ERROR, message=errors, statement=stmt)

                results = dict()
                tests = [s.strip() for s in tests.split('\n') if len(s.strip()) > 0]
                for stmt in tests:
                    func_call = f'SELECT {stmt} FROM DUAL'
                    cursor.execute(func_call)
                    row = cursor.fetchone()
                    results[stmt] = row[0]

            logger.debug('User %s - Function creation and testing executed in %s seconds',
                         conn.username, time.time() - init)

            state = OracleStatusCode.CLOSE_USER_CONNECTION
            conn.close()
            conn = None

            state = OracleStatusCode.DROP_USER
            self.drop_user(user, gestor)
            user = None

            state = OracleStatusCode.RELEASE_ADMIN_CONNECTION
            self.connection_pool.release(gestor)
            gestor = None

            return {'db': db, 'results': results}
        except cx_Oracle.DatabaseError as excp:
            # Workaround to fix some odd problem when failing to get connections from the pool
            # But now it is not happening and I do not know how to re-produce it.
            # if 'timeout' in str(e):
            #     sleep(self.__SLEEP_AFTER_TIMEOUT / 1000)
            logger.info('Error when testing function statements: %s - %s - %s',
                        state, excp, stmt)
            if 'ORA-3156' in str(excp) and state == OracleStatusCode.EXECUTE_USER_CODE:
                raise ExecutorException(OracleStatusCode.TLE_USER_CODE, excp, stmt) from excp
            raise ExecutorException(state, excp, stmt) from excp
        finally:
            if conn:
                conn.close()
            if user:
                self.drop_user(user, gestor)
            if gestor:
                self.connection_pool.release(gestor)

    def execute_proc_test(self, creation, insertion, proc_creation, proc_call, pre_db=True):
        """
        Using a new fresh user, creates a set of tables ('creation) and inserts some data.
        Then, creates a PROCEDURE defined in proc_creation and invokes the call in proc_call
        :param pre_db:
        :param proc_call:
        :param proc_creation:
        :param creation: (str) Statements to create the tables and other structures
        :param insertion: (str) Statements to insert data into tables

        :return: {'pre': DB, 'post': DB} dictionary containing the state of the DB before defining the procedure and
                   and after invoking the procedure
        """
        conn, gestor, user, post, stmt = None, None, None, None, None
        state = OracleStatusCode.GET_ADMIN_CONNECTION
        try:
            gestor = self.connection_pool.acquire()

            state = OracleStatusCode.CREATE_USER
            user, passwd = self.create_user(gestor)

            state = OracleStatusCode.GET_USER_CONNECTION
            conn = self.create_connection(user, passwd)

            conn.callTimeout = int(os.environ['ORACLE_STMT_TIMEOUT_MS'])
            state = OracleStatusCode.EXECUTE_CREATE
            execute_sql_script(conn, creation)

            state = OracleStatusCode.EXECUTE_INSERT
            execute_sql_script(conn, insertion)

            db = None
            if pre_db:
                state = OracleStatusCode.GET_ALL_TABLES
                db = get_all_tables(conn)

            state = OracleStatusCode.EXECUTE_USER_CODE
            init = time.time()

            # sqlparse does not consider the whole CREATE PROCEDURE as a single statement, so we cannot check
            # the minimum and maximum number of statements in this kind of problems :-(

            with conn.cursor() as cursor:
                stmt = proc_creation
                cursor.execute(stmt)

                cursor.execute('''SELECT NAME "Nombre de procedimiento", LINE "Línea", POSITION "Posición",
                                         TEXT "Error detectado", ATTRIBUTE "Criticidad" 
                                  FROM SYS.USER_ERRORS 
                                  WHERE TYPE = \'PROCEDURE\'''')
                errors = table_from_cursor(cursor)
                if len(errors['rows']) > 0:
                    raise ExecutorException(OracleStatusCode.COMPILATION_ERROR, message=errors, statement=stmt)

                stmt = f"BEGIN {proc_call.strip()}; END;"
                cursor.execute(stmt)

            state = OracleStatusCode.GET_ALL_TABLES
            post = get_all_tables(conn)

            logger.debug('User %s - Procedure creation and testing executed in %s seconds',
                         conn.username, time.time() - init)

            state = OracleStatusCode.CLOSE_USER_CONNECTION
            conn.close()
            conn = None

            state = OracleStatusCode.DROP_USER
            self.drop_user(user, gestor)
            user = None

            state = OracleStatusCode.RELEASE_ADMIN_CONNECTION
            self.connection_pool.release(gestor)
            gestor = None

            return {'pre': db, 'post': post}
        except cx_Oracle.DatabaseError as excp:
            # Workaround to fix some odd problem when failing to get connections from the pool
            # But now it is not happening and I do not know how to re-produce it.
            # if 'timeout' in str(e):
            #     sleep(self.__SLEEP_AFTER_TIMEOUT / 1000)
            error_msg = str(excp)
            logger.info('Error when testing procedure creation and call: %s - %s - %s',
                        state, excp, stmt)
            if 'ORA-3156' in error_msg and state == OracleStatusCode.EXECUTE_USER_CODE:
                raise ExecutorException(OracleStatusCode.TLE_USER_CODE, error_msg, stmt) from excp
            raise ExecutorException(state, error_msg, stmt) from excp
        finally:
            if conn:
                conn.close()
            if user:
                self.drop_user(user, gestor)
            if gestor:
                self.connection_pool.release(gestor)

    def execute_trigger_test(self, creation, insertion, trigger_definition, tests, pre_db=True):
        """
        Using a new fresh user, creates a set of tables ('creation) and inserts some data.
        Then, creates a PROCEDURE defined in proc_creation and invokes the call in proc_call
        :param pre_db:
        :param tests: (str) 1 or more DML statements that should invoke the trigger
        :param trigger_definition:
        :param creation: (str) Statements to create the tables and other structures
        :param insertion: (str) Statements to insert data into tables

        :return: {'pre': DB, 'post': DB} dictionary containing the state of the DB before defining the trigger and
                   and after executing the tests
        """
        conn, gestor, user, post, stmt = None, None, None, None, None
        state = OracleStatusCode.GET_ADMIN_CONNECTION
        try:
            gestor = self.connection_pool.acquire()

            state = OracleStatusCode.CREATE_USER
            user, passwd = self.create_user(gestor)

            state = OracleStatusCode.GET_USER_CONNECTION
            conn = self.create_connection(user, passwd)

            conn.callTimeout = int(os.environ['ORACLE_STMT_TIMEOUT_MS'])
            state = OracleStatusCode.EXECUTE_CREATE
            execute_sql_script(conn, creation)

            state = OracleStatusCode.EXECUTE_INSERT
            execute_sql_script(conn, insertion)

            db = None
            if pre_db:
                state = OracleStatusCode.GET_ALL_TABLES
                db = get_all_tables(conn)

            state = OracleStatusCode.EXECUTE_USER_CODE
            init = time.time()

            # sqlparse does not consider the whole CREATE TRIGGER as a single statement, so we cannot check
            # the minimum and maximum number of statements in this kind of problems :-(

            with conn.cursor() as cursor:
                stmt = trigger_definition
                cursor.execute(stmt)
            # cx_Oracle does not seem to compile trigger at this point. Syntax error in the trigger will be detected
            # when firing the trigger

            execute_dml_statements(conn, tests)

            state = OracleStatusCode.GET_ALL_TABLES
            post = get_all_tables(conn)

            logger.debug('User %s - Procedure creation and testing executed in %s seconds',
                         conn.username, time.time() - init)

            state = OracleStatusCode.CLOSE_USER_CONNECTION
            conn.close()
            conn = None

            state = OracleStatusCode.DROP_USER
            self.drop_user(user, gestor)
            user = None

            state = OracleStatusCode.RELEASE_ADMIN_CONNECTION
            self.connection_pool.release(gestor)
            gestor = None

            return {'pre': db, 'post': post}
        except cx_Oracle.DatabaseError as excp:
            # Workaround to fix some odd problem when failing to get connections from the pool
            # But now it is not happening and I do not know how to re-produce it.
            # if 'timeout' in str(e):
            #     sleep(self.__SLEEP_AFTER_TIMEOUT / 1000)
            error_msg = str(excp)
            logger.info('Error when testing procedure creation and call: %s - %s - %s',
                        state, excp, stmt)
            if 'ORA-3156' in error_msg and state == OracleStatusCode.EXECUTE_USER_CODE:
                raise ExecutorException(OracleStatusCode.TLE_USER_CODE, error_msg, stmt) from excp
            raise ExecutorException(state, error_msg, stmt) from excp
        finally:
            if conn:
                conn.close()
            if user:
                self.drop_user(user, gestor)
            if gestor:
                self.connection_pool.release(gestor)