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

    def sortkey(self):
        """
        How should this calculator be compared to others like it? The
        default sorting method sorts by the value of the result.
        """
        return self.result

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
            district - A district whose compactness should be computed.
            plan -- A plan whose district compactnesses should be averaged.
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
            if district.district_id == 0:
                continue

            if district.geom is None:
                continue

            if district.geom.length == 0:
                continue
        
            r = sqrt(district.geom.area / pi)
            perimeter = 2 * pi * r
            compactness += perimeter / district.geom.length
            num += 1

        self.result = (compactness / num) if num > 0 else 0


    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"
        """
        return ("%0.2f%%" % (self.result * 100)) if self.result else "n/a"


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

        Keywords:
            district -- A district whose compactness should be computed.
            plan -- A plan whose district compactnesses should be averaged.
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
            if district.district_id == 0:
                continue

            if district.geom is None:
                continue

            centroid = district.geom.centroid
            maxd = 0
            for linestring in district.geom.convex_hull:
                for coord in linestring:
                    maxd = max(maxd, centroid.distance(Point(coord)))

            cir_area = pi * maxd * maxd

            compactness += district.geom.area / cir_area
            num += 1

        self.result = compactness / num

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"
        """
        return ("%0.2f%%" % (self.result * 100)) if self.result else "n/a"


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

        Keywords:
            district -- A district whose compactness should be computed.
            plan -- A plan whose district compactnesses should be averaged.
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
            if district.district_id == 0:
                continue

            if district.geom is None:
                continue

            perimeter = 0
            for poly in district.geom:
                for linestring in poly:
                    perimeter += linestring.length

            compactness += 4 * pi * district.geom.area / perimeter / perimeter
            num += 1

        self.result = compactness / num

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"
        """
        return ("%0.2f%%" % (self.result * 100)) if self.result else "n/a"


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

        Keywords:
            district -- A district whose compactness should be computed.
            plan -- A plan whose district compactnesses should be averaged.
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
            if district.district_id == 0:
                continue

            if district.geom is None:
                continue

            bbox = district.geom.extent
            compactness += (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])
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

    For lists of numbers, this calculator will return the sum of the list.

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
        elif 'list' in kwargs:
            lst = kwargs['list']
            self.result = reduce(lambda x,y: x + y, lst)
            return
        else:
            return
        
        self.result = 0

        for district in districts:
            if district.district_id == 0:
                continue

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
                if district.district_id == 0:
                    continue

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
    result value will be zero (0).

    If the value computed is greater than the threshold, the result value
    will be one (1).

    If this calculator is called with a plan, it will tally up the number
    of districts that exceed the designated threshold.
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
            val = self.get_value('value',district)
            thr = self.get_value('threshold',district)

            if val is None or thr is None:
                continue

            if float(val) > float(thr):
                self.result += 1


class Range(CalculatorBase):
    """
    Determine a value, and indicate if it falls within a range

    This calculator accepts three arguments: "value", "min", and "max". The
    result of this calculator is 1 or 0, to facilitate the combination of
    scores. One example may be where the number of districts that fall 
    within a range are required.
    
    If the value computed is greater than or equal to min and less than 
    or equal to max, the result value will be zero (1).

    If the value computed is less than min or greater than max, the result
    value will be one (1).

    If the calculator is passed a plan, then the result value will be the
    number of districts that are within the range. For a test like equi-
    population, this will count the number of districts within the target
    range.
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
        districts = None

        if 'district' in kwargs:
            districts = [kwargs['district']]

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=False)

        else:
            return

        self.result = 0
        for district in districts:
            val = self.get_value('value',district)
            minval = self.get_value('min',district)
            maxval = self.get_value('max',district)

            if val is None or minval is None or maxval is None:
                continue

            if float(val) > float(minval) and float(val) < float(maxval):
                self.result += 1


class Contiguity(CalculatorBase):
    """
    Calculate the contiguity of a district.

    This calculator accepts an optional argument: 'allow_single_point'.
    If this is set to '1' (True), the calculator will consider a district containing
    muliple polygons contiguous if the polygons are connected to each other by a
    minimum of one point. By default, this is set to '0' (False), and a district is
    only considered to be congiguous if it is comprised of a single polygon

    'ContiguityOverride' objects that are applicable to the district will be applied
    to allow for special cases where non-physical contiguity isn't possible.
    
    If the district is contiguous, the result value will be zero (0).

    If the district is discontiguous, the result value will be one (1).

    If this calculator is called with a plan, it will tally up the number
    of districts that are contiguous.

    """
    def compute(self, **kwargs):
        """
        Determine if a district is continuous.
        """
        districts = []

        if 'district' in kwargs:
            districts = [kwargs['district']]

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=True)

        else:
            return

        if 'allow_single_point' in self.arg_dict:
            allow_single = int(self.arg_dict['allow_single_point'][1]) == 1
        else:
            allow_single = False

        self.result = 0
        for district in districts:
            if district.district_id == 0:
                continue

            if len(district.geom) == 1: 
                self.result += 1
            else:
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
                        self.result += 1
    

class AllContiguous(CalculatorBase):
    """
    Used to verify that all districts in a plan are contiguous.

    This calculator will only operate on a plan.
    """
    def compute(self, **kwargs):
        if not 'plan' in kwargs:
            return

	plan = kwargs['plan']
        districts = plan.get_districts_at_version(plan.version, include_geom=False)

        calc = Contiguity()
        calc.compute(**kwargs)

        # ALL PLANS include 1 district named "Unassigned", which cannot be
        # removed. Therefore the actual target to be validated is one less
        # than the number of districts.
        self.result = (len(districts)-1) == calc.result


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

    def html(self):
        """
        Generate an HTML representation of the equivalence score. This
        is represented as an integer formatted with commas or "n/a"
        """
        return intcomma(int(self.result)) if self.result else "n/a"

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
            if district.district_id == 0:
                continue

            tmpval = self.get_value('value',district)
            if not tmpval is None:
                min_d = min(float(tmpval), min_d)
                max_d = max(float(tmpval), max_d)

        self.result = max_d - min_d


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

        if 'plan' in kwargs:
            plan = kwargs['plan']
            districts = plan.get_districts_at_version(plan.version, include_geom=False)

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

        self.result = dems - reps

    def html(self):
        """
        Display the results in HTML format. Since the results for this
        calculator are in tuple format for sorting purposes, it's important
        to display a human readable score that explains which party the 
        plan is biased toward
        """
        sort = abs(self.result)
        party = 'Democrat' if self.result > 0 else 'Republican'
        if sort == 0:
            return '<span>Balanced</span>'
        else:
            return '<span>%s&nbsp;%d</span>' % (party, sort)

    def json(self):
        """
        Return a basic JSON representation of the result.
        """
        sort = abs(self.result)
        party = 'Democrat' if self.result > 0 else 'Republican'
        return json.dumps( {'result': '%s %d' % (party, sort)} )

    def sortkey(self):
        """
        How should this calculator be compared to others like it? 
        Sort by the absolute value of the result (farther from zero
        is a worse score).
        """
        return abs(self.result)


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
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Compute the competitiveness.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        districts = plan.get_districts_at_version(plan.version, include_geom=False)
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

        self.result = fair

class CountDistricts(CalculatorBase):
    """
    Count the number of districts in a plan, and determine if that number
    matches a target.

    This calculator works on plans only.

    This calculator requires an argument 'target' set to the number of
    districts desired in a plan.  If the number of districts matches
    the target value, a boolean True is the result.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Compute the number of districts in a plan, and determine if that
        number matches a target.
        """
        if not 'plan' in kwargs or not 'target' in self.arg_dict:
            return

        plan = kwargs['plan']
        districts = plan.get_districts_at_version(plan.version, include_geom=False)
        # ALL PLANS include 1 district named "Unassigned", which cannot be
        # removed. Therefore the actual target to be validated is one less
        # than the number of districts.
        target = int(self.get_value('target'))

        self.result = (len(districts)-1) == target


class AllBlocksAssigned(CalculatorBase):
    """
    Determine if all the blocks in the state are assigned to a district.
    
    This calculator works on plans only.

    This calculator has an optional argument of 'threshold', which is used
    for buffer in/out optimization
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = { 'threshold': ('literal', 100)}

    def compute(self, **kwargs):
        """
        Determine if all the blocks in the state are assigned to a district.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']

        threshold = self.get_value('threshold')
        geounits = plan.get_unassigned_geounits(threshold)
        self.result = len(geounits) == 0


class Equipopulation(CalculatorBase):
    """
    Determine if all the districts in a plan fall within a target range of
    population. This merely wraps a Range calculator, but looks for the
    number of districts outside the range.

    This calculator works on plans only.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Determine if all the districts in a plan fall within a target range.
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']

        inrange = Range()
        inrange.arg_dict = self.arg_dict
        inrange.compute(plan=plan)

        districts = plan.get_districts_at_version(plan.version, include_geom=False)

        # ALL PLANS include 1 district named "Unassigned", which should 
        # never be at the target.
        self.result = inrange.result == (len(districts) - 1)


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

    This calculator works on plans only.
    """
    def __init__(self):
        """
        Initialize the result and argument dictionary.
        """
        self.result = None
        self.arg_dict = {}

    def compute(self, **kwargs):
        """
        Determine if the requisite number of districts in a plan have a 
        majority of minority population. 
        """
        if not 'plan' in kwargs:
            return

        plan = kwargs['plan']
        districts = plan.get_districts_at_version(plan.version, include_geom=False)

        districtcount = 0
        self.result = False
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

                if num / den > threshold:
                    exceeds = True
                    break

            if exceeds:
                districtcount += 1

        try:
            count = float(self.get_value('count', district))
        except:
            count = 1

        self.result = districtcount >= count
