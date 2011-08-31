#!/usr/bin/env python
# Framework for loading census data
# Inputs: FIPS state code, list of variables to include as additional subjects
# Requirements:
#       - external software: DistrictBuilder, R, gdal, wget, unzip
# TODO -- check for VTD's


import re       # regular expressions
import sys      # arg lists etc
import glob     # globbing
import commands # system commands
import os       # os commands
import stat
import subprocess # for external commands
import zipfile # unzipping
import rpy2.robjects as robjects
import shutil
import psycopg2 as dbapi2
import optparse
import string
import time


### 
### Globals
###

PUBLICMAPPINGPASS="publicmapping"
# TODO : build in vote geographies, numbers of districts per state
#VOTEGEOGRAPHIES={"county":"COUNTYFP10","tract":"TRACTCE10","block":"BLOCKCE10"}


### clear_publicmapping_db
###
###     Truncate database

def     clear_publicmapping_db():
        db = dbapi2.connect (database="publicmapping", user="publicmapping", password=PUBLICMAPPINGPASS)
        cur = db.cursor()
        redtable=["redistricting_characteristic","redistricting_computedcharacteristic","redistricting_computeddistrictscore","redistricting_computedplanscore","redistricting_contiguityoverride","redistricting_district","redistricting_geolevel","redistricting_geounit","redistricting_legislativebody","redistricting_legislativedefault","redistricting_legislativelevel","redistricting_plan","redistricting_profile","redistricting_scoreargument","redistricting_scoredisplay","redistricting_scorefunction","redistricting_scorepanel","redistricting_scorepanel_displays","redistricting_scorepanel_score_functions","redistricting_subject","redistricting_target","redistricting_validationcriteria"]
        for i in redtable:
                cur.execute("truncate table %s CASCADE" % i)
        db.commit()
        db.close()

### Drop DB

def     drop_db():
        olddir = os.getcwd()
        os.chdir("/tmp")
        subprocess.check_call(["service","tomcat6","stop"])
        subprocess.check_call(["service","celeryd","stop"])
        subprocess.check_call(["service","apache2","stop"])
        subprocess.check_call(["service","apache2","restart"])
        subprocess.check_call(["service","postgresql","restart"])
        subprocess.check_call(['su postgres -c "dropdb publicmapping"'],shell=True)
        subprocess.check_call(['cat /projects/PublicMapping/DistrictBuilder/sql/publicmapping_db.sql | su postgres -c "psql -f - postgres"'],shell=True)
        subprocess.check_call(["service","apache2","start"])
        subprocess.check_call(["service","tomcat6","start"])

        os.chdir(olddir)


### Install dependencies
###
### This attempts to install dependencies using apt-get
###

def     install_dependencies():
        if (os.path.exists("/usr/bin/ogrinfo")==False) :
        	cmdarg = 'gdal-bin'
        	subprocess.check_call(["apt-get","install",cmdarg])

###
### Retrieve data files
###
### This retrieves the census files,unzips and reprojects (using ogr2ogr) 

def     get_census_data(stateFips): 
	if (stateFips<10) :
		stateFips = "0%s" % stateFips
        print 'Retrieving census shapefiles...'
        # put all data in publicmapping data directory
        olddir = os.getcwd()
        os.chdir("/projects/PublicMapping/data/")
        # obtain state boundary files from census
        cenBlockFilePrefix = 'tl_2010_%s_tabblock10' % stateFips
        cenTractFilePrefix = 'tl_2010_%s_tract10' % stateFips
        cenCountyFilePrefix= 'tl_2010_%s_county10' % stateFips
        cmdarg = 'ftp://ftp2.census.gov/geo/tiger/TIGER2010/TABBLOCK/2010/%s.zip' % cenBlockFilePrefix 
        subprocess.check_call(["wget","-nc",cmdarg])
        cmdarg = 'ftp://ftp2.census.gov/geo/tiger/TIGER2010/TRACT/2010/%s.zip' % cenTractFilePrefix
        subprocess.check_call(["wget","-N",cmdarg])
        cmdarg = 'ftp://ftp2.census.gov/geo/tiger/TIGER2010/COUNTY/2010/%s.zip' % cenCountyFilePrefix
        subprocess.check_call(["wget","-N",cmdarg])
        # get additional data from our S3 bucket
        print 'Retrieving additional data...'
        cmdarg = 'https://s3.amazonaws.com/redistricting_supplement_data/redist/%s_redist_data.zip' % stateFips
        subprocess.check_call(["wget","-N",cmdarg])
        cmdarg = 'https://s3.amazonaws.com/redistricting_supplement_data/redist/%s_contiguity_overrides.csv' % stateFips
        subprocess.call(["wget","-N",cmdarg])
        print 'Unzipping files ...'
        # unzip data files
        for i in [ cenBlockFilePrefix, cenTractFilePrefix, cenCountyFilePrefix ] :
	    	zfile = '%s.zip' % i 
		print ('Unzipping %s' %zfile)
                myzip = zipfile.ZipFile(zfile, 'r')
                myzip.extractall()
        myzip = zipfile.ZipFile('%s_redist_data.zip' % stateFips, 'r')
        myzip.extractall()        # Reproject block data
        print 'Reprojecting block shapefile...'
        if (os.path.exists("census_blocks.shp")) :
                os.remove('census_blocks.shp')
        if (os.path.exists("census_tracts.shp")) :
                os.remove('census_tracts.shp')
        if (os.path.exists("census_counties.shp")) :
                os.remove('census_counties.shp')
        subprocess.check_call(["ogr2ogr",'-overwrite','-t_srs','EPSG:3785','census_blocks.shp','%s.shp' % cenBlockFilePrefix ])
        subprocess.check_call(["ogr2ogr",'-overwrite','-t_srs','EPSG:3785','census_tracts.shp','%s.shp' % cenTractFilePrefix])
        subprocess.check_call(["ogr2ogr",'-overwrite','-t_srs','EPSG:3785','census_counties.shp','%s.shp' % cenCountyFilePrefix])
        # standardize file names
        print 'Copying data files...'
        shutil.copy('%s_redist_data.csv' %stateFips , 'redist_data.csv' )
        if (os.path.exists("redist_overrides.csv")) :
        	os.remove('redist_overrides.csv')
        if (os.path.exists("%s_contiguity_overrides.csv" % stateFips)) :
        	shutil.copy("%s_contiguity_overrides.csv" % stateFips,'redist_overrides.csv') 
        os.chdir(olddir)



###
### TEMPLATING  - SLD's
###

# general template classes
class DictionaryTemplate:
    def __init__(self, dict={}, **keywords):
        self.dict = dict
        self.dict.update(keywords)
    def __str__(self):
        return self._template % self
    def __getitem__(self, key):
            return self._process(key.split("|"))
    def _process(self, l):
        arg = l[0]
        if len(l) == 1:
            if arg in self.dict:
                return self.dict[arg]
            elif hasattr(self, arg) and callable(getattr(self, arg)):
                return getattr(self, arg)()
            else:
                raise KeyError(arg)
        else:
            func_name = l[1]
            if func_name in self.dict:
                func = self.dict[func_name]
            else:
                func = getattr(self, func_name)
            return func(self._process([arg]))

class ListTemplate:
    def __init__(self, input_list=[]):
        self.input_list = input_list
    def __str__(self):
        return "\n".join([self._template % x for x in self.input_list])

class Empty_Template(ListTemplate):
    _template = """        
	"""

###
### SLD Skeleton Classes
###

class SldList_Template(DictionaryTemplate):
    _template = """<?xml version="1.0" encoding="ISO-8859-1"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>%(layername)s</Name>
    <UserStyle>
      <Title>%(layertitle)s</Title>
      <Abstract>%(layerabs)s</Abstract>
      <FeatureTypeStyle>
        %(slst|sli)s
        %(lst|li)s
        %(elst|eli)s
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
      """

class Sld_Poly_Template(ListTemplate):
    _template = """
        <Rule>
          <Title>%(title)s</Title>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">%(fill)s</CssParameter>
              <CssParameter name="fill-opacity">%(fillopacity)s</CssParameter>            
	    </Fill>
          </PolygonSymbolizer>
        </Rule>
        """


class Sld_PolyB_Template(ListTemplate):
    _template = """
        <Rule>
          <Title>%(title)s</Title>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">%(fill)s</CssParameter>
              <CssParameter name="fill-opacity">%(fillopacity)s</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">%(stroke)s</CssParameter>
              <CssParameter name="stroke-width">%(strokewidth)s</CssParameter>
              <CssParameter name="stroke-opacity">%(strokeopacity)s</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
        """

# plain fill template
class Sld_Line_Template(ListTemplate):
    _template = """
        <Rule>
          <Title>%(title)s</Title>
          <LineSymbolizer>
            <Stroke>
              <CssParameter name="stroke">%(stroke)s</CssParameter>
              <CssParameter name="stroke-width">%(strokewidth)s</CssParameter>
              <CssParameter name="stroke-opacity">%(strokeopacity)s</CssParameter>
            </Stroke>
          </LineSymbolizer>
        </Rule>
        """

# min-max range template
class Sld_Range_Template(ListTemplate):
    _template = """
        <Rule>
          <Title>%(bottom)s-%(top)s</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>%(unit)s</ogc:PropertyName>
                <ogc:Literal>%(top)s</ogc:Literal>
              </ogc:PropertyIsLessThan>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>%(unit)s</ogc:PropertyName>
                <ogc:Literal>%(bottom)s</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">%(fill)s</CssParameter>
              <CssParameter name="fill-opacity">%(fillopacity)s</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        """


class Sld_URange_Template(ListTemplate):
    _template = """
        <Rule>
          <Title>%(bottom)s-%(top)s</Title>
          <ogc:Filter>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>%(unit)s</ogc:PropertyName>
                <ogc:Literal>%(bottom)s</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">%(fill)s</CssParameter>
              <CssParameter name="fill-opacity">%(fillopacity)s</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        """

def gensld_none(geoname):
        target_file = '/projects/PublicMapping/DistrictBuilder/sld/pmp:%s_none.sld' % (geoname)       
        f = open(target_file,'w')
        f.write ( str(SldList_Template(layername="%s No fill" % (geoname),layertitle="%s No Fill" % (geoname) ,layerabs="A style showing the boundaries of a geounit with a transparent fill", slst=[],sli=Empty_Template, lst=[{"title":"Fill","fill":"#FFFFFF","fillopacity":"1.0"}],li=Sld_Poly_Template,elst=[{"title":"Boundary","stroke":"#555555","strokewidth":"3.00","strokeopacity":"1.0"}],eli=Sld_Line_Template)) )
	f.write("\n")
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)    

def gensld_boundaries(geoname):
        target_file = '/projects/PublicMapping/DistrictBuilder/sld/pmp:%s_boundaries.sld' % (geoname) 
        f = open(target_file,'w')
        f.write ( str(SldList_Template(layername="%s Boundaries" % (geoname) ,layertitle="%s Boundaries Only" %(geoname),layerabs="A style showing the boundaries of a geounit", slst=[] ,sli=Empty_Template, lst=[],li=Empty_Template,elst=[{"title":"County Boundaries","fill":"#000000","fillopacity":"0.0","stroke":"#2255FF","strokewidth":"2","strokeopacity":"0.35"}],eli=Sld_PolyB_Template)))
	f.write("\n")
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)  

#TODO: generalize to any number of choropleths
def gensld_choro(geoname,varname,vartitle,quantiles):
	gensld_choro_internal(geoname,varname,vartitle,quantiles,unit="number")

def gensld_choro_internal(geoname,varname,vartitle,quantiles,unit="number"):
	# WARNING: sld files need to be lower case to be compatible with postgres views
	lvarname = string.lower(varname)
        target_file = '/projects/PublicMapping/DistrictBuilder/sld/pmp:%s_%s.sld' % (geoname,lvarname) 
        varabs="Grayscale choropleth based on quantiles of %s" % (varname)
        valuelist= [
          {"top": str(quantiles[4]),
          "bottom": str(quantiles[3]),
          "fill": "#444444",
          "fillopacity":"1.0",
  	   "unit":unit},
          {"top": str(quantiles[3]),
          "bottom": str(quantiles[2]),
          "fill": "#777777",
          "fillopacity":"1.0",
           "unit":unit},
          {"top": str(quantiles[2]),
          "bottom": str(quantiles[1]),
          "fill": "#AAAAAA",
          "fillopacity":"1.0",
	  "unit":unit},
          {"top": str(quantiles[1]),
          "bottom": str(quantiles[0]),
          "fill": "#EEEEEE",
          "fillopacity":"1.0",
	  "unit":unit}]

   	svaluelist = [{"top": str(quantiles[5]),
          "bottom": str(quantiles[4]),
          "fill": "#000000",
          "fillopacity":"1.0",
	  "unit":unit}]

        f = open(target_file,'w')
        f.write(str( SldList_Template(layername=lvarname,layertitle=vartitle,layerabs=varabs,slst=svaluelist,sli=Sld_URange_Template, lst=valuelist,li=Sld_Range_Template,elst=[{"title":"Boundary","stroke":"#555555","strokewidth":"0.25","strokeopacity":"1.0"}],eli=Sld_Line_Template) ))
	f.write("\n")
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)  


def gensld_choro_denquint(geoname,varname,vartitle,dummy):
	quantiles=[0,0.2,0.4,0.6,0.8,1]
	gensld_choro_internal(geoname,varname,vartitle,quantiles,unit="percentage")


### Config file generation
### TODO: has_vtds==1 has not fully implemented 
###        paramaterize thresholds?

class Config_Template(DictionaryTemplate):
    _template = """<!-- Define Internal Entities to avoid Repeated Entering of Values -->
<!DOCTYPE DistrictBuilder [
    <!ENTITY num_districts_congress "%(num_districts_congress)s">
    <!ENTITY num_districts_house "%(num_districts_house)s">
    <!ENTITY num_districts_senate "%(num_districts_senate)s">
    <!ENTITY pop_congress "%(pop_congress)s">
    <!ENTITY pop_house "%(pop_house)s">
    <!ENTITY pop_senate "%(pop_senate)s">
    <!ENTITY pop_congress_min "%(pop_congress_min)s">
    <!ENTITY pop_house_min "%(pop_house_min)s">
    <!ENTITY pop_senate_min "%(pop_senate_min)s">
    <!ENTITY pop_congress_max "%(pop_congress_max)s">
    <!ENTITY pop_house_max "%(pop_house_max)s">
    <!ENTITY pop_senate_max "%(pop_senate_max)s">
    <!ENTITY target_hisp_congress "%(target_hisp_congress)s">
    <!ENTITY target_hisp_senate "%(target_hisp_senate)s">
    <!ENTITY target_hisp_house "%(target_hisp_house)s">
    <!ENTITY target_bl_congress "%(target_bl_congress)s">
    <!ENTITY target_bl_senate "%(target_bl_senate)s">
    <!ENTITY target_bl_house "%(target_bl_house)s">
    <!ENTITY target_na_senate "%(target_na_senate)s">
    <!ENTITY target_na_house "%(target_na_house)s">
    <!ENTITY target_na_congress "%(target_na_congress)s">
 ]>

<DistrictBuilder>


    <!-- Define legislative bodies referenced in the system. -->
    <LegislativeBodies>
        <!-- A Legislative body has an ID (for referencing in GeoLevel
            definitions later), a name, and a label for plan items 
            ("District" for Congressional, etc) -->
        <LegislativeBody id="congress" name="Congressional" member="District %%s" maxdistricts="&num_districts_congress;"/>
        <LegislativeBody id="house" name="State House" member="District %%s" maxdistricts="&num_districts_house;" />
        <LegislativeBody id="senate" name="State Senate" member="District %%s" maxdistricts="&num_districts_senate;" />
    </LegislativeBodies>
    <!-- A list of subjects referenced in the system. -->
    <Subjects>       
	 <!-- A Subject is a measurement type, such as "Total Population".            
	 The subject is mapped to an attribute during the import phase,
            and contains a long and short display name. Subjects have IDs
            for referencing in GeoLevel definitions later. -->
        <Subject id="vap_b" field="VAP_B" name="African-American Voting Age Population" short_name="Black VAP " displayed="true" sortkey="1" percentage_denominator="vap" />
        <Subject id="vap_h" field="VAP_H" name="Hispanic or Latino voting age population" short_name="Hispanic VAP" displayed="true" sortkey="2" percentage_denominator="vap" />
        <Subject id="vap_na" field="VAP_NA" name="Native American Voting Age Population" short_name="Nat Amer VAP" displayed="true" sortkey="4" percentage_denominator="vap" />
        %(start_elec)s
        <Subject id="vote_dem" field="VOTE_DEM" name="num likely Democratic voters" short_name="Democratic voters" displayed="true" sortkey="3" percentage_denominator="vote_tot" />
        <Subject id="vote_rep" field="VOTE_REP" name="num likely Republican voters" short_name="Republican voters" displayed="true" sortkey="5" percentage_denominator="vote_tot" />
        <Subject id="vote_tot" field="VOTE_TOT" name="num likely Rep/Dem voters" short_name="Rep+ Dem vote" displayed="false" sortkey="6" />
        <Subject id="vote_dem_norm" field="VOTE_DEM_N" name="num of likely Democratic voters normalized to 50/50 state baseline" short_name="Normal Dem vote" displayed="true" sortkey="18" percentage_denominator="vote_tot_norm" />
        <Subject id="vote_rep_norm" field="VOTE_REP_N" name="num of likely Republican voters normalized to 50/50 state baseline" short_name="Normal Rep vote" displayed="true" sortkey="19" percentage_denominator="vote_tot_norm" />
        <Subject id="vote_tot_norm" field="VOTE_TOT_N" name="number of likely Republican and Democratic voters normalized to 50/50 state baseline" short_name="Normal 2-party vote" displayed="false" sortkey="20" />
        %(end_elec)s
        <Subject id="vap" field="VAP" name="Voting Age Population" short_name="vap" displayed="true" sortkey="7" />
        <Subject id="totpop_b" field="TOTPOP_B" name="African-American" short_name="Black" displayed="false" sortkey="8" percentage_denominator="totpop"/>        
	<Subject id="totpop_h" field="TOTPOP_H" name="Hispanic or Latino" short_name="Hispanic" displayed="false" sortkey="9" percentage_denominator="totpop"/>
	<Subject id="totpop_na" field="TOTPOP_NA" name="Native American" short_name="Nat Amer" displayed="false" sortkey="10" percentage_denominator="totpop"/>
	<Subject id="totpop_a" field="TOTPOP_A" name="Asian Population" short_name="Asian" displayed="false" sortkey="11" percentage_denominator="totpop"/>
	<Subject id="totpop_pi" field="TOTPOP_PI" name="Pacific Islander" short_name="Pac Isl" displayed="false" sortkey="12" percentage_denominator="totpop"/>
	<Subject id="totpop_wnh" field="TOTPOP_WNH" name="White Non-Hispanic" short_name="White" displayed="false" sortkey="13" percentage_denominator="totpop"/>
        <Subject id="totpop" field="TOTPOP" name="Total Population" short_name="Total Pop." displayed="true" sortkey="14"/>
        <Subject id="vap_a" field="VAP_A" name="Asian Voting Age Population" short_name="Asian VAP" displayed="true" sortkey="15" percentage_denominator="vap" />
        <Subject id="vap_pi" field="VAP_PI" name="Pacific Islander Voting Age Population" short_name="Pacific VAP" displayed="true" sortkey="16" percentage_denominator="vap"/>
        <Subject id="vap_wnh" field="VAP_WNH" name="White Non-Hispanic Voting Age Population" short_name="White VAP" displayed="true" sortkey="17" percentage_denominator="vap"/>
   </Subjects>

    <Scoring>
        <ScoreFunctions>
            <!-- A district score that returns a literal value -->
            <ScoreFunction id="district_poptot" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Total Pop" user_selectable="true">
                <SubjectArgument name="value1" ref="totpop" />
            </ScoreFunction>
            <ScoreFunction id="district_totpop_b" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Black VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="totpop_b" />
            </ScoreFunction>
            <ScoreFunction id="district_totpop_h" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Hispanic VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="totpop_h" />
            </ScoreFunction>
            <ScoreFunction id="district_totpop_a" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Asian VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="totpop_a" />
            </ScoreFunction>
            <ScoreFunction id="district_totpop_na" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Native American VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="totpop_na" />
            </ScoreFunction>
            <ScoreFunction id="district_totpop_pi" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Pacific Islander VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="totpop_pi" />
            </ScoreFunction>
            <ScoreFunction id="district_totpop_wnh" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Pacific Islander VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="totpop_wnh" />
            </ScoreFunction>
            <ScoreFunction id="district_vap" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="vap" />
            </ScoreFunction>
            <ScoreFunction id="district_vap_b" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Black VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="vap_b" />
            </ScoreFunction>
            <ScoreFunction id="district_vap_h" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Hispanic VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="vap_h" />
            </ScoreFunction>
            <ScoreFunction id="district_vap_a" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Asian VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="vap_a" />
            </ScoreFunction>
            <ScoreFunction id="district_vap_na" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Native American VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="vap_na" />
            </ScoreFunction>
            <ScoreFunction id="district_vap_pi" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Pacific Islander VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="vap_pi" />
            </ScoreFunction>
            <ScoreFunction id="district_vap_wnh" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Pacific Islander VAP" user_selectable="true">
                <SubjectArgument name="value1" ref="vap_wnh" />
            </ScoreFunction>

            <!-- A district score that returns a percentage -->
            <ScoreFunction id="district_blkvap_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="Black VAP %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vap_b" />
                <SubjectArgument name="denominator" ref="vap" />
            </ScoreFunction>
            <ScoreFunction id="district_blkvap_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Black VAP Threshold">
                <ScoreArgument name="value" ref="district_blkvap_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
            <ScoreFunction id="district_hispvap_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="Hisp. VAP %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vap_h" />
                <SubjectArgument name="denominator" ref="vap" />
            </ScoreFunction>
            <ScoreFunction id="district_hispvap_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Hisp. VAP Threshold">
                <ScoreArgument name="value" ref="district_hispvap_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
            <ScoreFunction id="district_navap_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="Native American VAP %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vap_na" />
                <SubjectArgument name="denominator" ref="vap" />
            </ScoreFunction>
            <ScoreFunction id="district_navap_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Native American VAP Threshold">
                <ScoreArgument name="value" ref="district_navap_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
            <ScoreFunction id="district_avap_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="Asian VAP %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vap_a" />
                <SubjectArgument name="denominator" ref="vap" />
            </ScoreFunction>
            <ScoreFunction id="district_avap_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Asian VAP Threshold">
                <ScoreArgument name="value" ref="district_avap_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
            <ScoreFunction id="district_pivap_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="Pacific Islander VAP %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vap_pi" />
                <SubjectArgument name="denominator" ref="vap" />
            </ScoreFunction>
            <ScoreFunction id="district_pivap_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Pacific Islander VAP Threshold">
                <ScoreArgument name="value" ref="district_pivap_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
            <ScoreFunction id="district_wnhvap_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="White VAP %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vap_wnh" />
                <SubjectArgument name="denominator" ref="vap" />
            </ScoreFunction>
            <ScoreFunction id="district_wnhvap_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="White VAP Threshold">
                <ScoreArgument name="value" ref="district_wnhvap_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
                %(start_elec)s
            <ScoreFunction id="district_vote" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Estimated votes" user_selectable="true">
                <SubjectArgument name="value1" ref="vote_tot" />
            </ScoreFunction>
            <ScoreFunction id="district_vote_dem" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Estimated Democratic votes" user_selectable="true">
                <SubjectArgument name="value1" ref="vote_dem" />
            </ScoreFunction>
            <ScoreFunction id="district_vote_rep" type="district"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Estimated votes" user_selectable="true">
                <SubjectArgument name="value1" ref="vote_rep" />
            </ScoreFunction>
            <ScoreFunction id="district_vote_dem_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="Democratic Predicted Vote %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vote_dem" />
                <SubjectArgument name="denominator" ref="vote_tot" />
            </ScoreFunction>
            <ScoreFunction id="district_vote_dem_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Democratic Predicted Vote Threshold">
                <ScoreArgument name="value" ref="district_vote_dem_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
            <ScoreFunction id="district_vote_rep_percent" type="district"
                calculator="publicmapping.redistricting.calculators.Percent"
                label="Republican Predicted Vote %%" user_selectable="true">
                <SubjectArgument name="numerator" ref="vote_rep" />
                <SubjectArgument name="denominator" ref="vote_tot" />
            </ScoreFunction>
            <ScoreFunction id="district_vote_rep_thresh" type="district"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Republican Predicted Vote Threshold">
                <ScoreArgument name="value" ref="district_vote_rep_percent" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>
                %(end_elec)s

            <!-- A district score that generates classes based on a couple
                ranges around a mean value. -->
            <ScoreFunction id="district_poptot_uitarget_congress" type="district" 
                calculator="publicmapping.redistricting.calculators.Target">
                <SubjectArgument name="value" ref="totpop" />
                <Argument name="target" value="&pop_congress;" />
                <Argument name="range1" value="0.005"/>
                <Argument name="range2" value="0.010"/>
            </ScoreFunction>
            <ScoreFunction id="district_poptot_uitarget_house" type="district"
                calculator="publicmapping.redistricting.calculators.Target">
                <SubjectArgument name="value" ref="totpop" />
                <Argument name="target" value="%(pop_house)s" />
                <Argument name="range1" value="0.05" />
                <Argument name="range2" value="0.10" />
            </ScoreFunction>
            <ScoreFunction id="district_poptot_uitarget_senate" type="district"
                calculator="publicmapping.redistricting.calculators.Target">
                <SubjectArgument name="value" ref="totpop" />
                <Argument name="target" value="%(pop_senate)s" />
                <Argument name="range1" value="0.05" />
                <Argument name="range2" value="0.10" />
            </ScoreFunction>

            <!-- A district score that returns 1(T) if the subject value
                is between the ranges, otherwise returns 0(F). -->
            <ScoreFunction id="district_poptot_range" type="district"
                calculator="publicmapping.redistricting.calculators.Range"
                label="Tot Pop Range">
                <SubjectArgument name="value" ref="totpop" />
                <Argument name="min" value="&pop_congress_min;" />
                <Argument name="max" value="&pop_congress_max;" />
            </ScoreFunction>

            <!-- A district score that is threshold dependent, and returns 
                T/F; this example uses 2 score functions: 1 to combine a 
                set of subjects, and 2 to divide the sum over another 
                subject. -->
            <ScoreFunction id="district_mintot" type="district"
                calculator="publicmapping.redistricting.calculators.Sum">
                <SubjectArgument name="value1" ref="totpop_b" />
                <SubjectArgument name="value2" ref="totpop_h" />
                <SubjectArgument name="value3" ref="totpop_na" />
            </ScoreFunction>
            <ScoreFunction id="district_majmin" type="district"
                calculator="publicmapping.redistricting.calculators.DivideAndThreshold" >
                <ScoreArgument name="numerator" ref="district_mintot" />
                <SubjectArgument name="denominator" ref="totpop" />
                <Argument name="threshold" value="0.5" />
            </ScoreFunction>

            <!-- A custom calculator to calculate compactness, and return
                the raw compactness score. -->
            <ScoreFunction id="district_schwartzberg" type="district"
                calculator="publicmapping.redistricting.calculators.Schwartzberg"
                label="Compactness" user_selectable="true">
            </ScoreFunction>
            
            <!-- A custom calculator to do contiguity, and is boolean. -->
            <ScoreFunction id="district_contiguous" type="district"
                calculator="publicmapping.redistricting.calculators.Contiguity"
                label="Contiguous" user_selectable="true">
            </ScoreFunction>

            <!-- A plan score that aggregates all literal values -->
            <ScoreFunction id="plan_sum_equipop" type="plan" 
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Equal Population">
                <ScoreArgument name="value1" ref="district_poptot_range" />
            </ScoreFunction>
            <ScoreFunction id="plan_all_equipop" type="plan" 
                calculator="publicmapping.redistricting.calculators.Threshold" >
                <ScoreArgument name="value" ref="plan_sum_equipop" />
                <Argument name="threshold" value="0" />
            </ScoreFunction>

            <!-- A plan score that aggregates all districts over a threshold -->
            <ScoreFunction id="plan_count_majmin" type="plan" 
                calculator="publicmapping.redistricting.calculators.Sum">
                <ScoreArgument name="value1" ref="district_majmin" />
            </ScoreFunction>

            <ScoreFunction id="plan_blkvap_thresh" type="plan"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Majority Black Districts" user_selectable="true">
                <ScoreArgument name="value1" ref="district_blkvap_thresh" />
            </ScoreFunction>

            <ScoreFunction id="plan_hispvap_thresh" type="plan"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Majority Hispanic Districts" user_selectable="true">
                <ScoreArgument name="value1" ref="district_hispvap_thresh" />
            </ScoreFunction>

            <ScoreFunction id="plan_navap_thresh" type="plan"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Majority Asian Districts" user_selectable="true">
                <ScoreArgument name="value1" ref="district_navap_thresh" />
            </ScoreFunction>

            <ScoreFunction id="plan_avap_thresh" type="plan"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Majority Asian Districts" user_selectable="true">
                <ScoreArgument name="value1" ref="district_avap_thresh" />
            </ScoreFunction>

            <ScoreFunction id="plan_pivap_thresh" type="plan"
                calculator="publicmapping.redistricting.calculators.Sum">
                <ScoreArgument name="value1" ref="district_pivap_thresh" />
            </ScoreFunction>

            <!-- A plan score that evaluates a threshold, and returns T/F.
                This plan score checks that all districts are within the
                population limits. -->
            <ScoreFunction id="plan_poptot_inrange" type="plan" 
                calculator="publicmapping.redistricting.calculators.Threshold">
                <ScoreArgument name="value" ref="district_poptot_range" />
                <Argument name="threshold" value="0" />
            </ScoreFunction>
           
            <!-- A plan score that evaluates all districts, and returns
                1(T) if there is more than 0 districts that have a minority
                majority. -->
            <ScoreFunction id="plan_major_minor" type="plan"
                calculator="publicmapping.redistricting.calculators.Threshold"
                label="Majority-Minority">
                <ScoreArgument name="value" ref="district_majmin" />
                <Argument name="threshold" value="0" />
            </ScoreFunction>

          <ScoreFunction id="plan_contiguous" type="plan"
                calculator="publicmapping.redistricting.calculators.Sum"
                label="Contiguous">
                <ScoreArgument name="value1" ref="district_contiguous"/>
            </ScoreFunction>

            <ScoreFunction id="b_plan_congress_noncontiguous" type="plan"
                calculator="publicmapping.redistricting.calculators.Contiguity"
                label="Contiguous">
                <Argument name="target" value="&num_districts_congress;" />
            </ScoreFunction>

            <ScoreFunction id="b_plan_house_noncontiguous" type="plan"
                calculator="publicmapping.redistricting.calculators.Contiguity"
                label="Contiguous">
                <Argument name="target" value="&num_districts_house;" />
            </ScoreFunction>

            <ScoreFunction id="b_plan_senate_noncontiguous" type="plan"
                calculator="publicmapping.redistricting.calculators.Contiguity"
                label="Contiguous">
                <Argument name="target" value="&num_districts_senate;" />
            </ScoreFunction>


            <!-- interval score function for population -->
            <ScoreFunction id="a_congressional_population" type="district"
                label="Tot Pop Range (Congress)" user_selectable="true"
                description="Population interval calculator for congressional."
                calculator="publicmapping.redistricting.calculators.Interval">
                <SubjectArgument name="subject" ref="totpop" />
                <Argument name="target" value="&pop_congress;" />
                <Argument name="bound1" value=".005" />
                <Argument name="bound2" value=".01" />
            </ScoreFunction>

            <ScoreFunction id="a_house_population" type="district"
                label="Tot Pop Range (House)" user_selectable="true"
                description="Population interval calculator for house."
                calculator="publicmapping.redistricting.calculators.Interval">
                <SubjectArgument name="subject" ref="totpop" />
                <Argument name="target" value="%(pop_house)s" />
                <Argument name="bound1" value=".005" />
                <Argument name="bound2" value=".01" />
            </ScoreFunction>

            <ScoreFunction id="a_senate_population" type="district"
                label="Tot Pop Range (Senate)" user_selectable="true"
                description="Population interval calculator for senate."
                calculator="publicmapping.redistricting.calculators.Interval">
                <SubjectArgument name="subject" ref="totpop" />
                <Argument name="target" value="%(pop_senate)s" />
                <Argument name="bound1" value=".005" />
                <Argument name="bound2" value=".01" />
            </ScoreFunction>

            <!-- leaderboard functions -->
            <ScoreFunction id="a_congress_plan_count_districts" type="plan"
                calculator="publicmapping.redistricting.calculators.CountDistricts"
                label="Count Districts"
                description="The number of districts in a Congressional redistricting plan must be &num_districts_congress;.">
                <Argument name="target" value="&num_districts_congress;" />
            </ScoreFunction>

            <ScoreFunction id="a_house_plan_count_districts" type="plan"
                calculator="publicmapping.redistricting.calculators.CountDistricts"
                label="Count Districts"
                description="The number of districts in a House of Delegates redistricting plan must be &num_districts_house;.">
                <Argument name="target" value="&num_districts_house;" />
            </ScoreFunction>

            <ScoreFunction id="a_senate_plan_count_districts" type="plan"
                calculator="publicmapping.redistricting.calculators.CountDistricts"
                label="Count Districts"
                description="The number of districts in a State Senate redistricting plan must be &num_districts_senate;.">
                <Argument name="target" value="&num_districts_senate;" />
            </ScoreFunction>


            <ScoreFunction id="a_congress_plan_equipopulation_validation" type="plan"
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                label="Target Pop. &pop_congress;"
                description="The population of each Congressional district must be &pop_congress_min;-&pop_congress_max;">
                <Argument name="min" value="&pop_congress_min;"/>
                <Argument name="max" value="&pop_congress_max;"/>
                <SubjectArgument name="value" ref="totpop"/>
                <Argument name="validation" value="1"/>
            </ScoreFunction>

            <ScoreFunction id="a_congress_plan_equipopulation_summary" type="plan"
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                label="Target Pop. &pop_congress;"
                description="The population of each Congressional district must be &pop_congress_min;-&pop_congress_max;">
                <Argument name="min" value="&pop_congress_min;"/>
                <Argument name="max" value="&pop_congress_max;"/>
                <SubjectArgument name="value" ref="totpop"/>
		<Argument name="target" value="&num_districts_congress;"/>
            </ScoreFunction>

            <ScoreFunction id="a_senate_plan_equipopulation_validation" type="plan"
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                label="Target Pop. %(pop_senate)s"
                description="The population of each Senate district must be &pop_senate_min;-&pop_senate_max;">
                <Argument name="min" value="&pop_senate_min;"/>
                <Argument name="max" value="&pop_senate_max;"/>
                <SubjectArgument name="value" ref="totpop"/>
                <Argument name="validation" value="1"/>
            </ScoreFunction>

            <ScoreFunction id="a_senate_plan_equipopulation_summary" type="plan"
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                label="Target Pop. %(pop_senate)s"
                description="The population of each Senate district must be &pop_senate_min;-&pop_senate_max;">
                <Argument name="min" value="&pop_senate_min;"/>
                <Argument name="max" value="&pop_senate_max;"/>
                <SubjectArgument name="value" ref="totpop"/>
		<Argument name="target" value="&num_districts_senate;"/>
            </ScoreFunction>

            <ScoreFunction id="a_house_plan_equipopulation_validation" type="plan"
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                label="Target Pop. %(pop_house)s"
                description="The population of each House district must be &pop_house_min;-&pop_house_max;">
                <Argument name="min" value="&pop_house_min;"/>
                <Argument name="max" value="&pop_house_max;"/>
                <SubjectArgument name="value" ref="totpop"/>
                <Argument name="validation" value="1"/>
            </ScoreFunction>

            <ScoreFunction id="a_house_plan_equipopulation_summary" type="plan"
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                label="Target Pop. %(pop_house)s"
                description="The population of each House district must be &pop_house_min;-&pop_house_max;">
                <Argument name="min" value="&pop_house_min;"/>
                <Argument name="max" value="&pop_house_max;"/>
                <SubjectArgument name="value" ref="totpop"/>
		<Argument name="target" value="&num_districts_house;"/>
            </ScoreFunction>

            <ScoreFunction id="plan_all_blocks_assigned" type="plan"
                calculator="publicmapping.redistricting.calculators.AllBlocksAssigned"
                label="All Blocks Assigned"
                description="All blocks in the plan must be assigned.">
            </ScoreFunction>


            <ScoreFunction id="plan_all_contiguous" type="plan"
                calculator="publicmapping.redistricting.calculators.AllContiguous"
                label="All Contiguous"
                description="Contiguity means that every part of a district must be reachable from every other part without crossing the district&apos;s borders. All districts within a plan must be contiguous. Water contiguity is permitted. &apos;Point contiguity&apos; or &apos;touch-point contiguity&apos; where two sections of a district are connected at a single point is not permitted.">
            </ScoreFunction>
                %(start_elec)s
            <ScoreFunction id="plan_competitiveness" type="plan"
                calculator="publicmapping.redistricting.calculators.Competitiveness"
                label="Competitiveness"
                description="Each plan&apos;s overall political competitiveness is determined by averaging each district.s &apos;partisan differential&apos;.  The partisan differential of each district is calculated by subtracting the Democratic &apos;partisan index&apos; from the Republican &apos;partisan index&apos;.&lt;br/&gt;&lt;br/&gt;&apos;Heavily&apos; competitive districts are districts with partisan differentials of less than or equal to 5%%. &apos;Generally&apos; competitive districts are districts with partisan differentials of greater than 5%% but less than 10%%.">
                <SubjectArgument name="democratic" ref="vote_dem" />
                <SubjectArgument name="republican" ref="vote_rep" />
            </ScoreFunction>
                %(end_elec)s

            <ScoreFunction id="plan_equivalence" type="plan"
                calculator="publicmapping.redistricting.calculators.Equivalence"
                label="Equal Population"
                description="The Equipopulation score is the difference between the district with the highest population and the district with the lowest population.">
                <SubjectArgument name="value" ref="totpop" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_blk_congress" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Black VAP Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_b" />
                <Argument name="target" value="&target_bl_congress;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_blk_house" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Black VAP Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_b" />
                <Argument name="target" value="&target_bl_house;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_blk_senate" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Black VAP Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_b" />
                <Argument name="target" value="&target_bl_senate;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_hisp_congress" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Hisp. VAP Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_h" />
                <Argument name="target" value="&target_hisp_congress;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_hisp_house" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Hisp. VAP Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_h" />
                <Argument name="target" value="&target_hisp_house;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_hisp_senate" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Hisp. VAP Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_h" />
                <Argument name="target" value="&target_hisp_senate;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_na_congress" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Native American Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_na" />
                <Argument name="target" value="&target_na_congress;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_na_house" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Native American Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_na" />
                <Argument name="target" value="&target_na_house;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority_na_senate" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Native American Majority (&gt; 50%%)"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_na" />
                <Argument name="target" value="&target_na_senate;" />
            </ScoreFunction>

            <ScoreFunction id="plan_majority_minority" type="plan"
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                label="Majority Minority District"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S. 30, 49 (1986)) &apos;sufficiently large and geographically compact to constitute a majority in a single-member district&apos;.">
                <SubjectArgument name="population" ref="vap" />
                <SubjectArgument name="minority1" ref="vap_b" />
                <SubjectArgument name="minority2" ref="vap_h" />
                <SubjectArgument name="minority3" ref="vap_na" />
                <Argument name="validation" value="1" />
            </ScoreFunction>

                %(start_elec)s
            <ScoreFunction id="plan_repfairness" type="plan"
                calculator="publicmapping.redistricting.calculators.RepresentationalFairness"
                label="Representational Fairness"
                description="Representational fairness is increased when the percentage of districts a party would likely win (based upon the &apos;partisan index&apos; used to determine Competitiveness) closely mirrors that party.s percentage of the statewide vote." >
                <Argument name="range" value="0.05" />
                <SubjectArgument name="normalized democratic" ref="vote_dem_norm" />
                <SubjectArgument name="normalized republican" ref="vote_rep_norm" />
            </ScoreFunction>
                %(end_elec)s

            <ScoreFunction id="plan_schwartzberg" type="plan"
                calculator="publicmapping.redistricting.calculators.Schwartzberg"
                label="Average Compactness"
                description="The competition is using the &apos;Schwartzberg&apos; compactness measure. This measure is a ratio of the perimeter of the district to the circumference of the circle whose area is equal to the area of the district." >
            </ScoreFunction>

        </ScoreFunctions>
        
        <ScorePanels>
            <ScorePanel id="panel_equipop_all" type="plan" position="1"
                title="Equipopulation" template="leaderboard_panel_all.html">
                <Score ref="plan_equivalence" />
            </ScorePanel>
            <ScorePanel id="panel_equipop_mine" type="plan" position="1"
                title="Equipopulation" template="leaderboard_panel_mine.html">
                <Score ref="plan_equivalence" />
            </ScorePanel>
            <ScorePanel id="panel_compact_all" type="plan" position="2"
                title="Schwartzberg" template="leaderboard_panel_all.html">
                <Score ref="plan_schwartzberg" />
            </ScorePanel>
            <ScorePanel id="panel_compact_mine" type="plan" position="2"
                title="Schwartzberg" template="leaderboard_panel_mine.html">
                <Score ref="plan_schwartzberg" />
            </ScorePanel>
                %(start_elec)s
            <ScorePanel id="panel_competitive_all" type="plan" position="3"
                title="Competitiveness" template="leaderboard_panel_all.html">
                <Score ref="plan_competitiveness" />
            </ScorePanel>
            <ScorePanel id="panel_competitive_mine" type="plan" position="3"
                title="Competitiveness" template="leaderboard_panel_mine.html">
                <Score ref="plan_competitiveness" />
            </ScorePanel>
            <ScorePanel id="panel_rf_all" type="plan" position="4"
                title="Representational Fairness" template="leaderboard_panel_all.html">
                <Score ref="plan_repfairness" />
            </ScorePanel>
            <ScorePanel id="panel_rf_mine" type="plan" position="4"
                title="Representational Fairness" template="leaderboard_panel_mine.html">
                <Score ref="plan_repfairness" />
            </ScorePanel>
                %(end_elec)s

            <!-- Summary above all sidebar panels -->
            <ScorePanel id="congressional_panel_summary" type="plan_summary" position="1"
                title="Plan Summary" cssclass="plan_summary congressional" template="plan_summary.html">
	        <Score ref="a_congress_plan_equipopulation_summary"/>
                <Score ref="b_plan_congress_noncontiguous"/>
                <Score ref="plan_majority_minority_blk_congress" />
                <Score ref="plan_majority_minority_hisp_congress" />
		%(start_na)s
                <Score ref="plan_majority_minority_na_congress" />
		%(end_na)s
            </ScorePanel>

            <ScorePanel id="house_panel_summary" type="plan_summary" position="1"
                title="Plan Summary" cssclass="plan_summary house" template="plan_summary.html">
	        <Score ref="a_house_plan_equipopulation_summary"/>
                <Score ref="b_plan_house_noncontiguous"/>
                <Score ref="plan_majority_minority_blk_house" />
                <Score ref="plan_majority_minority_hisp_house" />
		%(start_na)s
                <Score ref="plan_majority_minority_na_house" />
		%(end_na)s
            </ScorePanel>

            <ScorePanel id="senate_panel_summary" type="plan_summary" position="1"
                title="Plan Summary" cssclass="plan_summary senate" template="plan_summary.html">
	        <Score ref="a_senate_plan_equipopulation_summary"/>
                <Score ref="b_plan_senate_noncontiguous"/>
                <Score ref="a_senate_plan_count_districts" />
                <Score ref="plan_majority_minority_blk_senate" />
                <Score ref="plan_majority_minority_hisp_senate" />
		%(start_na)s
                <Score ref="plan_majority_minority_na_senate" />
		%(end_na)s
            </ScorePanel>

            <!-- Basic Information -->
            <ScorePanel id="congresional_panel_info" type="district" position="2"
                title="Basic Information" cssclass="district_basic_info congressional" 
                template="basic_information.html">
                <Score ref="a_congressional_population" />
                <Score ref="district_contiguous" />
                <Score ref="district_schwartzberg" />
            </ScorePanel>

            <ScorePanel id="house_panel_info" type="district" position="2"
                title="Basic Information" cssclass="district_basic_info house" 
                template="basic_information.html">
                <Score ref="a_house_population" />
                <Score ref="district_contiguous" />
                <Score ref="district_schwartzberg" />
            </ScorePanel>
            
            <ScorePanel id="senate_panel_info" type="district" position="2"
                title="Basic Information" cssclass="district_basic_info senate" 
                template="basic_information.html">
                <Score ref="a_senate_population" />
                <Score ref="district_contiguous" />
                <Score ref="district_schwartzberg" />
            </ScorePanel>
            
            <!-- Demographics -->
            <ScorePanel id="congressional_panel_demo" type="district" position="2"
                title="Demographics" cssclass="district_demographics congressional" 
                template="demographics.html">
                %(start_elec)s
                <Score ref="district_vote_dem_percent" />
                %(end_elec)s
                <Score ref="district_blkvap_percent" />
                <Score ref="district_hispvap_percent" />
            </ScorePanel>

            <ScorePanel id="house_panel_demo" type="district" position="2"
                title="Demographics" cssclass="district_demographics house" 
                template="demographics.html">
                %(start_elec)s
                <Score ref="district_vote_dem_percent" />
                %(end_elec)s
                <Score ref="district_blkvap_percent" />
                <Score ref="district_hispvap_percent" />
            </ScorePanel>

            <ScorePanel id="senate_panel_demo" type="district" position="2"
                title="Demographics" cssclass="district_demographics senate" 
                template="demographics.html">
                %(start_elec)s
                <Score ref="district_vote_dem_percent" />
                %(end_elec)s
                <Score ref="district_blkvap_percent" />
                <Score ref="district_hispvap_percent" />
            </ScorePanel>

	     <!-- Needed due to issue https://sourceforge.net/apps/trac/publicmapping/ticket/340 Delete after setup -->
		<ScorePanel id="stats_picker" type="district" position="1" title="Stats Picker" cssclass="hidden" template="demographics.html">
			<Score ref="district_poptot"/>
			<Score ref="district_totpop_b"/>
			<Score ref="district_totpop_h"/>
			<Score ref="district_totpop_a"/>
			<Score ref="district_totpop_na"/>
			<Score ref="district_totpop_pi"/>
			<Score ref="district_totpop_wnh"/>
			<Score ref="district_vap"/>
			<Score ref="district_vap_b"/>
			<Score ref="district_vap_h"/>
			<Score ref="district_vap_a"/>
			<Score ref="district_vap_na"/>
			<Score ref="district_vap_pi"/>
			<Score ref="district_vap_wnh"/>
			<Score ref="district_blkvap_percent"/>
			<Score ref="district_hispvap_percent"/>
			<Score ref="district_avap_percent"/>
			<Score ref="district_navap_percent"/>
			<Score ref="district_pivap_percent"/>
			<Score ref="district_wnhvap_percent"/>
                	%(start_elec)s
			<Score ref="district_vote"/>
			<Score ref="district_vote_dem"/>
			<Score ref="district_vote_rep"/>
			<Score ref="district_vote_dem_percent"/>
			<Score ref="district_vote_rep_percent"/>
                	%(end_elec)s
		</ScorePanel>
        </ScorePanels>
        
        <ScoreDisplays>
            <ScoreDisplay legislativebodyref="congress" type="leaderboard" 
                title="Congressional Leaderboard - All" cssclass="leaderboard congress">
                <ScorePanel ref="panel_equipop_all" />
                <ScorePanel ref="panel_compact_all" />
                %(start_elec)s
                <ScorePanel ref="panel_competitive_all" />
                <ScorePanel ref="panel_rf_all" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="congress" type="leaderboard" 
                title="Congressional Leaderboard - Mine" cssclass="leaderboard congress">
                <ScorePanel ref="panel_equipop_mine" />
                <ScorePanel ref="panel_compact_mine" />
                %(start_elec)s
                <ScorePanel ref="panel_competitive_all" />
                <ScorePanel ref="panel_rf_mine" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="house" type="leaderboard" 
                title="State House Leaderboard - All" cssclass="leaderboard house">
                <ScorePanel ref="panel_equipop_all" />
                <ScorePanel ref="panel_compact_all" />
                %(start_elec)s
                <ScorePanel ref="panel_competitive_all" />
                <ScorePanel ref="panel_rf_all" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="house" type="leaderboard" 
                title="State House Leaderboard - Mine" cssclass="leaderboard house">
                <ScorePanel ref="panel_equipop_mine" />
                <ScorePanel ref="panel_compact_mine" />
                %(start_elec)s
                <ScorePanel ref="panel_competitive_mine" />
                <ScorePanel ref="panel_rf_mine" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="senate" type="leaderboard" 
                title="State Senate Leaderboard - All" cssclass="leaderboard senate">
                <ScorePanel ref="panel_equipop_all" />
                <ScorePanel ref="panel_compact_all" />
                %(start_elec)s
                <ScorePanel ref="panel_competitive_all" />
                <ScorePanel ref="panel_rf_all" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="senate" type="leaderboard" 
                title="State Senate Leaderboard - Mine" cssclass="leaderboard senate">
                <ScorePanel ref="panel_equipop_mine" />
                <ScorePanel ref="panel_compact_mine" />
                %(start_elec)s
                <ScorePanel ref="panel_competitive_mine" />
                <ScorePanel ref="panel_rf_mine" />
                %(end_elec)s
            </ScoreDisplay>

             <!-- Sidebar configuration -->
            <ScoreDisplay legislativebodyref="congress" type="sidebar" title="Basic Information" cssclass="basic_information">
                <ScorePanel ref="congressional_panel_summary" />
                <ScorePanel ref="congresional_panel_info" />
            </ScoreDisplay>

            <ScoreDisplay legislativebodyref="congress" type="sidebar" title="Demographics" cssclass="demographics">
                <ScorePanel ref="congressional_panel_summary" />
                <ScorePanel ref="congressional_panel_demo" />
            </ScoreDisplay>

            <ScoreDisplay legislativebodyref="house" type="sidebar" title="Basic Information" cssclass="basic_information">
                <ScorePanel ref="house_panel_summary" />
                <ScorePanel ref="house_panel_info" />
            </ScoreDisplay>

            <ScoreDisplay legislativebodyref="house" type="sidebar" title="Demographics" cssclass="demographics">
                <ScorePanel ref="house_panel_summary" />
                <ScorePanel ref="house_panel_demo" />
            </ScoreDisplay>

            <ScoreDisplay legislativebodyref="senate" type="sidebar" title="Basic Information" cssclass="basic_information">
                <ScorePanel ref="senate_panel_summary" />
                <ScorePanel ref="senate_panel_info" />
            </ScoreDisplay>

            <ScoreDisplay legislativebodyref="senate" type="sidebar" title="Demographics" cssclass="demographics">
                <ScorePanel ref="senate_panel_summary" />
                <ScorePanel ref="senate_panel_demo" />
            </ScoreDisplay>

<!-- Needed due to issue https://sourceforge.net/apps/trac/publicmapping/ticket/340 Delete after setup -->
	<ScoreDisplay legislativebodyref="congress" type="sidebar" title="All Stats" cssclass="hidden"><ScorePanel ref="stats_picker"/></ScoreDisplay>
        </ScoreDisplays>
    </Scoring>


    <Validation>
        <Criteria legislativebodyref="congress">
            <Criterion name="Equipopulation - Congress" description="&lt;p&gt;Your plan does not meet the competition criteria for Equipopulation:&lt;/p&gt;&lt;p&gt; The population of each Congressional district must be &pop_congress_max;-&pop_congress_min;">  
                <Score ref="a_congress_plan_equipopulation_validation" />
            </Criterion>
            <Criterion name="AllContiguous - Congress" 
                description="&lt;p&gt;Your plan does not meet the competition criteria for Contiguity&lt;/p&gt;&lt;p&gt;Every part of a district must be reachable from every other part without crossing the district's borders. All districts within a plan must be contiguous. &lt;/p&gt;">
                <Score ref="plan_all_contiguous" />
            </Criterion>
            <Criterion name="MajorityMinority - Congress" description="">
                <Score ref="plan_majority_minority" />
            </Criterion>
            <Criterion name="CountDistricts - Congress" description="">
                <Score ref="a_congress_plan_count_districts" />
            </Criterion>
            <Criterion name="AllBlocksAssigned - Congress" description="">
                <Score ref="plan_all_blocks_assigned" />
            </Criterion>
        </Criteria>
        <Criteria legislativebodyref="house">
            <Criterion name="Equipopulation - House" description="&lt;p&gt;Your plan does not meet the competition criteria for Equipopulation:&lt;/p&gt;&lt;p&gt;The population of each House of Delegates district must be &pop_house_min; - &pop_house_max;"> 
                <Score ref="a_house_plan_equipopulation_validation" />
            </Criterion>
            <Criterion name="AllContiguous - House" 
                description="&lt;p&gt;Your plan does not meet the competition criteria for Contiguity&lt;/p&gt;&lt;p&gt;Every part of a district must be reachable from every other part without crossing the district's borders. All districts within a plan must be contiguous. &lt;/p&gt;">
                <Score ref="plan_all_contiguous" />
            </Criterion>
            <Criterion name="MajorityMinority - House" description="">
                <Score ref="plan_majority_minority" />
            </Criterion>
            <Criterion name="CountDistricts - House" description="">
                <Score ref="a_house_plan_count_districts" />
            </Criterion>
            <Criterion name="AllBlocksAssigned - House" description="">
                <Score ref="plan_all_blocks_assigned" />
            </Criterion>
        </Criteria>
        <Criteria legislativebodyref="senate">
            <Criterion name="Equipopulation - Senate" description="&lt;p&gt;Your plan does not meet the competition criteria for Equipopulation:&lt;/p&gt;&lt;p&gt;The population of each State Senate district must be &pop_house_min;-&pop_house_max;">
                <Score ref="a_senate_plan_equipopulation_validation" />
            </Criterion>
            <Criterion name="AllContiguous - Senate" 
                description="&lt;p&gt;Your plan does not meet the competition criteria for Contiguity&lt;/p&gt;&lt;p&gt;Every part of a district must be reachable from every other part without crossing the district's borders. All districts within a plan must be contiguous. &lt;/p&gt;">
                <Score ref="plan_all_contiguous" />
            </Criterion>
            <Criterion name="MajorityMinority - Senate" description="">
                <Score ref="plan_majority_minority" />
            </Criterion>
            <Criterion name="CountDistricts - Senate" description="">
                <Score ref="a_senate_plan_count_districts" />
            </Criterion>
            <Criterion name="AllBlocksAssigned - Senate" description="">
                <Score ref="plan_all_blocks_assigned" />
            </Criterion>
        </Criteria>
    </Validation>

    <!--
    Optional configuration for geounits that require special contiguity rules.
    'id' is the portable id of the geounit in which to configure an override.
    'connect_to' is the portable id of the geounit in which the geounit is
    to be considered contiguous with. Tests for contiguity will apply these overrides
    in order to account for contiguity when physical contiguity is not possible.
    For example, an island may need to be marked contiguous with one or more geounits
    on an adjacent coast (possibly containing harbors). 
    <ContiguityOverrides>
        <ContiguityOverride id="510030112012077" connect_to="510030102011065" />
        <ContiguityOverride id="510030112012077" connect_to="510030103003037" />
    </ContiguityOverrides>
    -->

	<!-- Contiguity Overrides, if Any -->
	%(contiguityOverrideString)s

    <GeoLevels>
      <GeoLevel id="block" name="block" min_zoom="6" sort_key="3" tolerance="2.5">

          <Shapefile path="/projects/PublicMapping/data/census_blocks.shp">
              <Fields>

                  <Field name="NAME10" type="name"/>
                  <Field name="GEOID10" type="portable"/>
                  <Field name="STATEFP10" type="tree" pos="0" width="2"/>
                  <Field name="COUNTYFP10" type="tree" pos="1" width="3"/>
                  <Field name="TRACTCE10" type="tree" pos="2" width="6"/>
                  <Field name="BLOCKCE10" type="tree" pos="3" width="4"/>
              </Fields>
          </Shapefile>
          
          <GeoLevelCharacteristics>
              <GeoLevelCharacteristic ref="totpop" />
              <GeoLevelCharacteristic ref="vap" />
              <GeoLevelCharacteristic ref="vap_b" />
              <GeoLevelCharacteristic ref="vap_h" />
              <GeoLevelCharacteristic ref="vap_na" />
              <GeoLevelCharacteristic ref="vap_wnh" />
              <GeoLevelCharacteristic ref="vap_pi" />
              <GeoLevelCharacteristic ref="vap_a" />
              <GeoLevelCharacteristic ref="totpop_wnh" />
              <GeoLevelCharacteristic ref="totpop_pi" />
              <GeoLevelCharacteristic ref="totpop_a" />
              <GeoLevelCharacteristic ref="totpop_b" />
              <GeoLevelCharacteristic ref="totpop_h" />
              <GeoLevelCharacteristic ref="totpop_na" />
                %(start_elec)s
              <GeoLevelCharacteristic ref="vote_dem" />
              <GeoLevelCharacteristic ref="vote_rep" />
              <GeoLevelCharacteristic ref="vote_tot" />
              <GeoLevelCharacteristic ref="vote_dem_norm" />
              <GeoLevelCharacteristic ref="vote_rep_norm" />
              <GeoLevelCharacteristic ref="vote_tot_norm" />
                %(end_elec)s
          </GeoLevelCharacteristics>
         <LegislativeBodies>
              <LegislativeBody ref="congress">
                  <LegislativeTargets>
                      <LegislativeTarget ref="congress_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
              <LegislativeBody ref="house">
                  <LegislativeTargets>
                      <LegislativeTarget ref="house_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
              <LegislativeBody ref="senate">
                  <LegislativeTargets>
                      <LegislativeTarget ref="senate_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
          </LegislativeBodies>

     </GeoLevel>
      <GeoLevel id="tract" name="tract" min_zoom="3" sort_key="2" tolerance="25">
         <Files>
              <Geography path="/projects/PublicMapping/data/census_tracts.shp">
            <Fields>
                      <Field name="NAME10" type="name" />
                      <Field name="GEOID10" type="portable" />
                      <Field name="STATEFP10" type="tree" pos="0" width="2"/>
                      <Field name="COUNTYFP10" type="tree" pos="1" width="3"/>
                      <Field name="TRACTCE10" type="tree" pos="2" width="6"/>
                  </Fields>
              </Geography>
          </Files>
          <GeoLevelCharacteristics>
              <GeoLevelCharacteristic ref="totpop" />
              <GeoLevelCharacteristic ref="vap" />
              <GeoLevelCharacteristic ref="vap_b" />
              <GeoLevelCharacteristic ref="vap_h" />
              <GeoLevelCharacteristic ref="vap_na" />
              <GeoLevelCharacteristic ref="vap_wnh" />
              <GeoLevelCharacteristic ref="vap_pi" />
              <GeoLevelCharacteristic ref="vap_a" />
              <GeoLevelCharacteristic ref="totpop_wnh" />
              <GeoLevelCharacteristic ref="totpop_pi" />
              <GeoLevelCharacteristic ref="totpop_a" />
              <GeoLevelCharacteristic ref="totpop_b" />
              <GeoLevelCharacteristic ref="totpop_h" />
              <GeoLevelCharacteristic ref="totpop_na" />
                %(start_elec)s
              <GeoLevelCharacteristic ref="vote_dem" />
              <GeoLevelCharacteristic ref="vote_rep" />
              <GeoLevelCharacteristic ref="vote_tot" />
              <GeoLevelCharacteristic ref="vote_dem_norm" />
              <GeoLevelCharacteristic ref="vote_rep_norm" />
              <GeoLevelCharacteristic ref="vote_tot_norm" />
                %(end_elec)s
          </GeoLevelCharacteristics>
         <LegislativeBodies>
              <LegislativeBody ref="congress">
                  <Parent ref="block" />
                  <LegislativeTargets>
                      <LegislativeTarget ref="congress_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
              <LegislativeBody ref="house">
                  <Parent ref="block" />
                  <LegislativeTargets>
                      <LegislativeTarget ref="house_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
              <LegislativeBody ref="senate">
                  <Parent ref="block" />
                  <LegislativeTargets>
                      <LegislativeTarget ref="senate_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
          </LegislativeBodies>

      </GeoLevel>

      <GeoLevel id="county" name="county" min_zoom="0" sort_key="1" tolerance="250">
          <Files>
              <Geography path="/projects/PublicMapping/data/census_counties.shp">
                  <Fields>
                      <Field name="NAME10" type="name"/>
                      <Field name="GEOID10" type="portable"/>
                      <Field name="STATEFP10" type="tree" pos="0" width="2"/>
                      <Field name="COUNTYFP10" type="tree" pos="1" width="3"/>
                  </Fields>
              </Geography>
          </Files>
         <GeoLevelCharacteristics>
              <GeoLevelCharacteristic ref="totpop" />
              <GeoLevelCharacteristic ref="vap" />
              <GeoLevelCharacteristic ref="vap_b" />
              <GeoLevelCharacteristic ref="vap_h" />
              <GeoLevelCharacteristic ref="vap_na" />
              <GeoLevelCharacteristic ref="vap_wnh" />
              <GeoLevelCharacteristic ref="vap_pi" />
              <GeoLevelCharacteristic ref="vap_a" />
              <GeoLevelCharacteristic ref="totpop_wnh" />
              <GeoLevelCharacteristic ref="totpop_pi" />
              <GeoLevelCharacteristic ref="totpop_a" />
              <GeoLevelCharacteristic ref="totpop_b" />
              <GeoLevelCharacteristic ref="totpop_h" />
              <GeoLevelCharacteristic ref="totpop_na" />
               %(start_elec)s
              <GeoLevelCharacteristic ref="vote_dem" />
              <GeoLevelCharacteristic ref="vote_rep" />
              <GeoLevelCharacteristic ref="vote_tot" />
              <GeoLevelCharacteristic ref="vote_dem_norm" />
              <GeoLevelCharacteristic ref="vote_rep_norm" />
              <GeoLevelCharacteristic ref="vote_tot_norm" />
                %(end_elec)s
          </GeoLevelCharacteristics>
       <LegislativeBodies>
              <LegislativeBody ref="congress">
                  <Parent ref="tract" />
                  <LegislativeTargets>
                      <LegislativeTarget ref="congress_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
              <LegislativeBody ref="house">
                  <Parent ref="tract" />
                  <LegislativeTargets>
                      <LegislativeTarget ref="house_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
              <LegislativeBody ref="senate">
                  <Parent ref="tract" />
                  <LegislativeTargets>
                      <LegislativeTarget ref="senate_target" default="true" />
                  </LegislativeTargets>
              </LegislativeBody>
          </LegislativeBodies>
      </GeoLevel>
    </GeoLevels>

    <Templates>
        <Template name="Congressional">
            <LegislativeBody ref="congress"/>
             <Blockfile path="/projects/PublicMapping/data/congress_generated_index.csv" />
        </Template>
        <Template name="State House">
            <LegislativeBody ref="house"/>
            <Blockfile path="/projects/PublicMapping/data/house_generated_index.csv" />
        </Template>
        <Template name="State Senate">
            <LegislativeBody ref="senate"/>
            <Blockfile path="/projects/PublicMapping/data/senate_generated_index.csv" />
        </Template>
    </Templates>

    <Project root="/projects/PublicMapping/DistrictBuilder" sessionquota="5" 
             sessiontimeout="15">
        <!-- Database connection information. -->
        <Database name="publicmapping" user="publicmapping" password="publicmapping"/>
        
        <!-- 
        
        Administrative user information. This should match the admin
        user created when the django project is created.
        
        -->
        <Admin user="admin" email="support@publicmapping.org" password="admin"/>
        
        <!-- Configuration items specific to the 'redistricting' app. -->
       <Redistricting>      
	   <MapServer hostname="" ns="pmp" nshref="http://publicmapping.sourceforge.net/"
                adminuser="admin" adminpass="admin" maxfeatures="100" 
                styles="/projects/PublicMapping/DistrictBuilder/sld" />
            <!-- 
            
            Use a GoogleAnalytics account to tract the usage of the 
            application. This requires an account and domain.
            <GoogleAnalytics account="" domain=""/>
            
            -->
            <!-- Upload file size restrictions. This is in KB -->
            <Upload maxsize="2500"/>
            <!-- Undo restrictions -->
            <MaxUndos duringedit="50" afteredit="10" />
            <!-- Leaderboard configuration -->
            <Leaderboard maxranked="10" />
       </Redistricting>
       <Reporting>
            <BardConfigs>
  		 <BardConfig 
                    id="blocks"
                    shape="/projects/PublicMapping/data/census_configured.Rdata" 
                    temp="/projects/PublicMapping/local/reports"
                    transform="/projects/PublicMapping/DistrictBuilder/docs/bard_template.xslt">
                    <PopVars>
                        <PopVar subjectref="totpop" threshold=".01" default="true" />
                        <PopVar subjectref="vap" threshold=".1" />
                    </PopVars>
                    <RatioVars>
                        <!--
                        
                        Set up RatioVars for both ethnicity and political 
                        party.
                        
                        -->
                        <RatioVar id="racialComp" label="Majority Minority Districts" threshold=".5">
                            <Numerators>
                                <Numerator subjectref="totpop_b" />
                                <Numerator subjectref="totpop_h" />
                                <Numerator subjectref="totpop_na" />
                                <Numerator subjectref="totpop_a" />
                                <Numerator subjectref="totpop_pi" />
                                <Numerator subjectref="totpop_wnh" />
                            </Numerators>
                            <Denominator subjectref="totpop" />
                        </RatioVar>
                        <RatioVar id="racialCompVap" label="Majority Minority Districts" threshold=".5">
                            <Numerators>
                                <Numerator subjectref="vap_b" />
                                <Numerator subjectref="vap_h" />
                                <Numerator subjectref="vap_na" />
                                <Numerator subjectref="vap_a" />
                                <Numerator subjectref="vap_pi" />
                                <Numerator subjectref="vap_wnh" />
                            </Numerators>
                            <Denominator subjectref="vap" />
                        </RatioVar>
                %(start_elec)s
                        <RatioVar id="partyControl" label="Party-Controlled Districts" threshold=".5">
                            <Numerators>
                                <Numerator subjectref="vote_dem" />
                                <Numerator subjectref="vote_rep" />
                            </Numerators>
                            <Denominator subjectref="vote_tot" />
                        </RatioVar>
                %(end_elec)s
                    </RatioVars>
                    <SplitVars>
                        <!-- 
                        
                        See whether a given district splits a geography.
                        This can be any higher level geography: a county,
                        VTd, or tract.
                        -->
                        <SplitVar field="COUNTYFP10" label="County" />
                        <SplitVar field="TRACTCE10" label="Tract" />
                    </SplitVars>
                </BardConfig>
            </BardConfigs>
           <BardBodyConfigs>
                <!--
                For each legislative body, map the configuration to the
                geography used to generate reports.
                -->
                <BardBodyConfig
                    id="congress_blocks"
                    legislativebodyref="congress"
                    bardconfigref="blocks" />
                <BardBodyConfig
                    id="house_blocks"
                    legislativebodyref="house"
                    bardconfigref="blocks" />
                <BardBodyConfig
                    id="senate_blocks"
                    legislativebodyref="senate"
                    bardconfigref="blocks" />
            </BardBodyConfigs>
        </Reporting>
        
        <!-- Information about the mailer configuration. -->
        <Mailer server="localhost" port="25" username="" password=""/>
    </Project>
    
</DistrictBuilder>

      """



def gen_config(num_districts_congress,num_districts_senate,num_districts_house,sum_TOTPOP,has_election_data=0,has_vtds=0, conf_na=False , 
target_na_congress=0, target_hisp_congress = 0 , target_bl_congress = 0,
target_na_house=0, target_hisp_house = 0 , target_bl_house = 0,
target_na_senate =0, target_hisp_senate = 0 , target_bl_senate = 0, contiguityOverrideString = ""): 

        start_na="<!--"        
        start_elec="<!--"        
	end_elec="-->"
	end_na="-->"
        midlevel="tract"
	if (conf_na==True):
                start_na=""
                end_na=""
        midlevel_width="6"
        midlevel_var="TRACTCE10"        
	if (has_election_data==1):
                start_elec=""
                end_elec=""       
	if (has_vtds==1) :                
		midlevel="vtds"
                midlevel_width="4"
                midlevel_var="VTDST10"        
	pop_congress = int(round((sum_TOTPOP/float(num_districts_congress))))
	pop_congress_max = int(round((sum_TOTPOP/float(num_districts_congress)) * 1.005))
        pop_congress_min = int(round((sum_TOTPOP/float(num_districts_congress)) * 0.995))
	pop_house = int(round((sum_TOTPOP/float(num_districts_house))))
	pop_house_max = int(round((sum_TOTPOP/float(num_districts_house)) * 1.1))
        pop_house_min = int(round((sum_TOTPOP/float(num_districts_house)) * 0.9))
	pop_senate = int(round((sum_TOTPOP/float(num_districts_senate))))
	pop_senate_max = int(round((sum_TOTPOP/float(num_districts_senate)) * 1.1))
        pop_senate_min = int(round((sum_TOTPOP/float(num_districts_senate)) * 0.9))
        target_file = '/projects/PublicMapping/DistrictBuilder/docs/config_census_generated.xml'
        f = open(target_file,'w')
        f.write(str( Config_Template(start_elec=start_elec,end_elec=end_elec,num_districts_congress=num_districts_congress,num_districts_house=num_districts_house,num_districts_senate=num_districts_senate,pop_congress_max=pop_congress_max,pop_congress_min=pop_congress_min,pop_senate_max=pop_senate_max, pop_senate_min=pop_senate_min,pop_house_max=pop_house_max,pop_house_min=pop_house_min,pop_congress=pop_congress,pop_senate=pop_senate,pop_house=pop_house,start_na=start_na, end_na=end_na, target_na_congress=target_na_congress, target_hisp_congress=target_hisp_congress, target_bl_congress=target_bl_congress, target_na_house=target_na_house, target_hisp_house=target_hisp_house, target_bl_house=target_bl_house, target_na_senate=target_na_senate, target_hisp_senate=target_hisp_senate, target_bl_senate=target_bl_senate,contiguityOverrideString=contiguityOverrideString)))
	f.write("\n")
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)    


###
### MAIN
###

#
#  Get Arguments
#


parser=optparse.OptionParser(usage="%prog -F[fips_code] -C[num_congressional_districts] -S[num_senate_districts] -H[num_house_districts]", version="%prog 0.1")

# required arguments
parser.add_option('-F','--fips', dest='stateFips',help="State two digit FIPS code", type=int, default=0)
parser.add_option('-C','--congdist', dest='congDis',help="number of congressional districts", type=int, default=0)
parser.add_option('-H', '--housedist',dest='houseDis',help="number of senate districts", type=int, default=0)
parser.add_option('-S', '--sendist', dest='senDis',help="number of house districts", type=int,default=0)

# operations to perform
parser.add_option('-i', '--install', dest="do_install", help="Install dependencencies.", default=False, action='store_true') 
parser.add_option('-g', '--getdata', dest="do_getdata", help="Get data.", default=False, action='store_true') 
parser.add_option('-s', '--gensld', dest="do_gensld", help="Generate slds", default=False, action='store_true') 
parser.add_option('-c', '--genconf', dest="do_genconf", help="Generate config file", default=False, action='store_true') 
parser.add_option('-d', '--dropdb', dest="do_dropdb", help="Drop database", default=False, action='store_true') 
parser.add_option('-r', '--run', dest="do_run", help="run setup.py", default=False, action='store_true') 

# configuration options
parser.add_option('--na_inc', dest="conf_na", help="Include Native Americans in stats.", default=False, action='store_true') 
parser.add_option('--na_targ_c', dest='target_na_congress',help="Number of Native American Congressional Districts for target", type=int, default=0)
parser.add_option('--na_targ_h', dest='target_na_house',help="Number of Native American House Districts for target", type=int, default=0)
parser.add_option('--na_targ_s', dest='target_na_senate',help="Number of Native American Senate Districts for target", type=int, default=0)
parser.add_option('--hisp_targ_c', dest='target_hisp_congress',help="Number of Hispanic Congressional Districts for target", type=int, default=0)
parser.add_option('--hisp_targ_h', dest='target_hisp_house',help="Number of Hispanic House Districts for target", type=int, default=0)
parser.add_option('--hisp_targ_s', dest='target_hisp_senate',help="Number of Hispanic SenateDistricts for target", type=int, default=0)
parser.add_option('--bl_targ_c', dest='target_bl_congress',help="Number of Black Congressional districts for target", type=int, default=0)
parser.add_option('--bl_targ_h', dest='target_bl_house',help="Number of Black House districts for target", type=int, default=0)
parser.add_option('--bl_targ_s', dest='target_bl_senate',help="Number of Black Senate districts for target", type=int, default=0)

(parseResults,numargs)=parser.parse_args()


# include na if there is a positive target, even if not otherwise specified
if ((parseResults.target_na_congress+parseResults.target_na_senate+parseResults.target_na_house)>0) :
	parseResults.conf_na = True

allops = (not parseResults.do_install) and  (not parseResults.do_getdata) and  (not parseResults.do_gensld) and  (not parseResults.do_genconf) and (not parseResults.do_dropdb) and (not parseResults.do_run)
if (allops):
	parseResults.do_install=True
	parseResults.do_getdata=True
	parseResults.do_gensld=True
	parseResults.do_genconf=True
	parseResults.do_dropdb=True
	parseResults.do_run=True

if len(numargs) != 0:
        parser.error("additional arguments ignored ")
stateFips = parseResults.stateFips
houseDis = parseResults.houseDis
senDis= parseResults.senDis
congDis= parseResults.congDis
if (stateFips==0 or houseDis==0 or senDis==0 or congDis==0):
        print "Must supply all district arguments"
        raise ValueError

# install dependencies
if (parseResults.do_install):
	print "installing dependencies..."
	install_dependencies()

# Clear out DB
if (parseResults.do_dropdb):
	print 'clearing database ...'
	drop_db()

# generate generic sld files
if (parseResults.do_gensld):
	print 'generating generic sld files ...'
	gensld_none("county")
	gensld_none("tract")
	gensld_none("block")
	gensld_boundaries("county")
	gensld_boundaries("tract")
	gensld_boundaries("block")

# Retrieve data files

if (parseResults.do_getdata):
	print 'retrieving census data ...'
	get_census_data(stateFips)
	# merge standard variables
	# TODO: Refactor entirely in rpy
	print 'merging data...'
	robjects.r.source("/projects/PublicMapping/DistrictBuilder/docs/loadcensus/mergeCensus.R")

if ( (parseResults.do_genconf) or (parseResults.do_gensld)) :
	print 'calculating statistics for configs and slds...'
	robjects.r.source("/projects/PublicMapping/DistrictBuilder/docs/loadcensus/calcStats.R")
	sum_TOTPOP= robjects.r.sum_TOTPOP[0]
	# TODO: Refactor entirely in rpy
	# NOTE: robject is returning 6-level quantiles, has_election_data, has_vtd, sum_TOTPOP
	has_election_data = robjects.r.has_election_data[0]

if ( parseResults.do_genconf) :
	robjects.r.source("/projects/PublicMapping/DistrictBuilder/docs/loadcensus/contiguityOverride.R")
	# TODO: should work but has embedded string forwarding	
	#contiguityOverrideString = robjects.r.contiguityOverrideString
	f = open('/projects/PublicMapping/DistrictBuilder/docs/generated_overrides.xml', 'r')
	contiguityOverrideString = f.read()
	f.close()
	

# TODO: refactor as matrix of varnames and geographies
if ( parseResults.do_gensld) :
	print 'generating choropleth slds ...'
	gensld_choro("block","TOTPOP","Total Population",robjects.r.q_block_TOTPOP)
	gensld_choro_denquint("block","TOTPOP_H","Percent Hispanic Population",robjects.r.q_block_TOTPOP_H)
	gensld_choro_denquint("block","TOTPOP_B","Percent Black Population",robjects.r.q_block_TOTPOP_B)
	gensld_choro_denquint("block","TOTPOP_NA","Percent Native American Population",robjects.r.q_block_TOTPOP_NA)
	gensld_choro("block","VAP","Voting Age Population",robjects.r.q_block_VAP)
	gensld_choro_denquint("block","VAP_H","Percent Voting Age Hispanic Population",robjects.r.q_block_VAP_H)
	gensld_choro_denquint("block","VAP_B","Percent Voting Age Black Population",robjects.r.q_block_VAP_B)
	gensld_choro_denquint("block","VAP_NA","Percent Voting Age Native American Population",robjects.r.q_block_VAP_NA)
	gensld_choro("tract","TOTPOP","Total Population",robjects.r.q_tract_TOTPOP)
	gensld_choro_denquint("tract","TOTPOP_H","Percent Total Hispanic Population",robjects.r.q_tract_TOTPOP_H)
	gensld_choro_denquint("tract","TOTPOP_B","Percent Black Population",robjects.r.q_tract_TOTPOP_B)
	gensld_choro_denquint("tract","TOTPOP_NA","Percent Native American Population",robjects.r.q_tract_TOTPOP_NA)
	gensld_choro("tract","VAP","Voting Age Population",robjects.r.q_tract_VAP)
	gensld_choro_denquint("tract","VAP_H","Percent Voting Age Hispanic Population",robjects.r.q_tract_VAP_H)
	gensld_choro_denquint("tract","VAP_B","Percent Voting Age Black Population",robjects.r.q_tract_VAP_B)
	gensld_choro_denquint("tract","VAP_NA","Percent Voting Age Native American Population",robjects.r.q_tract_VAP_NA)
	gensld_choro("county","TOTPOP","Total Population",robjects.r.q_county_TOTPOP)
	gensld_choro_denquint("county","TOTPOP_H","Percent Hispanic Population",robjects.r.q_county_TOTPOP_H)
	gensld_choro_denquint("county","TOTPOP_B","Percent Black Population",robjects.r.q_county_TOTPOP_B)
	gensld_choro_denquint("county","TOTPOP_NA","Percent Native American Population",robjects.r.q_county_TOTPOP_NA)
	gensld_choro("county","VAP","Voting Age Population",robjects.r.q_county_VAP)
	gensld_choro_denquint("county","VAP_H","Percent Voting Age Hispanic Population",robjects.r.q_county_VAP_H)
	gensld_choro_denquint("county","VAP_B","Percent Voting Age Black Population",robjects.r.q_county_VAP_B)
	gensld_choro_denquint("county","VAP_NA","Percent Voting Age Native American Population",robjects.r.q_county_VAP_NA)
	if (has_election_data==1) :        
		gensld_choro_denquint("block","VOTE_DEM","Percent Predicted Democratic Vote ",robjects.r.q_block_VOTE_DEM)
		gensld_choro_denquint("block","VOTE_REP","Percent Predicted Republican Vote ",robjects.r.q_block_VOTE_REP)
        	gensld_choro("block","VOTE_TOT","Predicted Vote ",robjects.r.q_block_VOTE_TOT)
        	gensld_choro_denquint("tract","VOTE_DEM","Percent Predicted Democratic Vote ",robjects.r.q_tract_VOTE_DEM)
        	gensld_choro_denquint("tract","VOTE_REP","Percent Predicted Republican Vote ",robjects.r.q_tract_VOTE_REP)
        	gensld_choro("tract","VOTE_TOT","Predicted Vote ",robjects.r.q_tract_VOTE_TOT)
        	gensld_choro_denquint("county","VOTE_DEM","Perecent Predicted Democratic Vote ",robjects.r.q_county_VOTE_DEM)
        	gensld_choro_denquint("county","VOTE_REP","Percent Predicted Republican Vote ",robjects.r.q_county_VOTE_REP)
        	gensld_choro("county","VOTE_TOT","Predicted Vote ",robjects.r.q_county_VOTE_TOT)
		gensld_choro_denquint("block","VOTE_DEM_N","Percent Predicted Democratic Vote ",robjects.r.q_block_VOTE_DEM_N)
		gensld_choro_denquint("block","VOTE_REP_N","Percent Predicted Republican Vote ",robjects.r.q_block_VOTE_REP_N)
        	gensld_choro("block","VOTE_TOT_N","Predicted Vote ",robjects.r.q_block_VOTE_TOT_N)
        	gensld_choro_denquint("tract","VOTE_DEM_N","Percent Predicted Democratic Vote ",robjects.r.q_tract_VOTE_DEM_N)
        	gensld_choro_denquint("tract","VOTE_REP_N","Percent Predicted Republican Vote ",robjects.r.q_tract_VOTE_REP_N)
        	gensld_choro("tract","VOTE_TOT_N","Predicted Vote ",robjects.r.q_tract_VOTE_TOT_N)
        	gensld_choro_denquint("county","VOTE_DEM_N","Percent Predicted Democratic Vote ",robjects.r.q_county_VOTE_DEM_N)
        	gensld_choro_denquint("county","VOTE_REP_N","Percent Predicted Republican Vote ",robjects.r.q_county_VOTE_REP_N)
        	gensld_choro("county","VOTE_TOT_N","Predicted Vote ",robjects.r.q_county_VOTE_TOT_N)


# generate config file
if (parseResults.do_genconf):
	print 'generating config file ... '
	gen_config(num_districts_congress=congDis,num_districts_senate=senDis,num_districts_house=houseDis,sum_TOTPOP=sum_TOTPOP,has_election_data=has_election_data,has_vtds=0,conf_na=parseResults.conf_na, 
target_na_congress=parseResults.target_na_congress, target_hisp_congress = parseResults.target_hisp_congress, target_bl_congress = parseResults.target_bl_congress,
target_na_house=parseResults.target_na_house, target_hisp_house = parseResults.target_hisp_house, target_bl_house = parseResults.target_bl_house,
target_na_senate=parseResults.target_na_senate, target_hisp_senate = parseResults.target_hisp_senate, target_bl_senate = parseResults.target_bl_senate, contiguityOverrideString=contiguityOverrideString) 

if (parseResults.do_run):
	print 'running setup-py ... '
        olddir = os.getcwd()
        os.chdir("/projects/PublicMapping/DistrictBuilder/django/publicmapping/")
        subprocess.check_call(["ls"])
        #subprocess.check_call(["setup.py","-v2","/projects/PublicMapping/DistrictBuilder/docs/config.xsd"," /projects/PublicMapping/DistrictBuilder/docs/config_census_generated.xml"])
        subprocess.check_call(["./setup.py -v2 /projects/PublicMapping/DistrictBuilder/docs/config.xsd /projects/PublicMapping/DistrictBuilder/docs/config_census_generated.xml"],shell=True)
        os.chdir(olddir)
else:
	print '\n\n*** Now run: ***\n\n'
	print '(cd /projects/PublicMapping/DistrictBuilder/django/publicmapping/; python setup.py -v2 /projects/PublicMapping/DistrictBuilder/docs/config.xsd /projects/PublicMapping/DistrictBuilder/docs/config_census_generated.xml)'



# workaround celeryd first-time startup problem
print 'Starting celeryd ...'
subprocess.check_call(["service","celeryd","start"])
