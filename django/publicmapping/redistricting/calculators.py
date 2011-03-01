"""
Define the calculators used for scoring in the redistricting app.

The classes in redistricting.calculators define the scoring
calculators used in the application. Each class relates to
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
from django.utils import simplejson as json

class CalculatorBase:
    """
    A base class for all calculators that defines the result object,
    and defines a couple default rendering options for HTML, JSON, and 
    Boolean.
    """

    # This calculator's result
    result = None

    # This calculator's dictionary of arguments. This dictionary is keyed
    # by argument name, and the values are tuples of the type name and
    # the value.
    #
    # E.g.: arg_dict = { 'minimum':('literal','0.5',) }
    #
    arg_dict = {}

    def compute(self, **kwargs):
        """
        Compute the value for this calculator. The base class calculates
        nothing.
        """
        pass

    def html(self):
        """
        Return a basic HTML representation of the result.
        """
        if not self.result is None:
            return '<span>%s</span>' % self.result
        else:
            return '<span>n/a</span>'

    def json(self):
        """
        Return a basic JSON representation of the result.
        """
        return json.dumps( {'result':self.result} )


class Schwartzberg(CalculatorBase):
    """
    Calculator for the Schwartzberg measure of compactness.
        
    The Schwartzberg measure of compactness measures the perimeter of 
    the district to the circumference of the circle whose area is 
    equal to the area of the district.

    Parameters:
        district -- The District for which compactness is to be calculated.
    """
    def compute(self, **kwargs):
        """
        Calculates the Schwartzberg measure of compactness.
        """
        if not 'districts' in kwargs:
            return

        districts = kwargs['districts']
        if len(districts) == 0:
            return

        district = districts[0]
        if district.geom is None:
            return
        
        r = sqrt(district.geom.area / pi)
        perimeter = 2 * pi * r
        self.result = perimeter / district.geom.length

    def html(self):
        return ("%.2f%%" % (self.result * 100)) if self.result else "n/a"

#class Sum(CalculatorBase):
#    """
#    Sum up all values.
#    """
#    def compute(self, *args, **kwargs):
        
