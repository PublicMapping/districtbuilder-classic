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

class Schwartzberg:
    """
    Calculator for the Schwartzberg measure of compactness.
        
    The Schwartzberg measure of compactness measures the perimeter of 
    the district to the circumference of the circle whose area is 
    equal to the area of the district.

    Parameters:
        district -- The District for which compactness is to be calculated.
    """

    def __init__(self, district):
        self.district = district
        if not district:
            raise ValidationError("No district has been supplied.")

    def calculate(self):
        """
        Calculates the Schwartzberg measure of compactness.

        Returns:
            The Schwartzberg measure as a raw number.
        """
        if not self.district.geom:
            return None
        
        r = sqrt(self.district.geom.area / pi)
        perimeter = 2 * pi * r
        ratio = perimeter / self.district.geom.length
        return ratio
