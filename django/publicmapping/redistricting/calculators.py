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

        The base class generates an HTML span element, with the text
        content set to a string representation of the result. If the result
        is None, the string "n/a" is used.
        """
        if not self.result is None:
            return '<span>%s</span>' % self.result
        else:
            return '<span>n/a</span>'

    def json(self):
        """
        Return a basic JSON representation of the result.

        The base class generates an simple Javascript object that contains
        a single property, named "result".
        """
        return json.dumps( {'result':self.result} )

    def get_value(self, argument, district=None):
        """
        Get the value of an argument if it is a literal or a subject.

        This method is used anytime a calculator needs to get the value of
        a named argument. The type of the argument is determined from the 
        tuple in the argument dictionary, and either the literal value or
        the retrieved ComputedCharacteristic is returned. This only searches
        for the ComputedCharacteristic in the set attached to the district.

        If no district is provided, no subject argument value is ever 
        returned.
        """
        (argtype, argval) = self.arg_dict[argument]
        if argtype == 'literal':
            return argval
        elif argtype == 'subject' and not district is None:
            # This method is more fault tolerant than _set.get, since it 
            # won't throw an exception if the item doesn't exist.
            cc = district.computedcharacteristic_set.filter(subject__name=argval)
            if cc.count() == 0:
                return None
            
            return cc[0].number

        return None


class Schwartzberg(CalculatorBase):
    """
    Calculator for the Schwartzberg measure of compactness.
        
    The Schwartzberg measure of compactness measures the perimeter of 
    the district to the circumference of the circle whose area is 
    equal to the area of the district.

    This calculator will calculate either the compactness score of a
    single district, or it will average the compactness scores of all 
    districts in a plan.
    """
    def compute(self, **kwargs):
        """
        Calculate the Schwartzberg measure of compactness.

        Keywords:
            district - A district's whose compactness should be computed.
        """
        districts = []
        if 'district' in kwargs:
            districts = [kwargs['district']]
            if districts[0].geom is None:
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=True)

        else:
            return

        num = 0
        compactness = 0
        for district in districts:
            if district.geom is None:
                continue
        
            r = sqrt(district.geom.area / pi)
            perimeter = 2 * pi * r
            compactness += perimeter / district.geom.length
            num += 1

        self.result = compactness / num


    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"
        """
        return ("%0.2f%%" % (self.result * 100)) if self.result else "n/a"


class Sum(CalculatorBase):
    """
    Sum up all values.

    For districts, this calculator will sum up a series of arguments.

    For plans, this calculator will sum up a series of arguments across
    all districts. If a literal value is included in a plan calculation,
    that literal value is combined with the subject value for each 
    district.

    Each argument should be assigned the argument name "valueN", where N
    is a positive integer. The summation will add all arguments, starting
    at position 1, until an argument is not found.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate the sum of a series of values.
        """
        districts = []

        if 'district' in kwargs:
            districts = [kwargs['district']]
        elif 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=False)

        else:
            return

        self.result = 0

        for district in districts:
            argnum = 1
            while ('value%d'%argnum) in self.arg_dict:
                number = self.get_value('value%d'%argnum, district)
                if not number is None:
                    self.result += float(number)

                argnum += 1


class Percent(CalculatorBase):
    """
    Calculate a percentage for two values.

    A percentage calculator requires two arguments: "numerator", and 
    "denominator".

    When passed a district, the percentage calculator simply divides the
    numerator by the denominator.

    When passed a plan, the percentage calculator accumulates all the
    numerator values and denominator values for all districts in the plan.
    After the numerator and denominator values have been accumulated, 
    it computes the percentage of those totals.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate a percentage.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

            num = self.get_value('numerator',district)
            den = self.get_value('denominator',district)

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=False)
            num = 0
            den = 0
            for district in districts:
                tmpnum = self.get_value('numerator',district)
                tmpden = self.get_value('denominator',district)

                # If either the numerator or denominator don't exist,
                # we have to skip it.
                if tmpnum is None or tmpden is None:
                    continue

                den += float(tmpden)
                num += float(tmpnum)

        else:
            return

        if num is None or den is None:
            return

        self.result = float(num) / float(den)


class Threshold(CalculatorBase):
    """
    Determine a value, and indicate if it exceeds a threshold.

    This calculator accepts two arguments: "value", and "threshold". The
    result of this calculator is 1 or 0, to facilitate the combination of
    scores. One example may be where the number of districts that exceed a
    threshold are required.
    
    If the value computed is less than or equal to the threshold, the 
    return value will be zero (0).

    If the value computed is greater than the threshold, the return value
    will be one (1).
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate and determine if a value exceeds a threshold.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

        elif 'plans' in kwargs:
            pass

        else:
            return

        val = self.get_value('value',district)
        thr = self.get_value('threshold',district)

        if val is None or thr is None:
            return

        self.result = 1 if float(val) > float(thr) else 0


class Range(CalculatorBase):
    """
    Determine a value, and indicate if it falls within a range

    This calculator accepts three arguments: "value", "min", and "max". The
    result of this calculator is 1 or 0, to facilitate the combination of
    scores. One example may be where the number of districts that fall 
    within a range are required.
    
    If the value computed is greater than or equal to min and less than 
    or equal to max, the return value will be zero (1).

    If the value computed is less than min or greater than max, the return
    value will be one (1).
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Calculate and determine if a value lies within a range.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

        elif 'plan' in kwargs:
            pass

        else:
            return

        val = self.get_value('value',district)
        minval = self.get_value('min',district)
        maxval = self.get_value('max',district)

        if val is None or minval is None or maxval is None:
            return

        self.result = 1 if float(val) > float(minval) and float(val) < float(maxval) else 0


class Contiguity(CalculatorBase):
    """
    Calculate the contiguity of a district.

    A district is considered contiguous if it has only one polygon.

    This calculator will only operate on a district.
    """
    def compute(self, **kwargs):
        """
        Determine if a district is continuous.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

        elif 'plan' in kwargs:
            return

        else:
            return

        self.result = 1 if district.geom and len(district.geom) == 1 else 0


class Equivalence(CalculatorBase):
    """
    Generate a single score based on how closely a set of districts are
    to a target.

    This calculator examines every district in a plan, and generates a
    score which is the difference between the district with the maximum 
    value and the district with the minimum value.

    This calculator requires one argument: 'value', which is the name
    of a subject.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Generate an equivalence score.
        """
        if 'district' in kwargs or not 'plan' in kwargs:
            return

        plan = kwargs['plan']

        districts = plan.get_districts_at_version(plan.version,include_geom=False)
        if len(districts) == 0:
            return

        min_d = 1000000000 # 1B enough?
        max_d = 0
        for district in districts:
            tmpval = self.get_value('value',district)
            if not tmpval is None:
                min_d = min(float(tmpval), min_d)
                max_d = max(float(tmpval), max_d)

        self.result = max_d - min_d


class PartisanDifferential(CalculatorBase):
    """
    Compute the partisan differential.

    The partisan differential is the absolute value of the difference 
    between the Democratic Partisan Index and the Republican Partisan 
    Index. The Democratic Partisan Index is the number of democratic 
    votes divided by the combined number of democratic and republican 
    votes. The Republican Partisan Index is the number of republican 
    votes divided by the combined number of democratic and republican 
    votes.

    This calculator requires two arguments: 'democratic' and 'republican'

    When passed a district, this calculator will compute the partisan
    differential of one district.

    When passed a plan, this calculator will compute the average
    partisan differential of all districts in the plan.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Compute the partisan differential.
        """
        districts=[]
        if 'district' in kwargs:
            districts = [kwargs['district']]

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=False)

        else:
            return

        num = 0
        pd = 0
        for district in districts:
            dem = self.get_value('democratic',district)
            rep = self.get_value('republican',district)
            if dem is None or rep is None:
                continue

            dem = float(dem)
            rep = float(rep)
            dem_pi = dem / (rep + dem)
            rep_pi = rep / (rep + dem)

            pd += abs(rep_pi - dem_pi)
            num += 1.0

        self.result = pd / num

class RepresentationalFairness(CalculatorBase):
    """
    Compute the representational fairness.

    Representational fairness is defined here as the 

    This calculator only operates on Plans.

    This calculator requires two arguments: 'democratic', and 'republican'.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Compute the representational fairness.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        districts = plan.get_districts_at_version(plan.version, include_geom=False)
        numdistricts = 0
        likely = 0
        sumdem = 0
        sumrep = 0
        for district in districts:
            tmpdem = self.get_value('democratic',district)
            tmprep = self.get_value('republican',district)

            if tmpdem is None or tmprep is None:
                continue

            dem = float(tmpdem)
            rep = float(tmprep)

            pidx = dem / (dem + rep)
            if pidx > 0.5:
                likely += 1

            sumdem += dem
            sumrep += rep

            numdistricts += 1

        statepct = sumdem / (sumdem+sumrep)
        likelypct = float(likely) / float(numdistricts)

        self.result = abs( (likelypct/statepct) - 1 )
