"""
Migrate a database from pre-svn-rev-925.

This management command will update the way 'Unassigned' districts are 
stored in the database.

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
    Andrew Jennings, David Zwarg, Kenny Shepard
"""

from decimal import Decimal
from django.contrib.gis.geos import *
from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
from redistricting.models import *
from datetime import datetime

class Command(BaseCommand):
    """
    Migrate a database to new structure.
    """
    args = ''
    help = 'Migrates a database from r924- to r925+.'

    def handle(self, *args, **options):
        """
        Perform the command. 
        """

        vrb = int(options.get('verbosity'))

        if vrb > 1:
            print "Updating 'Unassigned' districts."

        # First, update the indexes of all the Unassigned districts.
        District.objects.filter(name='Unassigned').update(district_id=0)

        if vrb > 1:
            print "Updating all numbered districts."

        # Second, update the indexes of all the remaining districts.
        District.objects.filter(name__ne='Unassigned').update(district_id=F('district_id')-1)

        if vrb > 1:
            print "Getting the geometry of everything unioned together."

        # Third, create big geometries for all plans that are blank.
        body = LegislativeBody.objects.all()[0]
        geolevel = body.get_geolevels()[0]

        units = Geounit.objects.filter(geolevel=geolevel)
        allgeom = units.unionagg()
        if allgeom.geom_type == 'MultiPolygon':
            pass
        elif allgeom.geom_type == 'Polygon':
            allgeom = MultiPolygon([allgeom], srid=allgeom.srid)

        if vrb > 1:
            print "Getting all plans with only 1 district (Blank plans)."

        # Fourth, set the geometry of all the 'blank' plans to allgeom
        blanks = Plan.objects.filter(name='Blank')
        for blank in blanks:
            if blank.district_set.count() == 1:
                if vrb > 1:
                    print '\tFound Blank plan:', blank.id
                unassigned = blank.district_set.all()[0]
                unassigned.geom = allgeom
                unassigned.simplify() # implicit save

                # Remove any previously computed stats for the unassigned
                # district
                unassigned.computedcharacteristic_set.all().delete()

                # Add the characteristics together for this new geom
                unassigned.delta_stats(units,True)

        if vrb > 1:
            print "Getting all plans with no Unassigned areas (templates, valid)."

        # Fifth, get the plans that have an empty Unassigned district
        allassigned = Plan.objects.filter(Q(is_template=True) | Q(is_valid=True), ~Q(name='Blank'))
        
        for assigned in allassigned:
            districts = assigned.get_districts_at_version(assigned.version, include_geom=False)
            unassigned = filter(lambda x:x.long_label=='Unassigned',districts)[0]
            if vrb > 1:
                print '\tCreating an empty unassigned district:', unassigned.id
            unassigned.geom = MultiPolygon([],srid=allgeom.srid)
            unassigned.simplify() # implicit save

            unassigned.reset_stats()

        if vrb > 1:
            print "Getting 'Unassigned' districts in all plans that are not valid."

        # Sixth, get the unassigned districts in all remaining plans.
        remaining = Plan.objects.filter(Q(is_template=False), Q(is_valid=False))
        for plan in remaining:
            for version in range(plan.min_version, plan.version + 1):
                districts = plan.get_districts_at_version(version, include_geom=True)
                if vrb > 1:
                    print "Updating plan '%s', v%d - %d districts" % (plan.name, version, len(districts))

                bigpoly = None
                unassigned_district = None
                for district in districts:
                    if district.long_label == 'Unassigned':
                        unassigned_district = district
                        continue

                    if district.geom is None:
                        continue

                    if bigpoly:
                        if district.geom.geom_type == 'MultiPolygon':
                            for poly in district.geom:
                                bigpoly.append(poly)
                        else:
                            bigpoly.append(district.geom)
                    else:
                        if district.geom.geom_type == 'MultiPolygon':
                            bigpoly = district.geom
                        else:
                            bigpoly = MultiPolygon([district.geom], srid=district.geom.srid)
                if not bigpoly is None:
                    wholeplan = bigpoly.cascaded_union
                else:
                    wholeplan = MultiPolygon([], srid=allgeom.srid)
                unassigned = allgeom.difference(wholeplan)
                
                smallunits = plan.get_base_geounits_in_geom(unassigned, 100)

                if len(smallunits) == 0:
                    if vrb > 1:
                        print '\tCreating empty Unassigned district'

                    unassigned_district.geom = MultiPolygon([], srid=allgeom.srid)
                    unassigned_district.simplify() # implicit save

                    unassigned_district.reset_stats()
                else:
                    if vrb > 1:
                        print '\tCreating Unassigned district, and computing stats.'

                    unassigned_district.geom = unassigned
                    unassigned_district.simplify() # implicit save

                    smallunits = filter(lambda x:x[0], smallunits)
                    unassigned_district.delta_stats(smallunits, True)
