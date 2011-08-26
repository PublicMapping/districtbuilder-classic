"""
Define the calculators used for calculator reports in the redistricting app.

The classes in redistricting.reportcalculators define the scoring
calculators used in the reports in the application. Each class relates to
one type of calculator that can be referenced within the config
file to define how to score a plan or district.

This file is part of The Public Mapping Project
http://sourceforge.net/projects/publicmapping/

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
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from math import sqrt, pi
from django.contrib.gis.geos import Point
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils import simplejson as json
from decimal import Decimal
from redistricting.calculators import *
import locale, sys, traceback

class Population(CalculatorBase):
    """
    Report on the population in each district.

    This calculator only operates on districts. It accepts one required
    argument: "value", and two optional arguments: "min" and "max". If
    the optional values are specified, the population of the district will
    be marked within range if it falls between them.
    """
    def compute(self, **kwargs):
        district = kwargs['district']

        pop_value = self.get_value('value', district)
        avg_key = "population_" + self.arg_dict['value'][1]

        self.result = {
            'raw': [
                { 'label': 'DistrictID', 'type': 'string', 'value': district.name },
                { 'label': 'Population', 'type': 'integer', 'value': pop_value, 'avg_key': avg_key }
            ]
        }

        # Add 'Within Target Range' column if min/max are configured
        minval = self.get_value('min',district)
        maxval = self.get_value('max',district)
        
        if pop_value is None or minval is None or maxval is None:
            return
        
        within_value = float(pop_value) > float(minval) and float(pop_value) < float(maxval)
        self.result['raw'].append({ 'label': 'Within Target Range', 'value': within_value, 'type': 'boolean' })

class Compactness(CalculatorBase):
    """
    Report on the compactness of a district.

    This calculator only operates on districts. It accepts one required
    argument: "comptype", which allows the specification of which type of
    compactness calculation will be performed. Currently available comptypes
    are: 'LengthWidth', 'Roeck', and 'Schwartzberg'
    """
    def compute(self, **kwargs):
        district = kwargs['district']
        comptype = self.arg_dict['comptype'][1]

        calc = None;
        if comptype == 'LengthWidth':
            calc = LengthWidthCompactness()
        elif comptype == 'Roeck':
            calc = Roeck()
        elif comptype == 'Schwartzberg':
            calc = Schwartzberg()
        else:
            return

        calc.compute(district=district)
        
        self.result = {
            'raw': [
                { 'label': 'DistrictID', 'type': 'string', 'value': district.name },
                { 'label': 'Compactness', 'type': 'percent', 'value': calc.result['value'], 'avg_key': comptype }
            ]
        }

class Majority(CalculatorBase):
    """
    Report on the proportion of a district's composition by subject.

    This calculator only operates on districts. It accepts two required
    arguments: "value", and "total". If the ratio of the value to the total
    exceeds 50%, it is marked as a majority.
    """
    def compute(self, **kwargs):
        district = kwargs['district']

        pop_value = self.get_value('value', district)
        tot_value = self.get_value('total', district)
        proportion = float(pop_value) / float(tot_value)
        pop_avg_key = "majminpop_" + self.arg_dict['value'][1]
        prop_avg_key = pop_avg_key + "_" + "proportion"

        self.result = {
            'raw': [
                { 'label': 'DistrictID', 'type': 'string', 'value': district.name },
                { 'label': 'Population', 'type': 'integer', 'value': pop_value, 'avg_key': pop_avg_key },
                { 'label': 'Proportion', 'type': 'percent', 'value': proportion, 'avg_key': prop_avg_key },
                { 'label': '>= 50%', 'type': 'boolean', 'value': proportion >= .5 }
            ]
        }

class Unassigned(CalculatorBase):
    """
    Report on the unassigned base geounits of a plan.

    This calculator only operates on plans. It finds all of the unassigned base
    geounits, lists them by their portable_id, and tallys them up.
    """
    def compute(self, **kwargs):
        plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version            
        threshold = self.get_value('threshold')
        if not threshold:
            threshold = 100

        geounits = plan.get_unassigned_geounits(threshold=threshold, version=version)
        self.result = { 'raw': [{ 'type': 'list', 'value': [t[1] for t in geounits] }] }
