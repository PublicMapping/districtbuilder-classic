"""
Define the calculators used for scoring in the redistricting app.

The classes in redistricting.calculators define the scoring
calculators used in the application. Each class relates to
one type of calculator that can be referenced within the config
file to define how to score a plan or district.

This file is part of The Public Mapping Project
https://github.com/PublicMapping/

License:
    Copyright 2010-2012 Micah Altman, Michael McDonald

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
from django.contrib.gis.geos import Point, LineString
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.cache import caches
from django.utils.translation import ugettext as _
from django.template import Template, Context
from decimal import Decimal
from copy import copy
import random

from django.db.models import Q
import operator
import itertools
import json
from django.conf import settings
from redisutils import key_gen
redis_settings = settings.KEY_VALUE_STORE


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


class CalculatorBase(object):
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
        is None, the string "n/a" is used. If 'raw' is defined, the value
        of raw is used (for fine-grained control using templates).

        @return: An HTML SPAN element, formatted similar to: "<span>n/a</span>".
        """
        if not self.result is None and 'value' in self.result:
            return self.template('<span>{{ result.value }}</span>')

        if not self.result is None and 'raw' in self.result:
            return self.result['raw']

        return self.empty_html_result

    empty_html_result = '<span>%s</span>' % _('n/a')
    """
    In case of an empty result, return a span with the properly
    localized version of 'n/a'
    """

    def json(self):
        """
        Generate a basic JSON representation of the result.

        The base calculator generates an simple Javascript object that
        contains a single property, named "result".

        @return: A JSON string with a single object that contains the
            property 'result'.
        """
        if not self.result is None and 'value' in self.result:
            output = {'result': self.result['value']}
        else:
            output = {'result': None}

        return json.dumps(output, cls=DecimalEncoder)

    def template(self, template, context=None):
        """
        Generate a representation of the score using the django
        templating system and the calculator's result. Required
        for localizing number formats.

        @param template: A string that may use django template tags
        @param context: A dict object representing additional context
            to be used when rendering the template. The "result" of
            the calculator is always available.

        @return: A string representing the rendering template and context
        """
        t = Template(template)
        c = Context({'result': self.result})
        if context is not None:
            c.update(context)
        return t.render(c)

    def percentage(self, span=False):
        """
        Return the calculator's result value as a properly localized
        percentage

        @return: A string representing the result as a percentage
        """
        if span:
            t = Template('<span>{{ percentage|floatformat:2 }}%</span>')
        else:
            t = Template('{{ percentage|floatformat:2 }}%')
        c = Context({'percentage': self.result['value'] * 100})
        return t.render(c)

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
            if isinstance(argval, dict) and 'value' in argval:
                value = Decimal(argval['value'])
            else:
                try:
                    # If our literal is a number, make it a decimal to match models
                    value = Decimal(value)
                except:
                    # No problem, it may be a string
                    pass
        elif argtype == 'subject' and not district is None:
            # This method is more fault tolerant than _set.get, since it
            # won't throw an exception if the item doesn't exist.
            add_subject = True
            if argval.startswith('-'):
                add_subject = False
                argval = argval[1:]
            cc = district.computedcharacteristic_set.filter(
                subject__name=argval)
            if cc.count() > 0:
                value = cc[0].number if add_subject else -cc[0].number
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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=True)

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

        self.result = {'value': (compactness / num) if num > 0 else 0}

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return self.percentage()
        else:
            return _('n/a')


class Roeck(CalculatorBase):
    """
    Calculator for the Roeck measure of compactness.

    The Roeck measure of compactness measures the area of the smallest
    enclosing circle around a district compared to the area of the district.

    This calculator will calculate either the compactness score of a single
    district, or it will average the compactness scores of all districts
    in a plan.
    """
    rec = 0

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
        random.seed()
        districts = []
        if 'district' in kwargs:
            districts = [kwargs['district']]
            if districts[0].geom.empty:
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=True)

        else:
            return

        num = 0
        compactness = 0
        for district in districts:
            if district.district_id == 0:
                continue

            if district.geom.empty:
                continue

            # Convert the coordinates in the convex hull to a list of GEOS Points
            hull = map(lambda x: Point(x[0], x[1]),
                       list(district.geom.convex_hull.coords[0]))
            disk = self.minidisk(hull)

            cir_area = pi * disk.r * disk.r

            compactness += district.geom.area / cir_area
            num += 1

        try:
            self.result = {'value': compactness / num if num > 0 else 0}
        except:
            self.result = {'value': _('n/a')}

    class Circle:
        """
        Helper class for the Roeck calculator. A Circle class can create circles based
        on 1, 2, or 3 coordinates. A circle has a center and a radius. A circle also
        can test if another point lies within the area of itself.
        """
        cx = None
        cy = None
        r = None

        def __init__(self, pts):
            """
            Create a new Circle helper. Constructing a Circle with one coordinate
            creates a 0 diameter circle, centered on the coordinate. Constructing
            a Circle with two coordinates creates a circle positioned between the
            two coordinates, with the diameter set to the distance between the
            points. Constructing a Circle with three coordinates creates a circle
            that passes through all three points.

            @param pts: A set of points that lay on the perimeter of this circle.

            @return: A calculated Circle that contains the coordinates.
            """
            if len(pts) == 1:
                # Create a zero diameter circle at the coordinate location
                self.cx = pts[0].coords[0]
                self.cy = pts[0].coords[1]
                self.r = 0
            elif len(pts) == 2:
                # Create a circle between the coordinates, with the diameter
                # set to the distance between the points.
                ls = LineString(pts)
                self.cx = ls.centroid.x
                self.cy = ls.centroid.y
                self.r = ls.length / 2
            elif len(pts) == 3:
                # Create a circle that contains all three points
                try:
                    (
                        p1,
                        p2,
                        p3,
                    ) = self.deperpendicularize(pts)
                except ValueError:
                    # If the coordinates cannot be deperpendicularized, assume
                    # that they are colinear.
                    ls = LineString(pts)
                    self.cx = ls.centroid.x
                    self.cy = ls.centroid.y
                    self.r = ls.length / 2
                    return

                # If the coordinates describe a pair of lines that are perpendicular
                # and are parallel to the X and Y axes, the center of that rectangle
                # is the center of the circle.
                if abs(p2.coords[0] - p1.coords[0]) == 0 and abs(
                        p3.coords[1] - p2.coords[1]) == 0:
                    self.cx = (p2.coords[0] + p3.coords[0]) / 2
                    self.cy = (p1.coords[1] + p2.coords[1]) / 2
                    ls = LineString([p1, Point(self.cx, self.cy)])
                    self.r = ls.length
                    return

                # Determination of the center point is described pretty well here:
                #
                # "Equation of a Circle from 3 Points (2 dimensions)"
                # http://paulbourke.net/geometry/circlefrom3/
                #
                m1 = (p2.coords[1] - p1.coords[1]) / (
                    p2.coords[0] - p1.coords[0])
                m2 = (p3.coords[1] - p2.coords[1]) / (
                    p3.coords[0] - p2.coords[0])

                self.cx = (m1 * m2 * (p1.coords[1] - p3.coords[1]) + \
                    m2 * (p1.coords[0] + p2.coords[0]) - \
                    m1 * (p2.coords[0] + p3.coords[0]) ) / \
                    (2 * (m2-m1) )
                self.cy = -1 * (self.cx - (p1.coords[0]+p2.coords[0]) / 2.0) / m1 + \
                    (p1.coords[1] + p2.coords[1]) / 2.0
                lsR = LineString(pts[0], (
                    self.cx,
                    self.cy,
                ))
                self.r = lsR.length
            else:
                # Creating a circle with 0 or > 3 coordinates is not supported.
                self.cx = None
                self.cy = None
                self.r = None

        def deperpendicularize(self, pts):
            """
            Reorder coordinates to ensure that they are not perpendicular
            in a way that may cause divide by zero exceptions. This tests
            all 6 permutations of the point set, testing it with the
            isperpendicular method.

            @params pts: A set of points, passed in as an array
            @return: A 3 element tuple with the reordered points.
            """
            if not self.isperpendicular(pts[0], pts[1], pts[2]):
                return (
                    pts[0],
                    pts[1],
                    pts[2],
                )
            if not self.isperpendicular(pts[0], pts[2], pts[1]):
                return (
                    pts[0],
                    pts[2],
                    pts[1],
                )
            if not self.isperpendicular(pts[1], pts[0], pts[2]):
                return (
                    pts[1],
                    pts[0],
                    pts[2],
                )
            if not self.isperpendicular(pts[1], pts[2], pts[0]):
                return (
                    pts[1],
                    pts[2],
                    pts[0],
                )
            if not self.isperpendicular(pts[2], pts[1], pts[0]):
                return (
                    pts[2],
                    pts[1],
                    pts[0],
                )
            if not self.isperpendicular(pts[2], pts[0], pts[1]):
                return (
                    pts[2],
                    pts[0],
                    pts[1],
                )

            # Raise a general exception here, and fall back to
            # estimating a 2 point circle.
            raise ValueError('All combinations are perpendicular.')

        def isperpendicular(self, pt1, pt2, pt3):
            """
            Test a set of points to see if they are perpendicular.
            Points are deemed perpendicular if they describe two
            different lines that are parallel to the X and Y axes.

            @param pt1: The first point to test.
            @param pt2: The second point to test.
            @param pt3: The third point to test.

            @return: A boolean flag indicating if the points describe
            a set of perpendicular lines that are parallel with the
            X and Y axes.
            """
            dy1 = pt2.coords[1] - pt1.coords[1]
            dx1 = pt2.coords[0] - pt1.coords[0]
            dy2 = pt3.coords[1] - pt2.coords[1]
            dx2 = pt3.coords[0] - pt2.coords[0]

            if abs(dx1) == 0 and abs(dy2) == 0:
                return False
            elif abs(dy1) == 0:
                return True
            elif abs(dy2) == 0:
                return True
            elif abs(dx1) == 0:
                return True
            elif abs(dx2) == 0:
                return True

            return False

        def contains(self, pt):
            """
            Does this circle contain a specified point.

            @param: pt The specified point
            @return: A boolean flag indicating if the specified point lies
                     within the area of the Circle.
            """
            ls = LineString([pt, Point(self.cx, self.cy)])
            return ls.length <= self.r

    def minidisk(self, points):
        """
        A recursive minimum enclosing disk algorithm. Based on E. Welzl,
        "Smallest enclosing disks (balls and ellipsoids)", 1991.

        This code borrows some patterns from the applet source here:
        http://www.sunshine2k.de/stuff/Java/Welzl/Welzl.html

        @param points: An array of points, from a GEOSGeometry.
        @return: A L{Roeck.Circle} minimum enclosing disk for the points.
        """
        self.rec = 0
        shuffled = copy(points[1:])
        random.shuffle(shuffled)
        return self.b_minidisk(shuffled, len(shuffled), [None, None, None], 0)

    def b_minidisk(self, points, npts, boundary, nbnd):
        """
        A recursive minimum enclosing disk algorithm. Based on E. Welzl,
        "Smallest enclosing disks (balls and ellipsoids)", 1991.

        This code borrows some patterns from the applet source here:
        http://www.sunshine2k.de/stuff/Java/Welzl/Welzl.html

        @param points: A random array of non-duplicating points.
        @param npts: The position in the point array for searching.
        @param boundary: The farthest outliers on or in the smallest disk.
        @param nbnd: The index of the boundary list for the next boundary point.
        @return: A L{Roeck.Circle} minimum enclosing disk for the points.
        """
        if npts == 1 and nbnd == 0:
            disk = Roeck.Circle([points[0]])
        elif npts == 1 and nbnd == 1:
            disk = Roeck.Circle([points[0], boundary[0]])
        elif npts == 0 and nbnd == 2:
            disk = Roeck.Circle(boundary[0:2])
        elif nbnd == 3:
            disk = Roeck.Circle(boundary)
        else:
            self.rec += 1
            disk = self.b_minidisk(points, npts - 1, boundary, nbnd)

            if not disk.contains(points[npts - 1]):
                boundary[nbnd] = points[npts - 1]

                self.rec += 1
                disk = self.b_minidisk(points, npts - 1, boundary, nbnd + 1)

        self.rec -= 1
        return disk

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return self.percentage()
        else:
            return _("n/a")


class PolsbyPopper(CalculatorBase):
    """
    Calculator for the Polsby-Popper measure of compactness.

    The Polsby-Popper measure of compactness measures the area of a circle
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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=True)

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

        self.result = {'value': compactness / num}

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return self.percentage()
        else:
            return _("n/a")


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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=True)

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
            lw = (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])
            if lw > 1:
                lw = 1 / lw

            compactness += lw
            num += 1

        self.result = {'value': compactness / num if num > 0 else 0}

    def html(self):
        """
        Generate an HTML representation of the compactness score. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return self.percentage()
        else:
            return _("n/a")


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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=False)
        elif 'list' in kwargs:
            lst = kwargs['list']
            self.result = {'value': reduce(lambda x, y: x + y, lst)}
            return
        else:
            return

        sumvals = 0

        for district in districts:
            argnum = 1
            while ('value%d' % argnum) in self.arg_dict:
                number = self.get_value('value%d' % argnum, district)
                if not number is None:
                    sumvals += number

                argnum += 1

        if self.get_value('target') is not None:
            target = self.get_value('target')
            self.result = {'value': "%d (of %s)" % (sumvals, target)}
        else:
            self.result = {'value': sumvals}

    def html(self):
        """
        Generate an HTML representation of the summation score. This
        is represented as a decimal formatted with commas or "n/a".

        @return: The result wrapped in an HTML SPAN element: "<span>1</span>".
        """
        if not self.result is None and 'value' in self.result:
            return self.template(
                '<span>{{ result.value|floatformat:0 }}</span>')
        return self.empty_html_result


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

            num = self.get_value('numerator', district)
            den = self.get_value('denominator', district)

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=False)
            num = 0
            den = 0
            for district in districts:
                if district.district_id == 0:
                    continue

                tmpnum = self.get_value('numerator', district)
                tmpden = self.get_value('denominator', district)

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

        try:
            self.result = {'value': num / den}
        except:
            # TODO: temporary fix
            if den['value'] == 0:
                self.result = {'value': 0}
            else:
                self.result = {'value': num / den['value']}

    def html(self):
        """
        Generate an HTML representation of the percentage score. This
        is represented as a decimal formatted with commas or "n/a"

        @return: The result wrapped in an HTML SPAN element, formatted similar to: "<span>1.00%</span>" or "<span>n/a</span>".
        """
        if not self.result is None and 'value' in self.result:
            return self.percentage()

        return self.empty_html_result


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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=False)

        else:
            return

        count = 0
        for district in districts:
            val = self.get_value('value', district)
            thr = self.get_value('threshold', district)

            if val is None or thr is None:
                continue

            if float(val) > float(thr):
                count += 1

        self.result = {'value': count}


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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=False)

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

            val = self.get_value('value', district)

            if apply_num_members and district.num_members > 1:
                val = float(val) / district.num_members

            minval = self.get_value('min', district)
            maxval = self.get_value('max', district)

            if val is None or minval is None or maxval is None:
                continue

            if float(val) > float(minval) and float(val) < float(maxval):
                count += 1

        self.result = {'value': count}


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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=True)

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
                                    if (geom.contains(o) and union.contains(c)
                                        ) or (geom.contains(c)
                                              and union.contains(o)):
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

        self.result = {'value': count}
        try:
            target = self.get_value('target')
            if target != None:
                self.result = {
                    'value': _('%(value)d (of %(target)s)') % {
                        'value': count,
                        'target': target
                    }
                }
        except:
            pass

    def html(self):
        """
        Generate an HTML representation of the contiguity score. This
        is represented as an image element or the string result wrapped
        in a SPAN element if the result is non-numeric.

        @return: An HTML IMG element in the form of: '<img class="(yes|no)-contiguous" src="/static/images/icon-(check|warning).png">'
        """
        if not self.result is None and 'value' in self.result:
            if type(self.result['value']) == int:
                if self.result['value'] == 1:
                    return '<img class="yes-contiguous" src="/static/images/icon-check.png">'
                else:
                    return '<img class="no-contiguous" src="/static/images/icon-warning.png">'
            else:
                return CalculatorBase.html(self)

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

        self.result = {'value': (len(districts) - 1) == calc.result['value']}


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
                self.result = {
                    'value': _('%(value)d (of %(target)s)') % {
                        'value': count,
                        'target': target
                    }
                }
        except:
            self.result = {'value': count}


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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=True)

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

            self.result = {'value': count}
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
                t = '<span class="{{ class }} {{ result.subject }}">' \
                    '{{ result.value|floatformat:0 }}</span>'
                c = {'class': interval_class}
                return self.template(t, c)
        return self.empty_html_result


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
        districts = plan.get_districts_at_version(version, include_geom=False)
        if len(districts) == 0:
            return

        if 'apply_num_members' in self.arg_dict:
            apply_num_members = int(self.arg_dict['apply_num_members'][1]) == 1
        else:
            apply_num_members = False

        min_d = 1000000000  # 1B enough?
        max_d = 0
        for district in districts:
            if district.district_id == 0:
                continue

            tmpval = self.get_value('value', district)
            if apply_num_members and district.num_members > 1:
                tmpval = float(tmpval) / district.num_members

            if not tmpval is None:
                min_d = min(float(tmpval), min_d)
                max_d = max(float(tmpval), max_d)

        self.result = {'value': max_d - min_d}

    def html(self):
        """
        Generate an HTML representation of the equivalence score. This
        is represented as an integer formatted with commas or "n/a"

        @return: A string in the format of "1,000" or "n/a" if no result.
        """
        if not self.result is None and 'value' in self.result:
            return self.template('{{ result.value|floatformat:0 }}')

        return _('n/a')


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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=False)

        else:
            return

        dems = 0
        reps = 0
        for district in districts:
            dem = self.get_value('democratic', district)
            rep = self.get_value('republican', district)
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

        self.result = {'value': dems - reps}

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
            party = _('Democrat') if self.result['value'] > 0 else _(
                'Republican')
            if sort == 0:
                return '<span>%s</span>' % _('Balanced')
            else:
                return '<span>%s&nbsp;%d</span>' % (party, sort)

        return '<span>%s</span>' % _('n/a')

    def json(self):
        """
        Generate a basic JSON representation of the result.

        @return: A JSON object with 1 property: result.
        """
        if not self.result is None and 'value' in self.result:
            sort = abs(self.result['value'])
            party = _('Democrat') if self.result['value'] > 0 else _(
                'Republican')
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

            tmpdem = self.get_value('democratic', district)
            tmprep = self.get_value('republican', district)

            if tmpdem is None or tmprep is None:
                continue

            dem = float(tmpdem)
            rep = float(tmprep)

            if dem == 0.0 and rep == 0.0:
                continue

            pidx = dem / (dem + rep)
            if pidx > low and pidx < high:
                fair += 1

        self.result = {'value': fair}


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

        self.result = {'value': (len(districts) - 1) == target}


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

        geounits = plan.get_unassigned_geounits(
            threshold=threshold, version=version)
        self.result = {'value': len(geounits) == 0}


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

                self.result = {
                    'value': inrange.result['value'] == (len(districts) - 1)
                }
            elif target != None:
                self.result = {
                    'value': _('%(value)d (of %(target)s)') % {
                        'value': inrange.result['value'],
                        'target': target
                    }
                }
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

        if 'apply_num_members' in self.arg_dict:
            apply_num_members = int(self.arg_dict['apply_num_members'][1]) == 1
        else:
            apply_num_members = False

        districtcount = 0
        for district in districts:
            pop = self.get_value('population', district)

            if pop is None:
                continue

            den = float(pop)
            argnum = 1
            exceeds = False
            while ('minority%d' % argnum) in self.arg_dict:
                minor = self.get_value('minority%d' % argnum, district)
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
                if apply_num_members:
                    districtcount += district.num_members
                else:
                    districtcount += 1

        self.result = {'value': districtcount}

        try:
            target = self.get_value('target')
            validation = self.get_value('validation')
            if validation != None:
                self.result = {'value': districtcount >= Decimal(validation)}
            elif target != None:
                self.result = {
                    'value': _('%(value)d (of %(target)s)') % {
                        'value': districtcount,
                        'target': target
                    }
                }
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
        self.result = {'value': False}

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
                    if (d.num_members < min_dist_mems) or (d.num_members >
                                                           max_dist_mems):
                        return

            # Check number of multi-member districts
            if (total_multi_dists < min_multi_dists) or (total_multi_dists >
                                                         max_multi_dists):
                return

            # Check number of districts per plan
            if (total_members < min_plan_mems) or (total_members >
                                                   max_plan_mems):
                return

        self.result = {'value': True}


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

            filtered = filter(lambda x: not x is None, arg_list)
            if len(filtered) == 0:
                return

            reduced = reduce(lambda x, y: x + y, filtered)

            self.result = {'value': reduced / len(filtered)}

        elif 'district' in kwargs:
            districts.append(kwargs['district'])

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=False)
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
                while ('value%d' % (argnum + 1, )) in self.arg_dict:
                    argnum += 1

                    number = self.get_value('value%d' % argnum, district)
                    if not number is None:
                        argsum += float(number)

                total += argsum / argnum

            if count == 0:
                self.result = None
                return

            self.result = {'value': total / count}

    def html(self):
        """
        Generate an HTML representation of the competitiveness score. This
        is represented as a percentage or "n/a"

        @return: The result wrapped in an HTML SPAN element, formatted similar to: "<span>1.00%</span>" or "<span>n/a</span>".
        """
        if not self.result is None and 'value' in self.result:
            if type(self.result['value']) == float:
                return self.percentage(span=True)
            else:
                return CalculatorBase.html(self)

        return self.empty_html_result


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

        typetags = filter(lambda tag: tag.name[:4] == 'type', district.tags)
        typetags = map(lambda tag: tag.name[5:], typetags)

        self.result = {'typetags': typetags}

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
        if 'district' in kwargs:
            district = kwargs['district']
        else:
            return

        version = None
        if 'version' in kwargs:
            version = kwargs['version']

        self.result = {'value': _('n/a')}
        if 'community_map_id' in kwargs:
            try:
                self.result = {
                    'value':
                    district.count_community_type_union(
                        kwargs['community_map_id'], version=version)
                }
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
            self.result = {'value': 'n/a'}
            return

        ctype = kwargs['type']
        if not ctype.startswith('type='):
            ctype = 'type=' + ctype

        community_id = kwargs['community_map_id']
        alltypes = None
        for district in districts:
            if district.is_unassigned:
                continue

            tmpset = district.get_community_type_union(
                community_id, version=cversion)

            if alltypes is None:
                alltypes = tmpset
            else:
                alltypes = alltypes & tmpset

        # simplify all the matching tags to strings, not Tag objects
        alltypes = map(lambda x: str(x.name), alltypes)
        self.result = {'value': (ctype in alltypes)}


class SplitCounter(CalculatorBase):
    """
    This calculator determines which districts are "split" and how
    often by the districts in a different plan.

    This calculator accepts a "boundary_id" argument, which consists of
    a plan type and id, e.g., "geolevel.1" or "plan.3".

    This calculator also accepts an optional "inverse" value. If this
    is set to 1 (true), the inverse calculation will take place:
    the bottom layer will be treated as the top layer and vice versa.

    This calculator also accepts an optional "only_total" value. If this
    is set to 1 (true), only the total number of splits will be returned.

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
        @keyword inverse: A flag to indicate if the splits should be
            compared forward or backward.
        @keyword only_total: A flag to indicate if only the total number
            of splits should be returned.
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

        # Check if we only need to return the total in the html
        only_total = (self.get_value('only_total') == 1)
        splits = plan.compute_splits(target, version=version, inverse=inverse)

        self.result = {
            'value': len(splits['splits']) if only_total else splits,
            'only_total': only_total
        }

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

            # If 'only_total' is set, only return the total number of splits
            if self.result['only_total']:
                return '<span>%d</span>' % r

            total_split_districts = len(set(i[0] for i in r['splits']))

            if r['is_geolevel']:
                template = '<div>%s</div>' % _('Total %(district_type_a)s ' \
                    'which split a %(district_type_b)s: %(result)d')
            else:
                template = '<div>%s</div>' % _('Total %(district_type_a)s ' \
                    'splitting "%(district_type_b)s": %(result)d</div>')

            render += template % {
                'district_type_a':
                'communities' if r['is_community'] else 'districts',
                'district_type_b':
                r['other_name'],
                'result':
                total_split_districts
            }
            render += '<div>%s: %d</div>' % (_('Total number of splits'),
                                             len(r['splits']))

            render += '<div class="table_container"><table class="report"><thead><tr><th>%s</th><th>%s</th></tr></thead><tbody>' % (
                r['plan_name'].capitalize(), r['other_name'].capitalize()
                if r['is_geolevel'] else r['other_name'].capitalize())

            for s in r['named_splits']:
                render += '<tr><td>%s</td><td>%s</td></tr>' % (s['geo'],
                                                               s['interior'])

            render += '</tbody></table></div>'

        render += '</div>'

        return render


class DistrictSplitCounter(CalculatorBase):
    """
    This calculator determines how many times a district splits a given geolevel.

    This calculator accepts a "geolevel_id" argument, which is the id of
    the geolevel in which to perform the split comparison.
    """

    def compute(self, **kwargs):
        """
        Calculate splits between a district and a target geolevel.

        @keyword district: A L{District} whose splits should be computed.
        @keyword boundary_id: The ID of the geolevel to compare for splits.
        """
        if not 'district' in kwargs:
            return

        district = kwargs['district']
        if district.geom.empty:
            return

        geolevel_id = self.get_value('geolevel_id')
        num_splits = district.count_splits(geolevel_id)

        self.result = {'value': num_splits}


class ConvexHullRatio(CalculatorBase):
    """
    Calculate the ratio of the area of a district to the area of its convex hull.

    This calculator will either calculate a single district's convex hull ratio,
    or the average convex hull ratio of all districts.
    """

    def compute(self, **kwargs):
        """
        Calculate the convex hull ratio of a district or a plan.

        @keyword district: A L{District} whose convex hull ratio should be
            computed.
        @keyword plan: A L{Plan} whose district convex hull ratios should be
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
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(
                version, include_geom=True)

        else:
            return

        num = 0
        ratios = 0.0
        for district in districts:
            if district.geom.empty or district.geom.length == 0 or district.district_id == 0:
                continue

            ratios += district.geom.area / district.geom.convex_hull.area
            num += 1

        self.result = {'value': (ratios / num) if num > 0 else 0}

    def html(self):
        """
        Generate an HTML representation of the convex hull ratio. This
        is represented as a percentage or "n/a"

        @return: A number formatted similar to "1.00%", or "n/a"
        """
        if not self.result is None and 'value' in self.result:
            return self.percentage()
        else:
            return _('n/a')


class Adjacency(CalculatorBase):
    """
    Calculates travel time, costs, etc. between sections in a district, normalizes by region
    travel time.
    """

    def _district_calculator(self, district):
        def sum_query(query):
            return sum(
                map(lambda x: float(x) if x else 0,
                    self.cache.get_many(query)))

        geounit_ids = [geo[1] for geo in district.get_base_geounits()]
        geounit_ids.sort()
        geounit_id_combos = itertools.combinations(geounit_ids, 2)
        redis_query = []
        total = 0
        num_queries = 0
        for count, ids in enumerate(geounit_id_combos):
            num_queries += 1
            if count % 10000 == 0 and count > 0:
                total += sum_query(redis_query)
                redis_query = []

            redis_query.append(
                key_gen(**{
                    'geounit1': ids[0],
                    'geounit2': ids[1]
                }))

        total += sum_query(redis_query)

        # return 0 to prevent a divide-by-zero error
        if num_queries == 0:
            return 0

        return total / num_queries

    def compute(self, **kwargs):
        """
        Calculate the average costs for a district or the overall score for a plan.

        The score for a district is the average cost between all sections within a district.

        The score for a plan is a normalized sum of costs for districts within the plan.

        @keyword district: A L{District} whose cost ratio should be calculated

        @keyword plan: A L{Plan} whose total cost ratio should be calculated

        @keyword version: Optional. The version of the plan, defaults to
        the most recent version.

        @keyword host: Optional. The host to connect to redis, defaults to value in settings.

        @keyword port: Optional. The port to connect to redis, defaults to value in settings.

        @keyword redis_db: Optional. The redis database number to connect to, defaults to value in settings.
        """
        # Get Redis Connection - might as well re-use it
        redis_host = kwargs.get('host', redis_settings['HOST'])
        redis_port = int(kwargs.get('port', redis_settings['PORT']))
        redis_db = int(kwargs.get('db', redis_settings['DB']))
        self.cache = caches['calculations']

        districts = []
        if 'district' in kwargs:
            districts = [kwargs['district']]
            if districts[0].geom.empty:
                return

        elif 'plan' in kwargs:
            plan = kwargs['plan']
            version = kwargs[
                'version'] if 'version' in kwargs else plan.version
            districts = plan.get_districts_at_version(version)

        score = 0

        if len(districts) == 1:
            score = 0 if districts[
                0].district_id == 0 else self._district_calculator(
                    districts[0])

        elif len(districts) > 1:
            district_scores = []
            for district in districts:
                if district.district_id == 0:
                    continue
                district_score = self._district_calculator(district)
                district_scores.append(district_score)

            region = districts[0].plan.legislative_body.region.name

            region_key = key_gen(**{'region': region})
            region_score = float(self.cache.get(region_key))
            num_districts = len(district_scores)

            for district in district_scores:
                numerator = (district - region_score / num_districts)**2
                denominator = (region_score / num_districts)**2
                score += numerator / denominator

        self.result = {'value': score}

    def html(self):
        """
        Generates an HTML representation of adjacency scores. This is represented as a decimal
        number.

        @return: A number formatted similar to "10.01"
        """
        if not self.result is None and 'value' in self.result:
            t = Template('{{ result_value|floatformat:2 }}')
            c = Context({'result_value': self.result['value']})
            return t.render(c)
        else:
            return _('n/a')
