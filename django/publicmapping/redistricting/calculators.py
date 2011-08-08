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
from django.contrib.gis.geos import Point
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils import simplejson as json
from decimal import Decimal
import locale, sys, traceback

# This helps in formatting - by default, apache+wsgi uses the "C" locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')


class CalculatorBase:
    """
    The base class for all calculators. CalculatorBase defines the result 
    object and a couple default rendering options for HTML and JSON.
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

    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Compute the value for this calculator. The base class calculates
        nothing.
        """
        pass

    def sortkey(self):
        """
        Generate a key used to sort this calculator relative to all other
        calculators. The default sorting method sorts by the value of 
        the result.

        @return: The value of the result.
        """
        if not self.result is None and 'value' in self.result:
            return self.result['value']

        return self.result

    def html(self):
        """
        Generate a basic HTML representation of the result.

        The base calculator generates an HTML span element, with the text
        content set to a string representation of the result. If the result
        is None, the string "n/a" is used.

        @return: An HTML SPAN element, formatted similar to: "<span>n/a</span>".
        """
        if not self.result is None and 'value' in self.result:
            return '<span>%s</span>' % self.result['value']
        else:
            return '<span>n/a</span>'

    def json(self):
        """
        Generate a basic JSON representation of the result.

        The base calculator generates an simple Javascript object that 
        contains a single property, named "result".

        @return: A JSON string with a single object that contains the
            property 'result'.
        """
        if not self.result is None and 'value' in self.result:
            output = { 'result': self.result['value'] }
        else:
            output = { 'result': None }

        return json.dumps( output, use_decimal=True )

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

        @param argument: The name of the argument passed to the calculator.
        @param district: An optional district, used to fetch related 
            ComputedCharacteristics.

        @return: The value of the subject or literal argument.
        """
        try:
            (argtype, argval) = self.arg_dict[argument]
        except:
            return None

        value = None
        if argtype == 'literal':
            value = argval
            try:
                # If our literal is a number, make it a decimal to match models
                value = Decimal(value)
            except:
                # No problem, it may be a string
                pass
        elif argtype == 'subject' and not district is None:
            # This method is more fault tolerant than _set.get, since it 
            # won't throw an exception if the item doesn't exist.
            cc = district.computedcharacteristic_set.filter(subject__name=argval)
            if cc.count() > 0:
                value = cc[0].number
        return value


class Schwartzberg(CalculatorBase):
    """
    Calculator for the Schwartzberg measure of compactness.
        
    The Schwartzberg measure of compactness measures the perimeter of 
    the district to the circumference of the circle whose area is 
    equal to the area of the district. The algorithm here computes the
    inverse Schwartberg compactness measure, suitable for display as a 
    percentage, with a higher percentage indicating a more compact 
    district.

    This calculator will calculate either the compactness score of a
    single district, or it will average the compactness scores of all 
    districts in a plan.
    """
    def compute(self, **kwargs):
        """
        Calculate the Schwartzberg measure of compactness.

        @keyword district: A L{District} whose compactness should be 
            computed.
        @keyword plan: A L{Plan} whose district compactnesses should be 
            averaged.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []
        if 'district' in kwargs:
            districts = [kwargs['district']]
            if districts[0].geom.empty:
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=True)

        else:
            return

        num = 0
        compactness = 0
        for district in districts:
            if district.district_id == 0:
                continue

            if district.geom.empty:
                continue

            if district.geom.length == 0:
                continue
        
            r = sqrt(district.geom.area / pi)
            circumference = 2 * pi * r
            compactness += circumference / district.geom.length
            num += 1

        self.result = { 'value': (compactness / num) if num > 0 else 0 }


    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return ("%0.2f%%" % (self.result['value'] * 100))
        else:
            return "n/a"


class Roeck(CalculatorBase):
    """
    Calculator for the Roeck measure of compactness.

    The Roeck measure of compactness measures the area of the smallest
    enclosing circle around a district compared to the area of the district.

    This calculator will calculate either the compactness score of a single
    district, or it will average the compactness scores of all districts
    in a plan.
    """
    def compute(self, **kwargs):
        """
        Calculate the Roeck measure of compactness.

        @keyword district: A L{District} whose compactness should be 
            computed.
        @keyword plan: A L{Plan} whose district compactnesses should be 
            averaged.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []
        if 'district' in kwargs:
            districts = [kwargs['district']]
            if districts[0].geom.empty:
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=True)

        else:
            return

        num = 0
        compactness = 0
        for district in districts:
            if district.district_id == 0:
                continue

            if district.geom.empty:
                continue

            centroid = district.geom.centroid
            maxd = 0
            for linestring in district.geom.convex_hull:
                for coord in linestring:
                    maxd = max(maxd, centroid.distance(Point(coord)))

            cir_area = pi * maxd * maxd

            compactness += district.geom.area / cir_area
            num += 1

        try:
            self.result = { 'value': compactness / num }
        except:
            self.result = { 'value': 'N/A' }
        

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return ("%0.2f%%" % (self.result['value'] * 100))
        else:
            return "n/a"


class PolsbyPopper(CalculatorBase):
    """
    Calculator for the Polsby-Popper measure of compactness.

    The Polsby-Popper measure of campactness measures the area of a circle
    with the same perimeter as a district compared to area of the district.

    This calculator will calculate either the compactness score of a single
    district, or it will average the compactness scores of all districts
    in a plan.
    """
    def compute(self, **kwargs):
        """
        Calculate the Polsby-Popper measure of compactness.

        @keyword district: A L{District} whose compactness should be 
            computed.
        @keyword plan: A L{Plan} whose district compactnesses should be 
            averaged.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []
        if 'district' in kwargs:
            districts = [kwargs['district']]
            if districts[0].geom.empty:
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=True)

        else:
            return

        num = 0
        compactness = 0
        for district in districts:
            if district.district_id == 0:
                continue

            if district.geom.empty:
                continue

            perimeter = 0
            for poly in district.geom:
                for linestring in poly:
                    perimeter += linestring.length

            compactness += 4 * pi * district.geom.area / perimeter / perimeter
            num += 1

        self.result = { 'value': compactness / num }

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return ("%0.2f%%" % (self.result['value'] * 100))
        else:
            return "n/a"


class LengthWidthCompactness(CalculatorBase):
    """
    Calculator for the Length/Width measure of compactness.

    The Length/Width measure of campactness measures the length of the 
    district's bounding box, and divides it by the width of the district's
    bounding box.

    This calculator will calculate either the compactness score of a single
    district, or it will average the compactness scores of all districts
    in a plan.
    """
    def compute(self, **kwargs):
        """
        Calculate the Length/Width measure of compactness.

        @keyword district: A L{District} whose compactness should be 
            computed.
        @keyword plan: A L{Plan} whose district compactnesses should be 
            averaged.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []
        if 'district' in kwargs:
            districts = [kwargs['district']]
            if districts[0].geom.empty:
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=True)

        else:
            return

        num = 0
        compactness = 0
        for district in districts:
            if district.district_id == 0:
                continue

            if district.geom.empty:
                continue

            bbox = district.geom.extent
            compactness += (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])
            num += 1

        self.result = { 'value': compactness / num }

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return ("%0.2f%%" % (self.result['value'] * 100))
        else:
            return "n/a"


class SumValues(CalculatorBase):
    """
    Sum up all values.

    For districts, this calculator will sum up a series of arguments.

    For plans, this calculator will sum up a series of arguments across
    all districts. If a literal value is included in a plan calculation,
    that literal value is combined with the subject value for each 
    district.

    For lists of numbers, this calculator will return the sum of the list.

    Each argument should be assigned the argument name "valueN", where N
    is a positive integer. The summation will add all arguments, starting
    at position 1, until an argument is not found.

    This calculator takes an optional "target" argument.  If passed this
    argument, the calculator will return a string suitable for display in
    a plan summary
    """

    def compute(self, **kwargs):
        """
        Calculate the sum of a series of values.

        @keyword district: A L{District} whose values should be summed.
        @keyword plan: A L{Plan} whose district values should be summed.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        @keyword list: A list of values to sum, when summing a set of 
            ScoreArguments.
        """
        districts = []

        if 'district' in kwargs:
            districts = [kwargs['district']]
        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=False)
        elif 'list' in kwargs:
            lst = kwargs['list']
            self.result = reduce(lambda x,y: x + y, lst)
            return
        else:
            return
        
        sumvals = 0

        for district in districts:
            argnum = 1
            while ('value%d'%argnum) in self.arg_dict:
                number = self.get_value('value%d'%argnum, district)
                if not number is None:
                    sumvals += number

                argnum += 1

        if self.get_value('target') is not None:
            target = self.get_value('target')
            self.result = { 'value': "%d (of %s)" % (sumvals, target) }
        else:
            self.result = { 'value': sumvals }

    def html(self):
        """
        Generate an HTML representation of the summation score. This
        is represented as a decimal formatted with commas or "n/a".

        @return: The result wrapped in an HTML SPAN element: "<span>1</span>".
        """
        if not self.result is None and 'value' in self.result:
            if isinstance(self.result['value'], Decimal):
                result = locale.format("%d", self.result['value'], grouping=True)
                return '<span>%s</span>' % result
            else:
                return '<span>%s</span>' % self.result['value']

        return '<span>n/a</span>'


class Percent(CalculatorBase):
    """
    Calculate a percentage for two values.

    A percentage calculator requires two arguments: "numerator" and
    "denominator".

    When passed a district, the percentage calculator simply divides the
    numerator by the denominator.

    When passed a plan, the percentage calculator accumulates all the
    numerator values and denominator values for all districts in the plan.
    After the numerator and denominator values have been accumulated, 
    it computes the percentage of those totals.
    """
    def compute(self, **kwargs):
        """
        Calculate a percentage.

        @keyword district: A L{District} whose percentage should be 
            calculated.
        @keyword plan: A L{Plan} whose set of districts should be 
            calculated.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        district = None

        if 'district' in kwargs:
            district = kwargs['district']

            num = self.get_value('numerator',district)
            den = self.get_value('denominator',district)

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=False)
            num = 0
            den = 0
            for district in districts:
                if district.district_id == 0:
                    continue

                tmpnum = self.get_value('numerator',district)
                tmpden = self.get_value('denominator',district)

                # If either the numerator or denominator don't exist,
                # we have to skip it.
                if tmpnum is None or tmpden is None:
                    continue

                den += tmpden
                num += tmpnum

        else:
            return

        if num is None or den is None or den == 0:
            return
    
        self.result = { 'value': num / den }

    def html(self):
        """
        Generate an HTML representation of the percentage score. This
        is represented as a decimal formatted with commas or "n/a"

        @return: The result wrapped in an HTML SPAN element, formatted similar to: "<span>1.00%</span>" or "<span>n/a</span>".
        """
        if not self.result is None and 'value' in self.result:
            if (type(self.result['value']) == Decimal):
                return '<span>{0:.2%}</span>'.format(self.result['value'])
            
        return '<span>n/a</span>'


class Threshold(CalculatorBase):
    """
    Determine a value, and indicate if it exceeds a threshold.

    This calculator accepts two arguments: "value", and "threshold". The
    result of this calculator is 1 or 0, to facilitate the combination of
    scores. One example may be where the number of districts that exceed a
    threshold are required.
    
    If the value computed is less than or equal to the threshold, the 
    result value will be zero (0).

    If the value computed is greater than the threshold, the result value
    will be one (1).

    If this calculator is called with a plan, it will tally up the number
    of districts that exceed the designated threshold.
    """
    def compute(self, **kwargs):
        """
        Calculate and determine if a value exceeds a threshold.

        @keyword district: A L{District} whose threshold should be 
            calculated.
        @keyword plan: A L{Plan} whose set of districts should be 
            thresholded.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []

        if 'district' in kwargs:
            districts = [kwargs['district']]

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=False)

        else:
            return

        count = 0
        for district in districts:
            val = self.get_value('value',district)
            thr = self.get_value('threshold',district)

            if val is None or thr is None:
                continue

            if float(val) > float(thr):
                count += 1

        self.result = { 'value': count }


class Range(CalculatorBase):
    """
    Determine a value, and indicate if it falls within a range

    This calculator accepts three arguments: "value", "min", and "max". The
    result of this calculator is 1 or 0, to facilitate the combination of
    scores. One example may be where the number of districts that fall 
    within a range are required.

    This calculator accepts an optional argument: 'apply_num_members'.
    If this is set to '1' (True), the calculator will consider the number
    of members assigned to each district when performing calculations.
    This should only be used with population subjects.
    
    If the value computed is greater than or equal to min and less than 
    or equal to max, the result value will be zero (1).

    If the value computed is less than min or greater than max, the result
    value will be one (1).

    If the calculator is passed a plan, then the result value will be the
    number of districts that are within the range. For a test like equi-
    population, this will count the number of districts within the target
    range.
    """
    def compute(self, **kwargs):
        """
        Calculate and determine if a value lies within a range.

        @keyword district: A L{District} whose argument should be 
            evaluated.
        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = None

        if 'district' in kwargs:
            districts = [kwargs['district']]

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=False)

        else:
            return

        count = 0

        if 'apply_num_members' in self.arg_dict:
            apply_num_members = int(self.arg_dict['apply_num_members'][1]) == 1
        else:
            apply_num_members = False

        for district in districts:            
            if district.district_id == 0:
                continue

            val = self.get_value('value',district)
                
            if apply_num_members and district.num_members > 1:
                val = float(val) / district.num_members
            
            minval = self.get_value('min',district)
            maxval = self.get_value('max',district)

            if val is None or minval is None or maxval is None:
                continue

            if float(val) > float(minval) and float(val) < float(maxval):
                count += 1

        self.result = { 'value': count }


class Contiguity(CalculatorBase):
    """
    Calculate the contiguity of a district.

    This calculator accepts two optional arguments: 'allow_single_point',
    and 'target'. If 'allow_single_point' is set to '1' (True), the 
    calculator will consider a district containing muliple polygons 
    contiguous if the polygons are connected to each other by a minimum of 
    one point. By default, this is set to '0' (False), and a district is 
    only considered to be congiguous if it is comprised of a single 
    polygon.

    If 'target' is set, the calculator will format the result to include
    the target value in parenthesis after the calculated value.

    'ContiguityOverride' objects that are applicable to the district will 
    be applied to allow for special cases where non-physical contiguity 
    isn't possible.
    
    If the district is contiguous, the result value will be zero (0).

    If the district is discontiguous, the result value will be one (1).

    If this calculator is called with a plan, it will tally up the number
    of districts that are contiguous.

    """
    def compute(self, **kwargs):
        """
        Determine if a district is contiguous.

        @keyword district: A L{District} whose contiguity should be 
            evaluated.
        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for contiguity.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []

        if 'district' in kwargs:
            districts = [kwargs['district']]

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=True)

        else:
            return

        if 'allow_single_point' in self.arg_dict:
            allow_single = int(self.arg_dict['allow_single_point'][1]) == 1
        else:
            allow_single = False

        count = 0
        for district in districts:
            if len(district.geom) == 1 and district.district_id != 0:
                count += 1
            else:
                if district.district_id == 0:
                    # for plan summations of contiguity, ignore the unassigned in the tally
                    if 'plan' in kwargs:
                        continue
                    elif len(district.geom) == 1:
                        count += 1
                        continue

                # if the district has no geometry, i.e. an empty unassigned district,
                # treat it as contiguous
                if len(district.geom) == 0:
                    count += 1
                    continue
                    
                # obtain the contiguity overrides that need to be applied
                overrides = district.get_contiguity_overrides()

                if allow_single or len(overrides) > 0:
                    # create a running union of of polygons that are linked, seeded with the first.
                    # loop through remaining polygons and add any that either touch the union,
                    # or do so virtually with a contiguity override. repeat until either:
                    #   - the remaining list is empty: contiguous
                    #   - no matches were found in a pass: discontiguous
                    union = district.geom[0]
                    remaining = district.geom[1:]
                    contiguous = True
    
                    while (len(remaining) > 0):
                        if len(district.geom) == 0:
                            continue

                        match_in_pass = False
                        for geom in remaining:
                            linked = False
                            if allow_single and geom.touches(union):
                                linked = True
                            else:
                                for override in overrides:
                                    o = override.override_geounit.geom
                                    c = override.connect_to_geounit.geom
                                    if (geom.contains(o) and union.contains(c)) or (geom.contains(c) and union.contains(o)):
                                        linked = True
                                        overrides.remove(override)
                                        break

                            if linked:
                                remaining.remove(geom)
                                union = geom.union(union)
                                match_in_pass = True
                                    
                        if not match_in_pass:
                            contiguous = False
                            break
    
                    if contiguous:
                        count += 1

        self.result = { 'value': count }
        try:
            target = self.get_value('target')
            if target != None:
                self.result = { 'value':'%d (of %s)' % (count, target) }
        except:
            pass

    def html(self):
        """
        Generate an HTML representation of the contiguity score. This
        is represented as an image element or the string result wrapped
        in a SPAN element if the result is non-numeric.

        @return: An HTML IMG element in the form of: '<img class="(yes|no)-contiguous" src="/static-media/images/icon-(check|warning).png">'
        """
        if not self.result is None and 'value' in self.result:
            if type(self.result['value']) == int:
                if self.result['value'] == 1:
                    return '<img class="yes-contiguous" src="/static-media/images/icon-check.png">'
                else:
                    return '<img class="no-contiguous" src="/static-media/images/icon-warning.png">'
            else:
                return '<span>%s</span>' % self.result['value']

        return '<span>%s</span>' % self.result


class AllContiguous(CalculatorBase):
    """
    Determine if all the districts in a plan are contiguous.

    This calculator uses the Contiguity calculator internally to tally up
    the number of districts that are contiguous, and compares the number
    of contiguous districts to the total number of districts in the plan.

    This calculator will only operate on a plan.
    """
    def compute(self, **kwargs):
        """
        Compute the contiguity of all the districts in the plan.

        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for contiguity.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        if not 'plan' in kwargs:
            return

	plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version, include_geom=False)

        calc = Contiguity()
        calc.compute(**kwargs)

        self.result = { 'value': (len(districts) - 1) == calc.result }


class NonContiguous(CalculatorBase):
    """
    Calculate the number of districts in a plan that are non-contiguous.

    This calculator accepts a 'target' argument. If set, the result of
    this calculator will be an HTML fragment with the target printed
    next to the calculated value.

    This calculator will only operate on a plan.
    """
    def compute(self, **kwargs):
        """
        Compute the number of districts in a plan that are non-contiguous.

        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for contiguity.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version, include_geom=False)

        calc = Contiguity()
        calc.compute(**kwargs)

        count = len(districts) - calc.result

        try:
            target = self.get_value('target')
            if target != None:
                self.result = { 'value': '%d (of %s)' % (count, target) }
        except:
            self.result = { 'value': count }


class Interval(CalculatorBase):
    """
    Used to determine whether a value falls in an interval determined by 
    a central target value and bounds determined to be a percentage of
    that target value.  With bound values of .10 and .20 and a target of 10,
    the intervals would be:
         [-infinity, 8), [8, 9), [9, 11), [11, 12), [12, infinity) 
    
    Given a district, this calculator will return the 0-based index of the
    interval in which the district's value lies - Using the above example, 
    a district with a value of 8.5 would have a result of 1.

    Given a plan, this calculator will return the number of districts that 
    fall in the interval including the target
    """
    def compute(self, **kwargs):
        """
        Determine the interval to which a district's value belongs.

        @keyword district: A L{District} whose interval should be computed.
        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for their intervals.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []
        bounds = []
        target = Decimal(str(self.get_value('target')))

        if 'apply_num_members' in self.arg_dict:
            apply_num_members = int(self.arg_dict['apply_num_members'][1]) == 1
        else:
            apply_num_members = False

        if 'district' in kwargs:
            districts = [kwargs['district']]

            # Set up our bounds
            argnum = 1
            while ('bound%d' % argnum) in self.arg_dict:
                bound = Decimal(str(self.get_value('bound%d' % argnum)))
                bounds.append(target + (target * bound))
                bounds.append(target - (target * bound))
                
                argnum += 1
            bounds.sort()
        
            # Check which interval our subject's value is in
            for district in districts:
                value = self.get_value('subject', district)
                if value == None:
                    return
                if apply_num_members and district.num_members > 1:
                    value = value / district.num_members
                
                for idx, bound in enumerate(bounds):
                    if value < bound:
                        self.result = { 
                            'index': idx, 
                            'value': value, 
                            'subject': self.arg_dict['subject'][1]
                        }
                        return
                self.result = {
                    'index': len(bounds), 
                    'value': value, 
                    'subject': self.arg_dict['subject'][1]
                }
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=True)

            # Set up our bounds
            argnum = 1
            min_bound = None
            while ('bound%d' % argnum) in self.arg_dict:
                bound = Decimal(str(self.get_value('bound%d' % argnum)))
                if (not min_bound) or (bound < min_bound):
                    min_bound = bound
                argnum += 1

            max_bound = target + (target * min_bound)
            min_bound = target - (target * min_bound)

            count = 0
            for district in districts:
                value = self.get_value('subject', district)

                if apply_num_members and district.num_members > 1:
                    value = float(value) / district.num_members
                
                if value != None and value >= min_bound and value < max_bound:
                    count += 1

            self.result = { 'value': count }
        else:
            return

    def html(self):
        """
        Returns an HTML representation of the Interval, using a css class 
        called interval_X, with X being the interval index.

        An empty value will have a class of no_interval.

        The span will also have a class named after the subject to make
        multiple intervals available in a panel.

        @return: An HTML SPAN element, in the format: '<span class="interval_X X">1,000</span>'
        """
        # Get the name of the subject
        if not self.result is None and 'value' in self.result:
            if 'index' in self.result and 'subject' in self.result:
                interval = self.result['index']
                interval_class = "interval_%d" % interval if interval >= 0 else 'no_interval'
                span_value = locale.format("%d", self.result['value'], grouping=True)
                return '<span class="%s %s">%s</span>' % (interval_class, self.result['subject'], span_value)

        return '<span>n/a</span>' 


class Equivalence(CalculatorBase):
    """
    Generate a single score based on how closely a set of districts are
    to a target.

    This calculator examines every district in a plan, and generates a
    score which is the difference between the district with the maximum 
    value and the district with the minimum value.

    This calculator requires one argument: 'value', which is the name
    of a subject.
    
    This calculator accepts an optional argument: 'apply_num_members'.
    If this is set to '1' (True), the calculator will consider the number
    of members assigned to each district when performing calculations.
    This should only be used with population subjects.
    """
    def compute(self, **kwargs):
        """
        Generate an equivalence score.

        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for their equivalence.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        if 'district' in kwargs or not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version,include_geom=False)
        if len(districts) == 0:
            return

        if 'apply_num_members' in self.arg_dict:
            apply_num_members = int(self.arg_dict['apply_num_members'][1]) == 1
        else:
            apply_num_members = False

        min_d = 1000000000 # 1B enough?
        max_d = 0
        for district in districts:
            if district.district_id == 0:
                continue

            tmpval = self.get_value('value',district)
            if apply_num_members and district.num_members > 1:
                tmpval = float(tmpval) / district.num_members
            
            if not tmpval is None:
                min_d = min(float(tmpval), min_d)
                max_d = max(float(tmpval), max_d)

        self.result = { 'value': max_d - min_d }

    def html(self):
        """
        Generate an HTML representation of the equivalence score. This
        is represented as an integer formatted with commas or "n/a"

        @return: A string in the format of "1,000" or "n/a" if no result.
        """
        if not self.result is None and 'value' in self.result:
            return intcomma(int(self.result['value']))
        
        return 'n/a'


class RepresentationalFairness(CalculatorBase):
    """
    The representational fairness measure, or partisan differential,
    is absolute value of the number of districts where the partisan
    index for a one party is above 50% minus the number of districts
    where the partisan index for the other party is above 50%
    
    The Democratic Partisan Index is the number of democratic 
    votes divided by the combined number of democratic and republican 
    votes. The Republican Partisan Index is the number of republican 
    votes divided by the combined number of democratic and republican 
    votes.

    This calculator requires two arguments: 'democratic' and 'republican'

    When passed a plan, this calculator will compute the
    representational fairness for all districts in the plan.
    The result is a tuple with - the first item is the differential
    and the second item is the party toward which the plan's 
    districts are biased
    """
    def compute(self, **kwargs):
        """
        Compute the representational fairness.

        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for representational fairness.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        if 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=False)

        else:
            return

        dems = 0
        reps = 0
        for district in districts:
            dem = self.get_value('democratic',district)
            rep = self.get_value('republican',district)
            if dem is None or rep is None:
                continue

            dem = float(dem)
            rep = float(rep)

            if dem == 0.0 and rep == 0.0:
                continue

            dem_pi = dem / (rep + dem)
            if dem_pi > .5:
                dems += 1
            else:
                rep_pi = rep / (rep + dem)
                if rep_pi > .5:
                    reps += 1

        self.result = { 'value': dems - reps }

    def html(self):
        """
        Display the results in HTML format. Since the results for this
        calculator are in tuple format for sorting purposes, it's important
        to display a human readable score that explains which party the 
        plan is biased toward.

        @return: An HTML SPAN element similar to the form: "<span>Democrat 5</span>" or "<span>Balanced</span>".
        """
        if not self.result is None and 'value' in self.result:
            sort = abs(self.result['value'])
            party = 'Democrat' if self.result['value'] > 0 else 'Republican'
            if sort == 0:
                return '<span>Balanced</span>'
            else:
                return '<span>%s&nbsp;%d</span>' % (party, sort)
        
        return '<span>n/a</span>'

    def json(self):
        """
        Generate a basic JSON representation of the result.

        @return: A JSON object with 1 property: result.
        """
        if not self.result is None and 'value' in self.result:
            sort = abs(self.result['value'])
            party = 'Democrat' if self.result['value'] > 0 else 'Republican'
            output = {'result': '%s %d' % (party, sort)}
        else:
            output = {'result': None}

        return json.dumps(output)

    def sortkey(self):
        """
        How should this calculator be compared to others like it? 
        Sort by the absolute value of the result (farther from zero
        is a worse score).

        If the calculator experiences any error, the sortkey value is
        fixed at '99', which will sort all errors to the end of any
        sorted list.

        @return: The absolute value of the result.
        """
        if not self.result is None and 'value' in self.result:
            return abs(self.result['value'])

        return 99


class Competitiveness(CalculatorBase):
    """
    Compute the plan's Competitiveness.

    Competitiveness is defined here as the number of districts that 
    have a partisan index (democratic or republican) that falls within
    a desired range of .5 (by default).

    This calculator only operates on Plans.

    This calculator requires three arguments: 'democratic', 'republican',
        and 'range'
    """
    def compute(self, **kwargs):
        """
        Compute the competitiveness.

        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for competitiveness.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version, include_geom=False)
        try:
            difference = float(self.get_value('range'))
            low = .5 - difference
            high = .5 + difference
        except:
            low = .45
            high = .55

        
        fair = 0
        for district in districts:
            if district.district_id == 0:
                continue

            tmpdem = self.get_value('democratic',district)
            tmprep = self.get_value('republican',district)

            if tmpdem is None or tmprep is None:
                continue

            dem = float(tmpdem)
            rep = float(tmprep)

            if dem == 0.0 and rep == 0.0:
                continue

            pidx = dem / (dem + rep)
            if pidx > low and pidx < high:
                fair += 1

        self.result = { 'value': fair }


class CountDistricts(CalculatorBase):
    """
    Verify that the number of districts in a plan matches a target.

    The number of districts counted does not include the special district
    named 'Unassigned'.

    This calculator works on plans only.

    This calculator requires an argument 'target' set to the number of
    districts desired in a plan.  If the number of districts matches
    the target value, a boolean True is the result.
    """
    def compute(self, **kwargs):
        """
        Compute the number of districts in a plan.

        @keyword plan: A L{Plan} whose set of districts should be verified 
            against the target.
        @keyword version: Optional. The version of the plan, defaults to
            the most recent version.
        @keyword target: The target number of districts in the plan.
        """
        if not 'plan' in kwargs or not 'target' in self.arg_dict:
            return

        plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version, include_geom=False)
        # ALL PLANS include 1 district named "Unassigned", which cannot be
        # removed. Therefore the actual target to be validated is one less
        # than the number of districts.
        target = int(self.get_value('target'))

        self.result = { 'value': (len(districts)-1) == target }


class AllBlocksAssigned(CalculatorBase):
    """
    Determine if all the blocks in the state are assigned to a district.
    
    This calculator works on plans only.

    This calculator has an optional argument of 'threshold', which is used
    for buffer in/out optimization.
    """
    def compute(self, **kwargs):
        """
        Determine if all the blocks in the plan are assigned to a district.

        @keyword plan: A L{Plan} whose blocks are evaluated for assignment.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        @keyword threshold: Optional. The amount of simplification used 
            during buffering optimization.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version

        threshold = self.get_value('threshold')
        if not threshold:
            threshold = 100

        geounits = plan.get_unassigned_geounits(threshold=threshold, version=version)
        self.result = { 'value': len(geounits) == 0 }


class Equipopulation(CalculatorBase):
    """
    Determine if all the districts in a plan fall within a target range of
    population. This merely wraps a Range calculator, but looks for the
    number of districts outside the range.

    This calculator takes either a "target" or a "validation" parameter.  
    If given a target, it will return a string that's showable in a plan 
    summary.  If given a validation number, it will return a boolean result
    representing whether the given plan has reached that number of 
    majority-minority districts as configured.

    This calculator only operates on Plans.
    """
    def compute(self, **kwargs):
        """
        Determine if all the districts in a plan fall within a target
        range.

        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for equipopulation.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        @keyword target: Optional. The target number of districts to report
            in the HTML output.
        @keyword validation: Optional. Change the output of the calculator 
            to a boolean measure for plan validity.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']

        inrange = Range()
        inrange.arg_dict = self.arg_dict
        inrange.compute(**kwargs)

        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version, include_geom=False)

        try:
            target = self.get_value('target')
            validation = self.get_value('validation')
            if validation != None:
                # ALL PLANS include 1 district named "Unassigned", which
                # should never be at the target.
        
                self.result = { 'value': inrange.result['value'] == (len(districts) - 1) }
            elif target != None:
                self.result = { 'value': '%d (of %s)' % (inrange.result['value'], target) }
            else:
                self.result = inrange.result
        except:
            self.result = inrange.result


class MajorityMinority(CalculatorBase):
    """
    Determine if at least one district in a plan has a majority of minority
    population.

    This calculator accepts 'population', 'count', 'threshold' arguments, 
    and any number of 'minorityN' arguments, where N is a number starting 
    at 1 and incrementing by 1. If there are gaps in the sequence, only the
    first continuous set of 'minorityN' parameters will be used.

    The 'population' argument is for the general population to be compared
    to the 'minorityN' populations. These should probably by voting age
    populations. The 'count' argument defines AT LEAST how many districts
    must be majority/minority in order for a plan to pass. The 'threshold'
    argument defines the threshold at which a majority is determined.

    This calculator takes either a 'target' or a 'validation' parameter.  
    If given a target, it will return a string that's showable in a plan 
    summary.  If given a validation number, it will return a boolean result
    representing whether the given plan has reached that number of 
    majority-minority districts as configured.

    This calculator works on plans only.
    """
    def compute(self, **kwargs):
        """
        Determine if the requisite number of districts in a plan have a 
        majority of minority population. 

        @keyword plan: A L{Plan} whose set of districts should be 
            evaluated for majority minority compliance.
        @keyword version: Optional. The version of the plan, defaults to
            the most recent version.
        @keyword population: The primary population subject.
        @keyword minorityN: The minorty population subjects. Numbering 
            starts at 1, and must be continuous.
        @keyword threshold: Optional. The ratio of all minorityN 
            populations to the population subject when 'majority' is 
            achieved. Defaults to 0.5.
        @keyword target: Optional. The number of districts required to be 
            valid.
        @keyword validation: Optional. Change the output of the calculator
            to a boolean measure for plan validity.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version, include_geom=False)

        districtcount = 0
        for district in districts:
            pop = self.get_value('population', district)

            if pop is None:
                continue

            den = float(pop)
            argnum = 1
            exceeds = False
            while ('minority%d'%argnum) in self.arg_dict:
                minor = self.get_value('minority%d'%argnum, district)
                argnum += 1

                if minor is None:
                    continue
                    
                num = float(minor)

                try:
                    threshold = float(self.get_value('threshold', district))
                except:
                    threshold = 0.5

                if den != 0 and num / den > threshold:
                    exceeds = True
                    break

            if exceeds:
                districtcount += 1

        self.result = { 'value': districtcount }

        try:
            target = self.get_value('target')
            validation = self.get_value('validation')
            if validation != None:
                self.result = { 'value': districtcount >= Decimal(validation) }
            elif target != None:
                self.result = { 'value': "%d (of %s)" % (districtcount, target) }
        except:
            pass


class MultiMember(CalculatorBase):
    """
    Verify that multi-member plans satisfy all parameters.

    This calculator only operates on Plans.

    All multi-member parameters are pulled from the plan's legislative
    body.
    """
    def compute(self, **kwargs):
        """
        Verify that multi-member plans satisfy all parameters.

        @keyword plan: A L{Plan} whose districts should be evaluated for
            multi-member compliance.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        self.result = { 'value': False }

        if not 'plan' in kwargs:
            return

	plan = kwargs['plan']
        version = kwargs['version'] if 'version' in kwargs else plan.version
        districts = plan.get_districts_at_version(version, include_geom=False)
        legbod = plan.legislative_body

        if legbod.multi_members_allowed:
            min_dist_mems = legbod.min_multi_district_members
            max_dist_mems = legbod.max_multi_district_members
            min_multi_dists = legbod.min_multi_districts
            max_multi_dists = legbod.max_multi_districts
            min_plan_mems = legbod.min_plan_members
            max_plan_mems = legbod.max_plan_members
            
            total_members = 0
            total_multi_dists = 0

            for d in districts:
                if d.district_id == 0:
                    continue

                total_members += d.num_members
                if (d.num_members > 1):
                    total_multi_dists += 1

                    # Check number of members per multi-member district
                    if (d.num_members < min_dist_mems) or (d.num_members > max_dist_mems):
                        return

            # Check number of multi-member districts
            if (total_multi_dists < min_multi_dists) or (total_multi_dists > max_multi_dists):
                return

            # Check number of districts per plan
            if (total_members < min_plan_mems) or (total_members > max_plan_mems):
                return
        
        self.result = { 'value': True }


class Average(CalculatorBase):
    """
    Calculate the average of a series of values.

    This calculator will add up all arguments passed into it, and return
    the mathematical mean of their values.

    For a district, this calculator will average a set of scores for 
    each district.

    For a plan, this calculator will average a set of district scores 
    across the entire plan.

    Each argument should be assigned the argument name "valueN", where N
    is a positive integer. The summation will add all arguments, starting
    at position 1, until an argument is not found.
    """
    def compute(self, **kwargs):
        """
        Calculate the average of a series of values.

        @keyword list: A list of values to average.
        @keyword district: Optional. A L{District} to get the subject 
            values from. If this is not specified, 'plan' must be provided.
        @keyword plan: Optional. A L{Plan} to get the subject values from. 
            If this is not specified, 'district' must be provided.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        """
        districts = []

        if 'list' in kwargs:
            arg_list = kwargs['list']

            filtered = filter(lambda x:not x is None, arg_list)
            if len(filtered) == 0:
                return

            reduced = reduce(lambda x,y: x+y, filtered)

            self.result = { 'value': reduced / len(filtered) }

        elif 'district' in kwargs :
            districts.append(kwargs['district'])

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs['version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version, include_geom=False)
        else:
            return

        if not 'list' in kwargs:
            total = 0.0
            count = 0.0
            for district in districts:
                if district.district_id == 0:
                    # do nothing with the unassigned districts
                    continue

                count += 1
                argnum = 0
                argsum = 0.0
                while ('value%d' % (argnum+1,)) in self.arg_dict:
                    argnum += 1

                    number = self.get_value('value%d'%argnum, district)
                    if not number is None:
                        argsum += float(number)

                total += argsum / argnum

            if count == 0:
                self.result = None
                return
            
            self.result = { 'value': total / count }

    def html(self):
        """
        Generate an HTML representation of the competitiveness score. This
        is represented as a percentage or "n/a"

        @return: The result wrapped in an HTML SPAN element, formatted similar to: "<span>1.00%</span>" or "<span>n/a</span>".
        """
        if not self.result is None and 'value' in self.result:
            if type(self.result['value']) == float:
                return "<span>%0.2f%%</span>" % (self.result['value'] * 100)
            else:
                return '<span>%s</span>' % self.result['value']

        return '<span>n/a</span>'


class Comments(CalculatorBase):
    """
    Calculate the comments and types associated with a district.

    Not really a calculator, but this occupies a ScorePanel. This 
    calculator just gets the related comments and tags for districts
    in a plan, to enable a ScorePanel to render them.

    This calculator generates the typetags and labeltags required for
    the comment/tagging form template.

    This calculator only accepts districts.
    """
    def compute(self, **kwargs):
        """
        Get the related comments and tags, and store them in a dict for
        the result. The result is suitable for passing to the template
        that renders the comment sidebar.

        @keyword district: The district whose comments should be retrieved.
        """
        if not 'district' in kwargs:
            return
        
        district = kwargs['district']

        typetags = filter(lambda tag:tag.name[:4]=='type', district.tags)
        typetags = map(lambda tag:tag.name[5:], typetags)

        self.result = { 'typetags': typetags }

    def html(self):
        """
        Override the default html method. This is required due to the cache
        mechanism.

        @return: A dict of typetags.
        """
        return self.result


class CommunityTypeCounter(CalculatorBase):
    """
    Count the number of community types which intersect a given district.
    For districts, this calculator will count the number of distinct
    community types that intersect the district.

    This calculator, in addition to requiring a "districts" argument, 
    requires a "community_map_id" argument, which is the primary key
    of the community map (L{Plan}) that is being compared to the district,
    and a "version" argument indicating the version number of the 
    community map.

    This calculator will only operate on a district.
    """
    def compute(self, **kwargs):
        """
        Count the number of community types which intersect a district.

        @keyword district: The L{District} to compare against the community
            map.
        @keyword community_map_id: The ID of the community map.
        @keyword version: Optional. The version of the community map. 
            Defaults to the latest version of the community map.
        """
        districts = []

        if 'district' in kwargs:
            district = kwargs['district']
        else:
            return

        version = None
        if 'version' in kwargs:
            version = kwargs['version']

        self.result = { 'value': 'n/a' }
        if 'community_map_id' in kwargs:
            try:
                self.result = { 'value': district.count_community_type_union(kwargs['community_map_id'], version=version) }
            except:
                pass


class CommunityTypeCompatible(CalculatorBase):
    """
    This calculator determines if all districts in a plan are type-
    compatible. A type-compatible community map contains the same community
    types in across all districts.

    This calculator requires a "community_map_id" argument, which is the 
    primary key of the community map (L{Plan}) that is being compared to 
    the L{Plan} and a "version" argument indicating the version number of
    the community map.

    This calculator will only operate on a plan.
    """
    def compute(self, **kwargs):
        """
        Evaluate a L{Plan} to determine if it is type-compatible. A L{Plan}
        will be type-compatible if the type provided is in all L{District}s
        of the plan.

        @keyword plan: The L{Plan} to compare against the community
            map.
        @keyword community_map_id: The ID of the community map.
        @keyword plan_version: Optional, The version of the plan.
            Defaults to the latest version of the plan.
        @keyword community_version: Optional. The version of the community 
            map.  Defaults to the latest version of the community map.
        @keyword type: The community type to check for compatibility.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']

        if 'plan_version' in kwargs:
            pversion = kwargs['plan_version']
        else:
            pversion = plan.version

        if 'community_version' in kwargs:
            cversion = kwargs['community_version']
        else:
            cversion = None

        districts = plan.get_districts_at_version(pversion, include_geom=True)

        if not 'community_map_id' in kwargs:
            self.result = { 'value': 'n/a' }
            return

        ctype = kwargs['type']
        if not ctype.startswith('type='):
            ctype = 'type=' + ctype

        community_id = kwargs['community_map_id']
        alltypes = None
        for district in districts:
            if district.is_unassigned:
                continue

            tmpset = district.get_community_type_union(community_id, version=cversion)

            if alltypes is None:
                alltypes = tmpset
            else:
                alltypes = alltypes & tmpset

        # simplify all the matching tags to strings, not Tag objects
        alltypes = map(lambda x:str(x.name), alltypes)
        self.result = { 'value': (ctype in alltypes) }


class SplitCounter(CalculatorBase):
    """
    This calculator determines which districts are "split" and how
    often by the districts in a different plan.

    This calculator accepts a "boundary_id" argument, which consists of
    a plan type and id, e.g., "geolevel.1" or "plan.3".

    This calculator also accepts an optional "inverse" value. If this
    is set to 1 (true), the inverse calculation will take place:
    the bottom layer will be treated as the top layer and vice versa.
    
    A "version" argument may be supplied to compare a given version of
    the plan in the keyword args to the plan/geolevel given in the 
    boundary_id.
    """
    def compute(self, **kwargs):
        """
        Calculate splits between a plan and a target layer.

        @keyword plan: A L{Plan} whose districts will be analyzed for 
            splits.
        @keyword version: Optional. The version of the plan, defaults to 
            the most recent version.
        @keyword boundary_id: The layer type and ID to compare for splits.
        @keyword inverse: A flag to indicato if the splits should be 
            compared forward or backward.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']

        # Set the version
        version = self.get_value('version')
        if version is None:
            version = plan.version

        # Use the argument to find "bottom" map
        target = self.get_value('boundary_id')

        # Check if we should invert the order or the layers
        inverse = self.get_value('inverse') == 1

        self.result = { 'value': plan.compute_splits(target, version=version, inverse=inverse) }

    def html(self):
        """
        Generate an HTML representation of the split report. This is 
        represented as an HTML fragment containing a TABLE element with
        the splits listed in the cells.

        @return: An HTML TABLE element with the split geographies/districts.
        """
        render = '<div class="split_report">'
        if not self.result is None and 'value' in self.result:
            r = self.result['value']
            total_split_districts = len(set(i[0] for i in r['splits']))
            

            if r['is_geolevel']:
                template = '<div>Total %s which split a %s: %d</div>'
            else:
                template = '<div>Total %s splitting "%s": %d</div>'

            render += template % ('communities' if r['is_community'] else 'districts', r['other_name'], total_split_districts)
            render += '<div>Total number of splits: %d</div>' % len(r['splits'])

            render += '<div class="table_container"><table class="report"><thead><tr><th>%s</th><th>%s</th></tr></thead><tbody>' % (r['plan_name'].capitalize(), r['other_name'].capitalize() if r['is_geolevel'] else r['other_name'].capitalize())
            for s in r['named_splits']:
                render += '<tr><td>%s</td><td>%s</td></tr>' % (s[0], s[1])

            render += '</tbody></table></div>'

        render += '</div>'

        return render

