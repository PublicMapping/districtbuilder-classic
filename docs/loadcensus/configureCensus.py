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
        cur.execute("truncate table redistricting_characteristic CASCADE ; truncate table redistricting_computedcharacteristic CASCADE; truncate table redistricting_district CASCADE; truncate table redistricting_geolevel CASCADE ; truncate table redistricting_geounit CASCADE; truncate table redistricting_legislativelevel CASCADE ; truncate table redistricting_profile CASCADE; truncate table redistricting_plan CASCADE ")
        #cur.execute("truncate table redistricting_characteristic CASCADE ; truncate table redistricting_computedcharacteristic CASCADE; truncate table redistricting_district CASCADE; truncate table redistricting_geolevel CASCADE ; truncate table redistricting_geounit CASCADE; truncate table redistricting_legislativebody CASCADE; truncate table redistricting_legislativedefault CASCADE ; truncate table redistricting_legislativelevel CASCADE ; truncate table redistricting_profile CASCADE; truncate table redistricting_plan CASCADE; truncate table re districting_subject CASCADE; truncate table redistricting_target CASCADE; ")
        db.commit()
        db.close()
### Install depende


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
        print 'Retrieving census shapefiles...'
        # put all data in publicmapping data directory
        olddir = os.getcwd()
        os.chdir("/projects/publicmapping/data/")
        # obtain state boundary files from census
        cenBlockFilePrefix = 'tl_2010_%s_tabblock10' % stateFips
        cenTractFilePrefix = 'tl_2010_%s_tract10' % stateFips
        cenCountyFilePrefix= 'tl_2010_%s_county10' % stateFips
        cmdarg = 'ftp://ftp2.census.gov/geo/tiger/TIGER2010/TABBLOCK/2010/%s.zip' % cenBlockFilePrefix 
        subprocess.check_call(["wget","-nc",cmdarg])
        cmdarg = 'ftp://ftp2.census.gov/geo/tiger/TIGER2010/TRACT/2010/%s.zip' % cenTractFilePrefix
        subprocess.check_call(["wget","-nc",cmdarg])
        cmdarg = 'ftp://ftp2.census.gov/geo/tiger/TIGER2010/COUNTY/2010/%s.zip' % cenCountyFilePrefix
        subprocess.check_call(["wget","-nc",cmdarg])
        # get additional data from our S3 bucket
        print 'Retrieving additional data...'
        cmdarg = 'https://s3.amazonaws.com/redistricting_supplement_data/redist/%s_redist_data.zip' % stateFips
        subprocess.check_call(["wget","-nc",cmdarg])
        print 'Unzipping files ...'
        # unzip data files
        for i in [ cenBlockFilePrefix, cenTractFilePrefix, cenCountyFilePrefix ] :
                myzip = zipfile.ZipFile('%s.zip' % i, 'r')
                myzip.extractall()
        myzip = zipfile.ZipFile('%s_redist_data.zip' % stateFips, 'r')
        myzip.extractall()        # Reproject block data
        print 'Reprojecting block shapefile...'
        if (os.path.exists("census_blocks.shp")) :
                os.remove('census_blocks.shp')
        subprocess.check_call(["ogr2ogr",'-overwrite','-t_srs','EPSG:3785','census_blocks.shp','%s.shp' % cenBlockFilePrefix ])
        # standardize file names
        print 'Copying data files...'
        shutil.copy('%s.dbf' % cenTractFilePrefix, 'census_tracts.dbf' )
        shutil.copy('%s.dbf' % cenCountyFilePrefix, 'census_county.dbf' )
        shutil.copy('%s_redist_data.csv' %stateFips , 'redist_data.csv' )
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
    _template = """
<?xml version="1.0" encoding="ISO-8859-1"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://
www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-ins
tance"  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
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
                <ogc:PropertyName>number</ogc:PropertyName>
                <ogc:Literal>%(top)s</ogc:Literal>
              </ogc:PropertyIsLessThan>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>number</ogc:PropertyName>
                <ogc:Literal>%(bottom)s</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">%(fill)s</CssParameter>
              <CssParameter name="fill-opacity">%(fillopacity)s</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        """



def gensld_none(geoname):
        target_file = '/projects/publicmapping/trunk/sld/%s_none.sld' % (geoname)       
        f = open(target_file,'w')
        f.write ( str(SldList_Template(layername="%s No fill" % (geoname),layertitle="%s No Fill" % (geoname) ,layerabs="A style showing the boundaries of a geounit with a transparent fill", slst=[],sli=Empty_Template, lst=[{"title":"Fill","fill":"#FFFFFF","fillopacity":"0.5"}],li=Sld_Poly_Template,elst=[{"title":"Boundary","stroke":"#555555","strokewidth":"0.25","strokeopacity":"1.0"}],eli=Sld_Line_Template)) )
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)    
def gensld_boundaries(geoname):
        target_file = '/projects/publicmapping/trunk/sld/%s_boundaries.sld' % (geoname) 
        f = open(target_file,'w')
        f.write ( str(SldList_Template(layername="%s Boundaries" % (geoname) ,layertitle="%s Boundaries Only" %(geoname),layerabs="A style showing the boundaries of a geounit", slst=[] ,sli=Empty_Template, lst=[],li=Empty_Template,elst=[{"title":"County Boundaries","fill":"#000000","fillopacity":"0.0","stroke":"#2255FF","strokewidth":"2","strokeopacity":"0.35"}],eli=Sld_PolyB_Template)))
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)  

#TODO: generalize to any number of choropleths
def gensld_choro(geoname,varname,vartitle,quantiles):
        target_file = '/projects/publicmapping/trunk/sld/%s_%s.sld' % (geoname,varname) 
        varabs="Grayscale choropleth based on quantiles of %s" % (varname)
        valuelist= [
          {"top": str(quantiles[5]),
          "bottom": str(quantiles[4]),
          "fill": "#000000",
          "fillopacity":"0.5"},
          {"top": str(quantiles[4]),
          "bottom": str(quantiles[3]),
          "fill": "#444444",
          "fillopacity":"0.5"},
          {"top": str(quantiles[3]),
          "bottom": str(quantiles[2]),
          "fill": "#777777",
          "fillopacity":"0.5"},
          {"top": str(quantiles[2]),
          "bottom": str(quantiles[1]),
          "fill": "#AAAAAA",
          "fillopacity":"0.5"},
          {"top": str(quantiles[1]),
          "bottom": str(quantiles[0]),
          "fill": "#EEEEEE",
          "fillopacity":"0.5"}]
        f = open(target_file,'w')
        f.write(str( SldList_Template(layername=varname,layertitle=vartitle,layerabs=varabs,slst=[],sli=Empty_Template, lst=valuelist,li=Sld_Range_Template,elst=[{"title":"Boundary","stroke":"#555555","strokewidth":"0.25","strokeopacity":"1.0"}],eli=Sld_Line_Template) ))
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)  


### Config file generation
### TODO: has_vtds==1 has not fully implemented 
###        paramaterize thresholds?

class Config_Template(DictionaryTemplate):
    _template = """
<DistrictBuilder>
    <!-- Define legislative bodies referenced in the system. -->
    <LegislativeBodies>
        <!-- A Legislative body has an ID (for referencing in GeoLevel
            definitions later), a name, and a label for plan items 
            ("District" for Congressional, etc) -->
        <LegislativeBody id="congress" name="Congressional" member="District %%s" maxdistricts="%(num_districts_congress)s"/>
        <LegislativeBody id="house" name="State House" member="District %%s" maxdistricts="%(num_districts_house)s" />
        <LegislativeBody id="senate" name="State Senate" member="District %%s" maxdistricts="%(num_districts_senate)s" />
    </LegislativeBodies>
    <!-- A list of subjects referenced in the system. -->
    <Subjects>       
	 <!-- A Subject is a measurement type, such as "Total Population".            
	 The subject is mapped to an attribute during the import phase,
            and contains a long and short display name. Subjects have IDs
            for referencing in GeoLevel definitions later. -->
        <Subject id="TOTPOP" field="TOTPOP" name="Total Population" short_name="Total Pop." displayed="true" sortkey="1" />
        <Subject id="TOTPOP_B" field="TOTPOP_B" name="African-American" short_name="Black" displayed="false" sortkey="2" />        
	<Subject id="TOTPOP_H" field="TOTPOP_H" name="Hispanic or Latino" short_name="Hispanic" displayed="false" sortkey="3" />
	<Subject id="TOTPOP_NA" field="TOTPOP_NA" name="Native American" short_name="Nat Amer" displayed="false" sortkey="4" />
        <Subject id="VAP" field="VAP" name="Voting Age Population" short_name="Total Pop." displayed="true" sortkey="5" />
        <Subject id="VAP_B" field="VAP_B" name="African-American Voting Age Population" short_name="Black VAP " displayed="false" sortkey="6" />
        <Subject id="VAP_H" field="VAP_H" name="Hispanic or Latino voting age population" short_name="Hispanic VAP" displayed="false" sortkey="8" />
        <Subject id="VAP_NA" field="VAP_NA" name="Native American Voting Age Population" short_name="Nat Amer VAP" displayed="false" sortkey="9" />

        %(start_elec)s
        <Subject id="VOTE_DEM" field="VOTE_DEM" name="number of likely Democratic voters" short_name="democratic voters" displayed="false" sortkey="10" />
        <Subject id="VOTE_REP" field="VOTE_REP" name="number of likely Republican voters" short_name="democratic voters" displayed="false" sortkey="11" />
        <Subject id="VOTE_TOT" field="VOTE_TOT" name="number of likely Republican voters" short_name="democratic voters" displayed="false" sortkey="12" />
        %(end_elec)s
   </Subjects>
   <Scoring>
        <ScoreFunctions>
                <ScoreFunction id="plan_equivalence" type="plan" label="Equal Population" calculator="publicmapping.redistricting.calculators.Equivalence" description="The Equipopulation score is the difference between the district
 with the highest population and the district with the lowest population.">
		<SubjectArgument name="value" ref="TOTPOP" />
	</ScoreFunction>
	<ScoreFunction id="plan_schwartzberg" type="plan" label="Average Compactness" calculator="publicmapping.redistricting.calculators.Schwartzberg" description="The competition is using the 'Schwartzberg' compactness measure. This measure is a ratio of the perimeter of the district to the circumference of the circle whose area is equal to the area of the district. ">
	</ScoreFunction>       
	
	 %(start_elec)s
            <ScoreFunction id="plan_competitiveness" type="plan" label="Competitiveness" calculator="publicmapping.redistricting.calculators.Competitiveness" description="Each plan's overall political competitiveness is determined by averaging each district.s 'partisan differential'.  The partisan differential of each district is calculated by subtracting the Democratic 'partisan index' from the Republican 'partisan index'.&lt;br/&gt;&lt;br/&gt;'Heavily' competitive districts are districts with partisan differentials of less than or equal to 5%%. 'Generally' competitive districts are districts with partisan differentials of greater than 5%% but less than 10%%.">               
		 <SubjectArgument name="democratic" ref="VOTE_DEM" />
		 <SubjectArgument name="republican" ref="VOTE_REP" />
            </ScoreFunction>
   	    <ScoreFunction id="plan_repfairness" type="plan" label="Representational Fairness"
                calculator="publicmapping.redistricting.calculators.RepresentationalFairness"
                description="Representational fairness is increased when the percentage of districts a party would likely win (based upon the 'partisan index' used to determine Competitiveness) closely mirrors that party.s percentage of the statewide vote. ">
                <SubjectArgument name="democratic" ref="VOTE_DEM" />
                <SubjectArgument name="republican" ref="VOTE_REP" />
                <Argument name="range" value="0.05" />
            </ScoreFunction>
	 %(end_elec)s
            <!-- For validation -->
            <ScoreFunction id="plan_majority_minority" type="plan" label="Majority Minority" 
                calculator="publicmapping.redistricting.calculators.MajorityMinority"
                description="Compliance with the Voting Rights Act will be assumed if maps include a minority-majority district in any area where a minority group is (as described in Thornburg V. Gingles, 478 U.S> 30, 49 (1986)) 'sufficiently large and geographically compact to constitute a majority in a single-member district'.">
                <SubjectArgument name="minority1" ref="VAP_H" />
                <SubjectArgument name="minority2" ref="VAP_B" />
                <SubjectArgument name="population" ref="VAP" />
            </ScoreFunction>
            <ScoreFunction id="plan_all_blocks_assigned" type="plan" label="All Blocks Assigned" 
                calculator="publicmapping.redistricting.calculators.AllBlocksAssigned"
                description="All blocks in the plan must be assigned.">
            </ScoreFunction>
            <ScoreFunction id="plan_all_contiguous" type="plan" label="All Contiguous" 
                calculator="publicmapping.redistricting.calculators.AllContiguous"
                description="Contiguity means that every part of a district must be reachable from every other part without crossing the district's borders. All districts within a plan must be contiguous. ">
            </ScoreFunction>
            <ScoreFunction id="congress_plan_equipopulation" type="plan" label="Equipopulation" 
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                description="The population of each Congressional district must be %(pop_congress_max)s - %(pop_congress_min)s .">
                <SubjectArgument name="value" ref="TOTPOP" />
                <Argument name="min" value="%(pop_congress_min)s" />
                <Argument name="max" value="%(pop_congress_max)s" />
            </ScoreFunction>
            <ScoreFunction id="congress_plan_count_districts" type="plan" label="Count Districts" 
                calculator="publicmapping.redistricting.calculators.CountDistricts"
                description="The number of districts in a Congressional redistricting plan must be %(num_districts_congress)s.">
                <Argument name="target" value="%(num_districts_congress)s" />
            </ScoreFunction>
            <ScoreFunction id="senate_plan_equipopulation" type="plan" label="Equipopulation" 
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                description="The population of each State Senate district %(pop_senate_max)s - %(pop_senate_min)s ">
                <SubjectArgument name="value" ref="TOTPOP" />
                <Argument name="min" value="%(pop_senate_min)s" />
                <Argument name="max" value="%(pop_senate_max)s" />
            </ScoreFunction>
            <ScoreFunction id="senate_plan_count_districts" type="plan" label="Count Districts" 
                calculator="publicmapping.redistricting.calculators.CountDistricts"
                description="The number of districts in a State Senate redistricting plan must be %(num_districts_senate)s .">
                <Argument name="target" value="%(num_districts_senate)s" />
            </ScoreFunction>
            <ScoreFunction id="house_plan_equipopulation" type="plan" label="Equipopulation" 
                calculator="publicmapping.redistricting.calculators.Equipopulation"
                description="The population of each House of Delegates district must be %(pop_house_max)s- %(pop_house_min)s">
                <SubjectArgument name="value" ref="TOTPOP" />
                <Argument name="min" value="%(pop_house_min)s"/>
                <Argument name="max" value="%(pop_house_max)s" />
            </ScoreFunction>
            <ScoreFunction id="house_plan_count_districts" type="plan" label="Count Districts" 
                calculator="publicmapping.redistricting.calculators.CountDistricts"
                description="The number of districts in a House of Delegates redistricting plan must be %(num_districts_house)s.">
                <Argument name="target" value="%(num_districts_house)s" />
            </ScoreFunction>           
        </ScoreFunctions>
     <ScorePanels>        
            <ScorePanel id="panel_equivalence_all" type="plan" template="leaderboard_panel_all.html" title="Equipopulation">
                <Score ref="plan_equivalence"/>            
	    </ScorePanel>
            <ScorePanel id="panel_schwartzberg_all" type="plan" template="leaderboard_panel_all.html" title="Average Compactness">
                <Score ref="plan_schwartzberg"/>
	    </ScorePanel>
                %(start_elec)s
            <ScorePanel id="panel_competitiveness_all" type="plan" template="leaderboard_panel_all.html" title="Competitiveness">
                <Score ref="plan_competitiveness"/>
	    </ScorePanel>
            <ScorePanel id="panel_repfairness_all" type="plan" template="leaderboard_panel_all.html" title="Representational Fairness">
                <Score ref="plan_repfairness"/>
	    </ScorePanel>
                %(end_elec)s
            <ScorePanel id="panel_equivalence_mine" type="plan" template="leaderboard_panel_ mine.html"	title="Equipopulation">
                <Score ref="plan_equivalence"/>
	    </ScorePanel>
            <ScorePanel id="panel_schwartzberg_mine" type="plan" template="leaderboard_panel_mine.html" title="Average Compactness">
                <Score ref="plan_schwartzberg"/>
	    </ScorePanel>
                %(start_elec)s
            <ScorePanel id="panel_competitiveness_mine" type="plan" template="leaderboard_panel_mine.html" title="Competitiveness">
                <Score ref="plan_competitiveness"/>
            </ScorePanel>
            <ScorePanel id="panel_repfairness_mine" type="plan" template="leaderboard_panel_mine.html" title="Representational Fairness">
                <Score ref="plan_repfairness"/>
            </ScorePanel>
                %(end_elec)s
        </ScorePanels>
        <ScoreDisplays>
            <ScoreDisplay legislativebodyref="congress" type="leaderboard"
                title="Congressional Leaderboard - All" cssclass="leaderboard congress">
                <ScorePanel ref="panel_equivalence_all" />
                <ScorePanel ref="panel_schwartzberg_all" />
                %(start_elec)s
                <ScorePanel ref="panel_competitiveness_all" />
                <ScorePanel ref="panel_repfairness_all" />
                %(end_elec)s            </ScoreDisplay>            <ScoreDisplay legislativebodyref="house" type="leaderboard"
                title="State House Leaderboard - All" cssclass="leaderboard house">
                <ScorePanel ref="panel_equivalence_all" />
                <ScorePanel ref="panel_schwartzberg_all" />
                %(start_elec)s
                <ScorePanel ref="panel_competitiveness_all" />
                <ScorePanel ref="panel_repfairness_all" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="senate" type="leaderboard"
                title="State Senate Leaderboard - All" cssclass="leaderboard senate">
                <ScorePanel ref="panel_equivalence_all" />
                <ScorePanel ref="panel_schwartzberg_all" />
                %(start_elec)s
                <ScorePanel ref="panel_competitiveness_all" />
                <ScorePanel ref="panel_repfairness_all" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="congress" type="leaderboard"
                title="Congressional Leaderboard - Mine" cssclass="leaderboard congress">
                <ScorePanel ref="panel_equivalence_mine" />
                <ScorePanel ref="panel_schwartzberg_mine" />
                %(start_elec)s
                <ScorePanel ref="panel_competitiveness_mine" />
                <ScorePanel ref="panel_repfairness_mine" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="house" type="leaderboard"
                title="State House Leaderboard - Mine" cssclass="leaderboard house">
                <ScorePanel ref="panel_equivalence_mine" />
                <ScorePanel ref="panel_schwartzberg_mine" />
                %(start_elec)s
                <ScorePanel ref="panel_competitiveness_mine" />
                <ScorePanel ref="panel_repfairness_mine" />
                %(end_elec)s
            </ScoreDisplay>
            <ScoreDisplay legislativebodyref="senate" type="leaderboard"
                title="State Senate Leaderboard - Mine" cssclass="leaderboard senate">
                <ScorePanel ref="panel_equivalence_mine" />
                <ScorePanel ref="panel_schwartzberg_mine" />
                %(start_elec)s
                <ScorePanel ref="panel_competitiveness_mine" />
                <ScorePanel ref="panel_repfairness_mine" />
                %(end_elec)s
            </ScoreDisplay>
        </ScoreDisplays>
    </Scoring>
   <Validation>
        <Criteria legislativebodyref="congress">
            <Criterion name="CountDistricts - Congress">
                <Score ref="congress_plan_count_districts" />
            </Criterion>
            <Criterion name="Equipopulation - Congress" description="&lt;p&gt;Your plan does not meet the competition criteria for Equipopulation:&lt;/p&gt;&lt;p&gt; The population of each Congressional district must be %(pop_congress_max)s-%(pop_congress_min)s">                
		<Score ref="congress_plan_equipopulation" />            
	    </Criterion>
            <Criterion name="MajorityMinority - Congress">
                <Score ref="plan_majority_minority" />
            </Criterion>
            <Criterion name="AllBlocksAssigned - Congress">
                <Score ref="plan_all_blocks_assigned" />
            </Criterion>
            <Criterion name="AllContiguous - Congress" description="&lt;p&gt;Your plan does not meet the competition criteria for Contiguity&lt;/p&gt;&lt;p&gt;Every part of a district must be reachable from every other part without crossing the district's borders. ">               
		 <Score ref="plan_all_contiguous" />
            </Criterion>
        </Criteria>
        <Criteria legislativebodyref="house">
            <Criterion name="CountDistricts - House">
                <Score ref="house_plan_count_districts" />
            </Criterion>
            <Criterion name="Equipopulation - House" description="&lt;p&gt;Your plan does not meet the competition criteria for Equipopulation:&lt;/p&gt;&lt;p&gt;The population of each House of Delegates district must be %(pop_house_min)s - %(pop_house_max)s">                
		<Score ref="house_plan_equipopulation" />            
	    </Criterion>            
	    <Criterion name="MajorityMinority - House">
                <Score ref="plan_majority_minority" />
            </Criterion>
            <Criterion name="AllBlocksAssigned - House">
                <Score ref="plan_all_blocks_assigned" />
            </Criterion>
            <Criterion name="AllContiguous - House" description="&lt;p&gt;Your plan does not meet the competition criteria for Contiguity&lt;/p&gt;&lt;p&gt;Every part of a district must be reachable from every other part without crossing the district's borders. All districts within a plan must be contiguous. ">                
		<Score ref="plan_all_contiguous" />
            </Criterion>
        </Criteria>
        <Criteria legislativebodyref="senate">            
	    <Criterion name="CountDistricts - Senate">
                <Score ref="senate_plan_count_districts" />
            </Criterion>
            <Criterion name="Equipopulation - Senate" description="&lt;p&gt;Your plan does not meet the competition criteria for Equipopulation:&lt;/p&gt;&lt;p&gt;The population of each State Senate district must be %(pop_house_min)s-%(pop_house_max)s">
                <Score ref="senate_plan_equipopulation" />
            </Criterion>
            <Criterion name="MajorityMinority - Senate">
                <Score ref="plan_majority_minority" />            
	    </Criterion>            
	    <Criterion name="AllBlocksAssigned - Senate">
                <Score ref="plan_all_blocks_assigned" />
            </Criterion>
            <Criterion name="AllContiguous - Senate" description="&lt;p&gt;Your plan does not meet the competition criteria for Contiguity&lt;/p&gt;&lt;p&gt;Every part of a district must be reachable from every other part without crossing the district's borders. ">
                <Score ref="plan_all_contiguous" />
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


    <GeoLevels>
      <GeoLevel id="block" name="block" min_zoom="8" sort_key="3" tolerance="2.5">

          <Shapefile path="/projects/publicmapping/data/census_blocks.shp">
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
              <GeoLevelCharacteristic ref="TOTPOP" />
              <GeoLevelCharacteristic ref="VAP" />
              <GeoLevelCharacteristic ref="VAP_B" />
              <GeoLevelCharacteristic ref="VAP_H" />
              <GeoLevelCharacteristic ref="VAP_NA" />
                %(start_elec)s
              <GeoLevelCharacteristic ref="VOTE_DEM" />
              <GeoLevelCharacteristic ref="VOTE_REP" />
              <GeoLevelCharacteristic ref="VOTE_TOT" />
                %(end_elec)s
          </GeoLevelCharacteristics>
     </GeoLevel>
      <GeoLevel id="tract" name="tract" min_zoom="4" sort_key="2" tolerance="25">
         <Files>
              <Geography path="/projects/publicmapping/data/census_tracts.dbf">
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
              <GeoLevelCharacteristic ref="TOTPOP" />
              <GeoLevelCharacteristic ref="VAP" />
              <GeoLevelCharacteristic ref="VAP_B" />
              <GeoLevelCharacteristic ref="VAP_H" />
              <GeoLevelCharacteristic ref="VAP_NA" />
                %(start_elec)s
              <GeoLevelCharacteristic ref="VOTE_DEM" />
              <GeoLevelCharacteristic ref="VOTE_REP" />
              <GeoLevelCharacteristic ref="VOTE_TOT" />
                %(end_elec)s
          </GeoLevelCharacteristics>
      </GeoLevel>

      <GeoLevel id="county" name="county" min_zoom="0" sort_key="1" tolerance="250">
          <Files>
              <Geography path="/projects/publicmapping/data/census_county.dbf">
                  <Fields>
                      <Field name="NAME10" type="name"/>
                      <Field name="GEOID10" type="portable"/>
                      <Field name="STATEFP10" type="tree" pos="0" width="2"/>
                      <Field name="COUNTYFP10" type="tree" pos="1" width="3"/>
                  </Fields>
              </Geography>
          </Files>
         <GeoLevelCharacteristics>
              <GeoLevelCharacteristic ref="TOTPOP" />
              <GeoLevelCharacteristic ref="VAP" />
              <GeoLevelCharacteristic ref="VAP_B" />
              <GeoLevelCharacteristic ref="VAP_H" />
              <GeoLevelCharacteristic ref="VAP_NA" />
               %(start_elec)s
              <GeoLevelCharacteristic ref="VOTE_DEM" />
              <GeoLevelCharacteristic ref="VOTE_REP" />
              <GeoLevelCharacteristic ref="VOTE_TOT" />
                %(end_elec)s
          </GeoLevelCharacteristics>
      </GeoLevel>
    </GeoLevels>

    <!--
    <Templates>
        <Template name="Congressional">
            <LegislativeBody ref="congress"/>
             <Blockfile path="/projects/publicmapping/data/cd111_index.csv" />
        </Template>
        <Template name="State House">
            <LegislativeBody ref="house"/>
            <Blockfile path="/projects/publicmapping/data/sldl10_index.csv" />
        </Template>
        <Template name="State Senate">
            <LegislativeBody ref="senate"/>
            <Blockfile path="/projects/publicmapping/data/sldu10_index.csv" />
        </Template>
    </Templates>
    -->

    <Project root="/projects/publicmapping/trunk" sessionquota="5" 
             sessiontimeout="15">
        <!-- Database connection information. -->
        <Database name="publicmapping" user="publicmapping" password="publicmapping"/>
        
        <!-- 
        
        Administrative user information. This should match the admin
        user created when the django project is created.
        
        -->
        <Admin user="admin" email="support@publicmapping.org"/>
        
        <!-- Configuration items specific to the 'redistricting' app. -->
       <Redistricting>      
	   <MapServer hostname="" ns="gmu" nshref="http://gmu.azavea.com/"
                adminuser="admin" adminpass="geoserver" maxfeatures="100" 
                styles="/projects/publicmapping/trunk/sld" />
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
                    shape="/projects/publicmapping/data/vablock_bard_save.Rdata" 
                    temp="/projects/publicmapping/local/reports"
                    transform="/projects/publicmapping/trunk/docs/bard_template.xslt">
                    <PopVars>
                        <PopVar subjectref="TOTPOP" threshold=".5" default="true" />
                        <PopVar subjectref="VAP" threshold=".1" />
                        <PopVar subjectref="VAP_B" threshold=".1" />
                        <PopVar subjectref="VAP_H" threshold=".1" default="false" />
                        <PopVar subjectref="VAP_NA" threshold=".1" default="false" />
                    </PopVars>
                    <RatioVars>
                        <!--
                        
                        Set up RatioVars for both ethnicity and political 
                        party.
                        
                        -->
                        <RatioVar id="racialComp" label="Majority Minority Districts" threshold=".5">
                            <Numerators>
                                <Numerator subjectref="TOTPOP_B" />
                                <Numerator subjectref="TOTPOP_H" />
                            </Numerators>
                            <Denominator subjectref="TOTPOP" />
                        </RatioVar>
                %(start_elec)s
                        <RatioVar id="partyControl" label="Party-Controlled Districts" threshold=".5">
                            <Numerators>
                                <Numerator subjectref="VOTE_DEM" />
                                <Numerator subjectref="VOTE_REP" />
                            </Numerators>
                            <Denominator subjectref="VOTE_TOT" />
                        </RatioVar>
                %(end_elec)s
                    </RatioVars>
                    <SplitVars>
                        <!-- 
                        
                        See whether a given district splits a geography.
                        This can be any higher level geography: a county,
                        VTd, or tract.
                        -->
                        <SplitVar field="COUNTYST10" label="County" />
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



def gen_config(num_districts_congress,num_districts_senate,num_districts_house,sum_TOTPOP,has_election_data=0,has_vtds=0) :
        start_elec="<!--"        
	end_elec="-->"
        midlevel="tract"
        midlevel_width="6"
        midlevel_var="TRACTCE10"        
	if (has_election_data==1) :
                start_elect=""
                end_elect=""       
	if (has_vtds==1) :                
		midlevel="vtds"
                midlevel_width="4"
                midlevel_var="VTDST10"        
	pop_congress_max = (sum_TOTPOP/float(num_districts_congress)) * 1.005
        pop_congress_min = (sum_TOTPOP/float(num_districts_congress)) * 0.995        
	pop_house_max = (sum_TOTPOP/float(num_districts_house)) * 1.1
        pop_house_min = (sum_TOTPOP/float(num_districts_house)) * 0.9        
	pop_senate_max = (sum_TOTPOP/float(num_districts_senate)) * 1.1
        pop_senate_min = (sum_TOTPOP/float(num_districts_senate)) * 0.9
        target_file = '/projects/publicmapping/trunk/docs/config_census_generated.xml'
        f = open(target_file,'w')
        f.write(str( Config_Template(start_elec=start_elec,end_elec=end_elec,num_districts_congress=num_districts_congress,num_districts_house=num_districts_house,num_districts_senate=num_districts_senate,pop_congress_max=pop_congress_max,pop_congress_min=pop_congress_min,pop_senate_max=pop_senate_max, pop_senate_min=pop_senate_min,pop_house_max=pop_house_max,pop_house_min=pop_house_min)))
        f.close()
        os.chmod(target_file,stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)    


###
### MAIN
###

#  Get Arguments

parser=optparse.OptionParser(usage="%prog -F[fips_code] -C[num_congressional_districts] -S[num_senate_districts] -H[num_house_districts]", version="%prog 0.1")
parser.add_option('-F','--fips', dest='stateFips',help="State two digit FIPS code", type=int, default=0)
parser.add_option('-C','--congdist', dest='congDis',help="number of congressional districts", type=int, default=0)
parser.add_option('-H', '--housedist',dest='senDis',help="number of senate districts", type=int, default=0)
parser.add_option('-S', '--sendist', dest='houseDis',help="number of house districts", type=int,default=0)

(parseResults,numargs)=parser.parse_args()
if len(numargs) != 0:
        parser.error("additional arguments ignored ")
stateFips = parseResults.stateFips
houseDis = parseResults.houseDis
senDis= parseResults.senDis
congDis= parseResults.congDis
if (stateFips==0 or houseDis==0 or senDis==0 or congDis==0):
        print "Must supply all arguments"
        raise ValueError

# install dependencies
print "installing dependencies..."
install_dependencies()

# generate generic sld files
print 'generating generic sld files ...'
gensld_none("county")
gensld_none("tract")
gensld_none("block")
gensld_boundaries("county")
gensld_boundaries("tract")
gensld_boundaries("block")

# Clear out DB
print 'clearing database ...'
clear_publicmapping_db()

# Retrieve data files
print 'retrieving census data ...'
get_census_data(stateFips)

# merge standard variables
# TODO: Refactor entirely in rpy
# NOTE: robject is returning 6-level quantiles, has_election_data, has_vtd, sum_TOTPOP
print 'merging data...'
robjects.r.source("/projects/publicmapping/trunk/docs/loadcensus/mergeCensus.R")
sum_TOTPOP= robjects.r.sum_TOTPOP[0]
has_election_data = robjects.r.has_election_data

# TODO: refactor as matrix of varnames and geographies
print 'generating choropleth slds ...'
gensld_choro("block","TOTPOP","Total Population",robjects.r.q_block_TOTPOP)
gensld_choro("block","TOTPOP_H","Total Hispanic Population",robjects.r.q_block_TOTPOP_H)
gensld_choro("block","TOTPOP_B","Total Black Population",robjects.r.q_block_TOTPOP_B)
gensld_choro("block","TOTPOP_NA","Total Native American Population",robjects.r.q_block_TOTPOP_NA)
gensld_choro("block","VAP","Voting Age Population",robjects.r.q_block_VAP)
gensld_choro("block","VAP_H","Voting Age Hispanic Population",robjects.r.q_block_VAP_H)
gensld_choro("block","VAP_B","Voting Age Black Population",robjects.r.q_block_VAP_B)
gensld_choro("block","VAP_NA","Voting Age Native American Population",robjects.r.q_block_VAP_NA)
if (has_election_data==1) :        
	gensld_choro("block","VOTE_DEM","Predicted Democratic Vote ",robjects.r.q_block_VOTE_DEM)        
	gensld_choro("block","VOTE_REP","Predicted Republican Vote ",robjects.r.q_block_VOTE_REP)
        gensld_choro("block","VOTE_TOT","Predicted Republican Vote ",robjects.r.q_block_VOTE_TOT)
gensld_choro("tract","TOTPOP","Total Population",robjects.r.q_tract_TOTPOP)
gensld_choro("tract","TOTPOP_H","Total Hispanic Population",robjects.r.q_tract_TOTPOP_H)
gensld_choro("tract","TOTPOP_B","Total Black Population",robjects.r.q_tract_TOTPOP_B)
gensld_choro("tract","TOTPOP_NA","Total Native American Population",robjects.r.q_tract_TOTPOP_NA)
gensld_choro("tract","VAP","Voting Age Population",robjects.r.q_tract_VAP)
gensld_choro("tract","VAP_H","Voting Age Hispanic Population",robjects.r.q_tract_VAP_H)
gensld_choro("tract","VAP_B","Voting Age Black Population",robjects.r.q_tract_VAP_B)
gensld_choro("tract","VAP_NA","Voting Age Native American Population",robjects.r.q_tract_VAP_NA)
if (has_election_data==1) :
        gensld_choro("tract","VOTE_DEM","Predicted Democratic Vote ",robjects.r.q_tract_VOTE_DEM)
        gensld_choro("tract","VOTE_REP","Predicted Republican Vote ",robjects.r.q_tract_VOTE_REP)
        gensld_choro("tract","VOTE_TOT","Predicted Republican Vote ",robjects.r.q_tract_VOTE_TOT)
gensld_choro("county","TOTPOP","Total Population",robjects.r.q_county_TOTPOP)
gensld_choro("county","TOTPOP_H","Total Hispanic Population",robjects.r.q_county_TOTPOP_H)
gensld_choro("county","TOTPOP_B","Total Black Population",robjects.r.q_county_TOTPOP_B)
gensld_choro("county","TOTPOP_NA","Total Native American Population",robjects.r.q_county_TOTPOP_NA)
gensld_choro("county","VAP","Voting Age Population",robjects.r.q_county_VAP)
gensld_choro("county","VAP_H","Voting Age Hispanic Population",robjects.r.q_county_VAP_H)
gensld_choro("county","VAP_B","Voting Age Black Population",robjects.r.q_county_VAP_B)
gensld_choro("county","VAP_NA","Voting Age Native American Population",robjects.r.q_county_VAP_NA)
if (has_election_data==1) :
        gensld_choro("county","VOTE_DEM","Predicted Democratic Vote ",robjects.r.q_county_VOTE_DEM)
        gensld_choro("county","VOTE_REP","Predicted Republican Vote ",robjects.r.q_county_VOTE_REP)
        gensld_choro("county","VOTE_TOT","Predicted Republican Vote ",robjects.r.q_county_VOTE_TOT)


# generate config file
print 'generating config file ... '
gen_config(num_districts_congress=congDis,num_districts_senate=senDis,num_districts_house=houseDis,sum_TOTPOP=sum_TOTPOP,has_election_data=has_election_data,has_vtds=0) 

print '\n\n*** Now run: ***\n\n'
print '(cd /projects/publicmapping/trunk/django/publicmapping/; python setup.py -D /projects/publicmapping/trunk/docs/config.xsd  /projects/publicmapping/trunk/docs/config_census_generated.xml)'



