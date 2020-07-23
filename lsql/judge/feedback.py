# -*- coding: utf-8 -*-
"""
Copyright Enrique Martín <emartinm@ucm.es> 2020

Generation of feedback messages
"""
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
import re
from multiset import Multiset
import json

from .types import VeredictCode

__ORACLE_TYPE_PATTERN = r"<class 'cx_Oracle\.(.*)'>"


def pretty_type(type_str):
    match = re.match(__ORACLE_TYPE_PATTERN, type_str)
    if match:
        return match.group(1)
    else:
        return type_str


def header_to_str(header):
    """
    Transform a list of lists of two elements [name, cx_Oracle type] in a pretty string
    :param header: Something like [['ID', "<class 'cx_Oracle.NUMBER'>"], ['NOMBRE', "<class 'cx_Oracle.STRING'>"]]
    :return: (str) Pretty version like "(ID: NUMBER, NOMBRE: STRING)"
    """
    columns = list()
    for name, oracle_type in header:
        columns.append("{}: {}".format(name, pretty_type(oracle_type)))
    str_header = ", ".join(columns)
    return "(" + str_header + ")"


def feedback_headers(expected, obtained):
    """
    :param expected: expected result ({'header': list, 'rows': list})
    :param obtained: obtained result ({'header': list, 'rows': list})
    :return: (str) HTML code with the feedback, or '' if the headers are equal
    """
    if expected['header'] == obtained['header']:
        return ''
    else:
        return render_to_string('feedback_wa_headers.html',
                                {'expected': header_to_str(expected['header']),
                                 'obtained': header_to_str(obtained['header'])}
                                )


def table_to_html(table, row_remark=None):
    if not row_remark:
        row_remark = set()
    return "{}, {}".format(table, row_remark)


def feedback_rows(expected, obtained, order):
    """
    :param expected: expected result ({'header': list, 'rows': list})
    :param obtained: obtained result ({'header': list, 'rows': list})
    :param order: consider order when comparing rows
    :return: (str) HTML code with the feedback, or '' if the table rows are equal (considering order)
    """
    tupled_expected = [tuple(r) for r in expected['rows']]
    tupled_obtained = [tuple(r) for r in obtained['rows']]
    mset_expected = Multiset(tupled_expected)
    mset_obtained = Multiset(tupled_obtained)
    obtained_not_expected = mset_obtained - mset_expected

    if obtained_not_expected:
        # Some rows are not expected, get row numbers to mark them in the feedback
        incorrect_row_numbers = set()  # Starting from 0
        pos = 0
        while pos < len(tupled_obtained) and obtained_not_expected:
            if tupled_obtained[pos] in obtained_not_expected:
                incorrect_row_numbers.add(pos)
                obtained_not_expected.remove(tupled_obtained[pos], 1)  # Removes one appearance of that row
            pos = pos + 1
        feedback = render_to_string('feedback_wa_wrong_rows.html',
                                    {'table': {'header': expected['header'], 'rows': tupled_obtained},
                                     'name': None,
                                     'mark_rows': incorrect_row_numbers}
                                    )
        return feedback

    expected_not_obtained = mset_expected - mset_obtained
    if expected_not_obtained:
        feedback = render_to_string('feedback_wa_missing_rows.html',
                                    {'obtained': obtained,
                                     'missing': {'header': expected['header'], 'rows': expected_not_obtained},
                                     'mark_missing': set(list(range(len(expected_not_obtained))))}
                                    )
        return feedback

    if order and expected != obtained:
        return render_to_string('feedback_wa_order.html', {'expected': expected, 'obtained': obtained})

    return ''  # Everything OK => Accepted


def compare_select_results(expected, obtained, order):
    """
    :param expected: {'header': list, 'rows': list}, expected SELECT result (teacher).
    :param obtained: {'header': list, 'rows': list}, obtained SELECT result (student)
    :param order: Consider order when comparing rows
    :return: (veredict, feedback), where veredict is VeredictCode.AC or VeredictCode.WA and
             error is a str with feedback to the student
    """
    # Encodes and decodes the obtained results using the same JSONEncoder used to store the data in the DB
    # (otherwise dates are represented differently in the results from the DB and the results from Oracle)
    encoded = json.dumps(obtained, cls=DjangoJSONEncoder)
    obtained = json.loads(encoded)
    feedback = feedback_headers(expected, obtained)
    if not feedback:
        feedback = feedback_rows(expected, obtained, order)
    veredict = VeredictCode.WA if feedback else VeredictCode.AC
    return veredict, feedback


def compare_db_results(expected_db, obtained_db):
    """
    Given an expected DB and an obtained DB, returns a veredict of the comparison and its HTML feedback
    :param expected_db: dict {table_name: dict}
    :param obtained_db: dict {table_name: dict}
    :return: (VeredictCode, str)
    """
    feedback = ''
    expected_tables = set(expected_db.keys())
    obtained_tables = set(obtained_db.keys())

    if expected_tables != obtained_tables:
        obtained = sorted(list(obtained_db.keys()))
        expected = sorted(list(expected_db.keys()))
        return VeredictCode.WA, render_to_string('feedback_wa_tables.html',
                                                 {'obtained': obtained, 'expected': expected})

    veredict = VeredictCode.AC
    for table in expected_db:
        veredict, feedback = compare_select_results(expected_db[table], obtained_db[table], order=False)
        if veredict != VeredictCode.AC:
            feedback = f"<h4>La tabla <code>{table}</code> es incorrecta:</h4>{feedback}"
            break
    return veredict, feedback


def compare_function_results(expected, obtained):
    """
    Given an expected DB and an obtained DB, returns a veredict of the comparison and its HTML feedback
    :param expected: dict {call: result}
    :param obtained: dict {call: result}
    :return: (VeredictCode, str)
    """
    veredict = VeredictCode.AC
    feedback = ''
    for call in expected:
        if expected[call] != obtained[call]:
            veredict = VeredictCode.WA
            feedback = render_to_string('feedback_wa_function.html',
                                        {'call': call, 'expected': expected[call], 'obtained': obtained[call]})
            break
    return veredict, feedback