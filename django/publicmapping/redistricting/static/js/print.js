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

    _self.styletracker = function(event, style, layername) {
        console.log('tracking style for '+layername);
        _styleCache[layername] = style;
    };

    _self.doprint = function() {
        var geolevel = null,
            disturl = '',
            geogurl = '',
            geolyr = '',
            legend = [],
            sz = _options.map.getExtent(),
            cen = _options.map.getCenter(),
            uStyle = null,
            sld = null,
            fmt = new OpenLayers.Format.SLD(),
            legendfmt = new OpenLayers.Format.JSON();
        // get the visible geolevel
        $.each(_options.map.getLayersBy('CLASS_NAME','OpenLayers.Layer.WMS'),function(idx, item){
            if (item.getVisibility()) {
                geolevel = item;
            }
        });

        console.log('Style cache for geography: ' + _styleCache[geolevel.name]);
        $.each(_styleCache[geolevel.name].rules, function(idx, item) {
            if (item.symbolizer.Polygon != null) {
                legend.push({
                    title: item.title,
                    fillColor: item.symbolizer.Polygon.fillColor,
                    strokeColor: item.symbolizer.Polygon.strokeColor,
                    strokeWidth: item.symbolizer.Polygon.strokeWidth
                });
            }
            else if (item.symbolizer.Line != null) {
                $.each(legend, function(idx, litem) {
                    litem.strokeColor = item.symbolizer.Line.strokeColor;
                    litem.strokeWidth = item.symbolizer.Line.strokeWidth;
                });
            }
        });

        // get the base URL for the geographic WMS
        geogurl = geolevel.url;
        // get the name of the geographic layer
        geolyr = geolevel.params.LAYERS;

        dlstart = legend.length;
        console.log('Style cache for districts: ' + _styleCache[_options.districtLayer.name]);
        $.each(_styleCache[_options.districtLayer.name].rules, function(idx, item) {
            if (item.symbolizer.Polygon != null) {
                legend.push({
                    title: item.title,
                    fillColor: item.symbolizer.Polygon.fillColor,
                    strokeColor: item.symbolizer.Polygon.strokeColor,
                    strokeWidth: item.symbolizer.Polygon.strokeWidth
                });
            }
            else if (item.symbolizer.Line != null) {
                $.each(legend, function(idx, litem){
                    if (idx < dlstart) { return; }
                    litem.strokeColor = item.symbolizer.Line.strokeColor;
                    litem.strokeWidth = item.symbolizer.Line.strokeWidth;
                });
            }
        });

        disturl = geolevel.url;
        var lyrRE = new RegExp('^(.*):demo_(.*)_.*$');
        $.each(_options.map.getLayersBy('visibility',true),function(idx, item){
            if (lyrRE.test(item.name)) {
                distlyr = RegExp.$1 + ':simple_district_' + RegExp.$2;
            }
        });

        // needs the reference layer, too!

        uStyle = OpenLayers.Util.extend({},_options.districtLayer.styleMap.styles['default']);
        uStyle.layerName = _options.districtLayer.name;
        var mapRules = [];
        var legendRules = [];
        var labeled = false;
        $.each(uStyle.rules, function(ridx, ruleItem){
            var fids = [];
            $.each(_options.districtLayer.features, function(fidx, featureItem) {
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
                            label:featureItem.attributes.name,
                            fontFamily: ffam,
                            fontWeight: fwht,
                            fontSize: fsz,
                            fillColor: fclr,
                            fillOpacity: 1.0
                        })}
                    });
                    mapRules.push(lblRule);
                }
            });
            labeled = true;
            if (fids.length > 0) {
                var myStyle = { Polygon: OpenLayers.Util.extend({}, uStyle.defaultStyle) },
                    subFilters = [],
                    myRule = null;
                myStyle = OpenLayers.Util.extend(myStyle, ruleItem.symbolizer);
                if (myStyle.Polygon.fillColor) {
                    myStyle.Polygon.fillColor = colorToHex(myStyle.Polygon.fillColor);
                }
                for (var i = 0; i < fids.length; i++) {
                    subFilters.push( new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.EQUAL_TO,
                        property: 'id',
                        value: fids[i]
                    }));
                }
                myRule = new OpenLayers.Rule({
                    title: ruleItem.title,
                    filter: new OpenLayers.Filter.Logical({
                        type: OpenLayers.Filter.Logical.OR,
                        filters: subFilters
                    }),
                    symbolizer: myStyle
                });
                mapRules.push(myRule);
                if (ruleItem.title !== null && ruleItem.title !='') {
                    legendRules.push(myRule);
                }
            }
        });
        delete uStyle.defaultStyle;

        var x = Sha1.hash(new Date().toString());

        uStyle.rules = mapRules;
        sld = { namedLayers: {}, version: '1.0.0' };
        sld.namedLayers[distlyr] = {
            name: distlyr,
            userStyles: [ uStyle ],
            namedStyles: []
        };

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

        $(document.body).append('<form id="printForm" method="POST" action="../print/?x='+x+'" target="_blank">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + $('#csrfmiddlewaretoken').val() + '"/>' +
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
            '<textarea name="sld" style="display:none;">' + fmt.write(sld) + '</textarea>' +
            '</form>');

        $('#printForm').submit();
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

