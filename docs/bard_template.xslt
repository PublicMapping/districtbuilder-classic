<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output omit-xml-declaration="yes" indent="yes" output="text/html" />
<xsl:key name="subject" match="//Subject" use="@id" />
<xsl:param name="legislativebody" />

<xsl:template match="/DistrictBuilder">
    <xsl:choose>
        <xsl:when test="//BardBodyConfig[@legislativebodyref=$legislativebody]">
            <xsl:for-each select="//BardBodyConfig">
                <xsl:choose>
                    <xsl:when test="@legislativebodyref=$legislativebody">
                        <xsl:apply-templates select="//BardConfig[@id=current()/@bardconfigref]" />
                    </xsl:when>
                </xsl:choose>
            </xsl:for-each>
        </xsl:when>
        <xsl:otherwise>
            <div id="reportdescription">
                <div id="description">
                   <h3>Sorry, no reports for this legislative body</h3>
                    <p>Reports are not enabled for this legislative body.</p>
                </div>
            </div>
        </xsl:otherwise>
    </xsl:choose>
</xsl:template>

<xsl:template match="BardConfig">
        <div id="reportdescription">
            <div id="description">
               <h3> Introduction to the reporting tool</h3>
                <p>Select the plan statistics you'd like included in a comprehensive report on your redistricting plan. After you've made your selections click "Create and Preview Report" to view the final report.</p>
            </div>
            <div id="options">
                <div id="options1">
                    <xsl:apply-templates select="./PopVars" />
                    <span class="compactness master" ><input id="compactness_master" type="checkbox" /><label for="compactness_master">Compactness</label></span>
                    <span class="compactness child reportVar"><input id="repCompactness" type="checkbox" value="repCompactness" /><label for="repCompactness">Compactness - Length/Width</label></span>
                    <!--<span class="compactness child reportVar"><input id="repCompactnessExtra" type="checkbox" value="repCompactnessExtra" /><label for="repCompactnessExtra">Compactness - Bounding Circle</label></span>-->
                    <span class="spatial master" ><input id="spatial_master" type="checkbox" /><label for="spatial_master">Spatial Analysis</label></span>
                    <!--<span class="spatial child reportVar"><input id="repSpatialExtra" type="checkbox" value="repSpatialExtra" /><label for="repSpatialExtra">Contiguity</label></span>-->
                    <span class="spatial child reportVar"><input id="repSpatial" type="checkbox" value="repSpatial" /><label for="repSpatial">Unassigned Blocks</label></span>
                </div>
                <div id="options2">
                    <xsl:apply-templates select="./RatioVars" />
                    <xsl:apply-templates select="./SplitVars" />
                </div>
            </div>
        </div>
        <div id="reportPreviewContainer">
            <div id="reportPreview" class="report">
                <xsl:comment>This div intentionally left blank</xsl:comment>
            </div>
        </div>
		<div id="reportButtons">
            <button id="btnPreviewReport">Create and Preview Report</button>
        </div>

</xsl:template>

<xsl:template match="PopVars">
    <span class="popVarExtra master" ><input id="popVarExtra_master" type="checkbox" /><label for="popVarExtra_master">Population</label></span>
    <xsl:for-each select="PopVar">
        <xsl:variable name="subjectfield" select="key('subject', @subjectref)/@field" />
        <xsl:variable name="subjectname" select="key('subject', @subjectref)/@name" />
        <xsl:choose>
            <xsl:when test="@default='true'">
                <input type="hidden" id = "popVar" value="{$subjectname}|{$subjectfield}^tolerance|{@threshold}" />
            </xsl:when>
            <xsl:otherwise>
                <span class="popVarExtra child reportVar" ><input id="pop_{$subjectfield}" type="checkbox"  value="{$subjectfield}" /><label for="pop_{$subjectfield}"><xsl:value-of select="$subjectname" /></label></span>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:for-each>
</xsl:template>

<xsl:template match="RatioVars">
    <xsl:for-each select="RatioVar">
            <input type="hidden" id="{@id}" value="{@id}" class="ratioVar" />
            <span class="{@id} master" ><input id="{@id}_master" type="checkbox" /><label for="{@id}_master"><xsl:value-of select="@label" /></label></span>
            <xsl:variable name="denominatorfield" select="key('subject', ./Denominator/@subjectref)/@field" />
            <xsl:variable name="denominatorname" select="key('subject',  ./Denominator/@subjectref)/@name" />
            <input type="hidden" id="{@id}Denominator" value="{$denominatorname}|{$denominatorfield}" />
            <input type="hidden" id="{@id}Threshold">
                <xsl:attribute name="value">
                    <xsl:value-of select="@threshold" />
                </xsl:attribute>
            </input>
            
            <xsl:for-each select="Numerators/Numerator">
                <xsl:variable name="parentid" select="../../@id" />
                <xsl:variable name="subjectfield" select="key('subject', @subjectref)/@field" />
                <xsl:variable name="subjectname" select="key('subject', @subjectref)/@name" />

                <span class="{$parentid} child reportVar"><input id="ratio_{$subjectfield}" type="checkbox" value="{$subjectfield}" /><label for="ratio_{$subjectfield}"><xsl:value-of select="$subjectname" /></label></span>

            </xsl:for-each>
    </xsl:for-each>
</xsl:template>

<xsl:template match="SplitVars">
        <span class="splitVar master" ><input id="splitVar_master" type="checkbox" /><label for="splitVar_master">Split Geographies</label></span>
    <xsl:for-each select="SplitVar">
        <span class="splitVar child reportVar" ><input id="split_{@field}" type="checkbox" value = "{@field}" /><label for="split_{@field}"><xsl:value-of select="@label" /> Splits</label></span>
    </xsl:for-each>
</xsl:template>

</xsl:stylesheet>
