/*
   Copyright 2011 Micah Altman, Michael McDonald

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

   This file is part of The Public Mapping Project
   https://github.com/PublicMapping/

   Purpose:
       This script file defines behaviors of the 'Choose Plan' dialog.
   
   Author: 
        Andrew Jennings, David Zwarg
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * printing the current map view.
 *
 * Parameters:
 *   options -- Configuration options for the print layout.
 */
printplan = function(options) {

    var _self = {},
        _options = $.extend({
            plan: 0,
            target: document.body,
            map: null,
            height: 500,
            width: 1024
        }, options),
        _styleCache = {};

    /**
     * Initialize the print button. Setup the click event for the target to
     * show the print page.
     *
     * Returns:
     *   The print button.
     */
    _self.init = function() {
        var _init = function(evt, map) {
            _options.target.click(_self.doprint);

            _options.map = map;
            _options.districtLayer = map.getLayersByName('Current Plan')[0];

            $(map.div).bind('style_changed',{type:'district'},_self.styletracker);
        };

        $(document.body).bind('mapready',_init);

        $(_options.target).button({icons: {primary:'ui-icon'}});

        return _self;
    };

    /**
     * Track the style changes to the layers, and cache the JSON-ified SLDs.
     */
    _self.styletracker = function(event, style, layername) {
        _styleCache[layername] = style;
    };

    /**
     * Print the current map view.
     */
    _self.doprint = function() {
        var geolevel = null,
            disturl = '',
            distlyr = '',
            geogurl = '',
            geolyr = '',
            legend = {
                geotitle:'',
                geo:[],
                disttitle:'',
                dist:[]
            },
            sz = _options.map.getExtent(),
            cen = _options.map.getCenter(),
            uStyle = null,
            sld = null,
            district_sld = null,
            label_sld = null,
            fmt = new OpenLayers.Format.SLD(),
            legendfmt = new OpenLayers.Format.JSON(),
            // regexp grouping:
            //   $1 = namespace
            //   $2 = region
            //   $3 = geography
            //   $4 = demographic
            lyrRE = new RegExp('^(.*):demo_([^_]*)_([^_]*)(_([^_]*))?$'),
            // the collection of rules for this area-part of the district
            areaRules = [],
            // the collection of rules for this border(+label) part of the district
            lineRules = [],
            labeled = false;

        // get the visible geolevel
        $.each(_options.map.getLayersBy('CLASS_NAME','OpenLayers.Layer.WMS'),function(idx, item){
            if (item.getVisibility()) {
                geolevel = item;
            }
        });

        // iterate over the rules of the geolevel style cache,
        // adding the polygon styles first, then appending the
        // line style to all features
        $.each(_styleCache[geolevel.name].rules, function(idx, item) {
            if (item.symbolizer.Polygon != null) {
                legend.geo.push({
                    title: item.title,
                    fillColor: item.symbolizer.Polygon.fillColor,
                    strokeColor: item.symbolizer.Polygon.strokeColor,
                    strokeWidth: item.symbolizer.Polygon.strokeWidth
                });
            }
            else if (item.symbolizer.Line != null) {
                if (legend.geo.length == 0) {
                    legend.geo.push({
                        title:item.title,
                        fillColor: '#eeeeee',
                        strokeColor: item.symbolizer.Line.strokeColor,
                        strokeWidth: item.symbolizer.Line.strokeWidth
                    });
                }
                else {
                    $.each(legend.geo, function(idx, litem) {
                        litem.strokeColor = item.symbolizer.Line.strokeColor;
                        litem.strokeWidth = item.symbolizer.Line.strokeWidth;
                    });
                }
            }
        });

        // get the base URL for the geographic WMS
        geogurl = geolevel.url;
        // get the name of the geographic layer
        geolyr = geolevel.params.LAYERS;
        // get the title of the geographic style layer
        legend.geotitle = _styleCache[geolevel.name].title;

        // iterate over the rules of the district style cache,
        // adding the polygon styles, which contain the borders, too
        $.each(_styleCache[_options.districtLayer.name].rules, function(idx, item) {
            if (item.symbolizer.Polygon != null) {
                legend.dist.push({
                    title: item.title,
                    fillColor: item.symbolizer.Polygon.fillColor,
                    strokeColor: item.symbolizer.Polygon.strokeColor,
                    strokeWidth: item.symbolizer.Polygon.strokeWidth
                });
            }
        });

        // begin constructing a full SLD for the district layer
        uStyle = OpenLayers.Util.extend({},_options.districtLayer.styleMap.styles['default']);
        uStyle.layerName = _options.districtLayer.name;

        // if the 'none' style is selected, there will be no polygon styles
        // for the district, so pull them out of the default style
        if (legend.dist.length == 0) {
            legend.dist.push({
                title: 'Boundary',
                fillColor: '#eeeeee',
                strokeColor: uStyle.defaultStyle.strokeColor,
                strokeWidth: uStyle.defaultStyle.strokeWidth
            });
        }

        // reconstitute the geoserver name of the district layer
        disturl = geolevel.url;
        $.each(_options.map.getLayersBy('visibility',true),function(idx, item){
            if (lyrRE.test(item.name)) {
                distlyr = RegExp.$1 + ':simple_district_' + RegExp.$2 + '_' + RegExp.$3;
            }
        });

        // get the title of the district style layer
        legend.disttitle = _styleCache[_options.districtLayer.name].title;

        // for each rule in the district layer user style
        $.each(uStyle.rules, function(ridx, ruleItem){
            var fids = [];
            // for each feature in the district layer
            $.each(_options.districtLayer.features, function(fidx, featureItem) {
                // if the rule applies to the feature, store the feature id
                if (ruleItem.evaluate(featureItem)) {
                    fids.push(featureItem.fid);
                }
                if (!labeled) {
                    var lblFilter = new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.EQUAL_TO,
                        property: 'id',
                        value: featureItem.fid
                    });
                    var defStyle = featureItem.layer.styleMap.styles['default'].defaultStyle,
                        ffam = defStyle.fontFamily,
                        fwht = defStyle.fontWeight,
                        fsz = defStyle.fontSize,
                        fclr = defStyle.fontColor;
                    // process the font stuff a little
                    ffam = ffam.split(',')[0];
                    fwht = (fwht > 100) ? 'bold' : 'normal';
                    fsz = new RegExp('.*pt$').test(fsz) ? convertPtToPx(fsz) : fsz;
                    var lblRule = new OpenLayers.Rule({
                        filter: lblFilter,
                        symbolizer: { Text: new OpenLayers.Symbolizer.Text({
                            label:featureItem.attributes.label,
                            fontFamily: ffam,
                            fontWeight: fwht,
                            fontSize: fsz,
                            fillColor: fclr,
                            fillOpacity: 1.0
                        })}
                    });
                    lineRules.push(lblRule);
                }
            });
            labeled = true;
            if (fids.length > 0) {
                var myAreaStyle = { Polygon: OpenLayers.Util.extend({}, uStyle.defaultStyle) },
                    myLineStyle = { Line: OpenLayers.Util.extend({}, uStyle.defaultStyle) },
                    subFilters = [],
                    myRule = null;
                myAreaStyle = OpenLayers.Util.extend(myAreaStyle, ruleItem.symbolizer);
                myLineStyle = OpenLayers.Util.extend(myLineStyle, ruleItem.symbolizer);
                if (myAreaStyle.Polygon.fillColor) {
                    // convert the rgb() colors to #... notation
                    myAreaStyle.Polygon.fillColor = colorToHex(myAreaStyle.Polygon.fillColor);
                }
                if (myLineStyle.Line.strokeColor) {
                    // convert the rgb() colors to #... notation
                    myLineStyle.Line.strokeColor = colorToHex(myLineStyle.Line.strokeColor);
                }
                for (var i = 0; i < fids.length; i++) {
                    subFilters.push( new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.EQUAL_TO,
                        property: 'id',
                        value: fids[i]
                    }));
                }
                // create a rule for the features that match this rule
                myAreaRule = new OpenLayers.Rule({
                    title: ruleItem.title,
                    filter: new OpenLayers.Filter.Logical({
                        type: OpenLayers.Filter.Logical.OR,
                        filters: subFilters
                    }),
                    symbolizer: myAreaStyle
                });
                areaRules.push(myAreaRule);

                // create a rule for the features that match this rule
                myLineRule = new OpenLayers.Rule({
                    title: ruleItem.title,
                    filter: new OpenLayers.Filter.Logical({
                        type: OpenLayers.Filter.Logical.OR,
                        filters: subFilters
                    }),
                    symbolizer: myLineStyle
                });
                lineRules.push(myLineRule);
            }
        });
        delete uStyle.defaultStyle;

        // construct the full userstyle
        uStyle.rules = areaRules;
        sld = { namedLayers: {}, version: '1.0.0' };
        sld.namedLayers[distlyr] = {
            name: distlyr,
            userStyles: [ uStyle ],
            namedStyles: []
        };
        // serialize to a string variable
        district_sld = fmt.write(sld);

        // construct the full userstyle
        uStyle.rules = lineRules;
        sld = { namedLayers: {}, version: '1.0.0' };
        sld.namedLayers[distlyr] = {
            name: distlyr,
            userStyles: [ uStyle ],
            namedStyles: []
        }
        // serialize to a string variable
        label_sld = fmt.write(sld);

        // the area district layer SLD now lives in 'district_sld'
        // the line district layer SLD now lives in 'label_sld'

        // pad out dimensions to keep from distorting result map
        if (sz.getWidth()/sz.getHeight() < _options.width/_options.height) {
            // sz_array height needs to be smaller
            var new_h = sz.getWidth() * _options.height / _options.width;
            sz.bottom = cen.lat - new_h / 2.0;
            sz.top = cen.lat + new_h / 2.0;
        }
        else if (sz.getWidth()/sz.getHeight() > _options.width/_options.height) {
            // sz_array width needs to be smaller
            var new_w = sz.getHeight() * _options.width / _options.height;
            sz.left = cen.lon - new_w / 2.0;
            sz.right = cen.lon + new_w / 2.0;
        }

        // POST all these items to the printing endpoint
        $(document.body).append('<form id="printForm" method="POST" action="../print/" target="_blank">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + $('input[name=csrfmiddlewaretoken]').val() + '"/>' +
            '<input type="hidden" name="plan_id" value="' + PLAN_ID + '"/>' +
            '<input type="hidden" name="height" value="' + _options.height + '"/>' +
            '<input type="hidden" name="width" value="' + _options.width + '"/>' +
            '<input type="hidden" name="geography_url" value="' + geogurl + '"/>' +
            '<input type="hidden" name="geography_lyr" value="' + geolyr + '"/>' +
            '<input type="hidden" name="district_url" value="' + disturl + '"/>' +
            '<input type="hidden" name="district_lyr" value="' + distlyr + '"/>' +
            '<input type="hidden" name="bbox" value="' + sz.toBBOX() + '"/>' +
            '<input type="hidden" name="opacity" value="' + _options.districtLayer.opacity + '"/>' +
            '<textarea name="legend" style="display:none;">' + legendfmt.write(legend) + '</textarea>' +
            '<textarea name="district_sld" style="display:none;">' + district_sld + '</textarea>' +
            '<textarea name="label_sld" style="display:none;">' + label_sld + '</textarea>' +
            '</form>');

        // submit the form
        $('#printForm').submit();

        // remove the form from the document, so you can print more than once
        $('#printForm').remove();
    };

    var convertPtToPx = function(str) {
        var pts = parseInt(str,10), px = 0;
        pts -= 6;
        px = pts / 0.75;
        px += 8;
        px *= 2; // superscale
        return px.toFixed(1);
    };

    var colorToHex = function(color) {
        if (color.substr(0, 1) === '#') {
            return color;
        }
        var digits = /(.*?)rgb\((\d+), (\d+), (\d+)\)/.exec(color);
                                    
        var red = parseInt(digits[2]);
        var green = parseInt(digits[3]);
        var blue = parseInt(digits[4]);
                                                    
        var rgb = blue | (green << 8) | (red << 16);
        var str = rgb.toString(16);
        while (str.length < 6) { str = '0' + str; }
        return '#' + str;
    };

    return _self;
};

