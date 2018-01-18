"""
Extra tags and templates used in the django 
templating system for the redistricting app.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010 Micah Altman, Michael McDonald
 
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
 
        http://www.apache.org/licenses/LICENSE-2.0
 
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
 
Author: 
    Andrew Jennings, David Zwarg 
"""

from django import template
from django.template.defaultfilters import floatformat
from django.utils.translation import ugettext as _

register = template.Library()


@register.filter
def spellnumber(value):
    """
    This filter converts a number into its spelled-out equivalent.
    Note: not all numbers are implemented. The return value for a
    number greater than twenty will be the non-spelled-out version.
    Parameters:
        value - A number value
    """
    try:
        return [
            _("zero"),
            _("one"),
            _("two"),
            _("three"),
            _("four"),
            _("five"),
            _("six"),
            _("seven"),
            _("eight"),
            _("nine"),
            _("ten"),
            _("eleven"),
            _("twelve"),
            _("thirteen"),
            _("fourteen"),
            _("fifteen"),
            _("sixteen"),
            _("seventeen"),
            _("eighteen"),
            _("nineteen"),
            _("twenty")
        ][value]
    except:
        return value


@register.filter
def dictsort_ignorecase(value, arg):
    """
    Takes a list of dicts, returns that list sorted by the property given in
    the argument. Sort is case insensitive.
    """

    def lower_if_string(object):
        try:
            return object.lower()
        except AttributeError:
            return object

    var_resolve = template.Variable(arg).resolve
    decorated = [(lower_if_string(var_resolve(item)), item) for item in value]
    decorated.sort()
    return [item[1] for item in decorated]


@register.filter
def count_true_values(value, key):
    """
    This filter accepts a list of dicts and returns the count of "True"
    values in the list. The "key" value is the key in the dict to check
    for True
    """
    try:
        return str(len(filter(lambda x: x[key], value)))
    except:
        return ''


@register.filter
def avg_report_column(districtscores, row):
    """
    This filter extracts all scores in a set of districtscores that are
    related to the row, by using 'avg_key', and returns an average of the score.
    Parameters:
        districtscores - A list of districtscores
        row - A single score row
    """
    if 'avg_key' not in row:
        return ''

    try:
        avg_key = row['avg_key']
        total = 0
        num_items = 0

        for districtscore in districtscores:
            if districtscore['district'].district_id == 0:
                continue

            for score in districtscore['scores']:
                for scorerow in score['score']:
                    if 'avg_key' in scorerow and avg_key == scorerow['avg_key']:
                        num_items += 1
                        total += float(scorerow['value'])
    except:
        return 'N/A'

    return format_report_value({
        'type':
        row['type'],
        'value':
        0 if not num_items else total / num_items
    })


@register.filter
def count_report_row_elements(row):
    """
    This filter returns the length of a list found in a score row.
    Parameters:
        row - A single score row
    """
    try:
        if (row['type'] == 'list'):
            return floatformat(len(row['value']), 0)
    except:
        return ''

    return ''


@register.filter
def format_report_value(row):
    """
    This filter formats a score based on it's type.
    Parameters:
        row - A single score row
    """
    try:
        if row['type'] == 'integer':
            return floatformat(row['value'], 0)

        if row['type'] == 'percent':
            return floatformat(row['value'] * 100, 2) + '%'

        if row['type'] == 'boolean':
            # Rather than using Upper on the string value, we'll be specific
            # for the sake of i18n
            return _('True') if row['value'] is True else _('False')

        if row['type'] == 'list':
            return '  '.join([str(x) for x in row['value']])
    except:
        return 'N/A'

    return row['value']


@register.filter
def format_report_class(row):
    """
    This filter returns a css class based on the score's type.
    Parameters:
        row - A single score row
    """
    try:
        if row['type'] in ['integer', 'float', 'percent']:
            return 'right'

        if row['type'] == 'list':
            return 'left'

        if row['type'] == 'boolean':
            return 'center ' + str(row['value']).lower()
    except:
        pass

    return 'center'
