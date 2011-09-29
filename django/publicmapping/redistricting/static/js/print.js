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
        }, options);

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
        };

        $(document.body).bind('mapready',_init);

        return _self;
    };

    _self.doprint = function() {
        var geolevel = null,
            districts = [],
            disturl = 'pmp:simple_district', // needs bbox, srs, height, width
            geogurl = '',
            osmurl = 'http://staticmap.openstreetmap.de/staticmap.php?maptype=mapnik', // needs center, zoom, size
            sz = _options.map.getExtent(),
            cen = sz.getCenterLonLat(),
            sz_array = sz.toArray(),
            zoom = 0,
            res = 1;
        $.each(_options.map.getLayersBy('CLASS_NAME','OpenLayers.Layer.WMS'),function(idx, item){
            if (item.getVisibility()) {
                geolevel = item;
            }
        });
        districts = $.map(_options.districtLayer.features,function(item, idx){
            return 'id='+item.fid;
        });
        // pad out dimensions to keep from distorting result map
        if (sz.getWidth()/sz.getHeight() < _options.width/_options.height) {
            // sz_array height needs to be smaller
            var new_h = sz.getWidth() * _options.height / _options.width;
            sz_array[1] = cen.lat - new_h / 2.0;
            sz_array[3] = cen.lat + new_h / 2.0;
        }
        else if (sz.getWidth()/sz.getHeight() > _options.width/_options.height) {
            // sz_array width needs to be smaller
            var new_w = sz.getHeight() * _options.width / _options.height;
            sz_array[0] = cen.lon - new_w / 2.0;
            sz_array[2] = cen.lon + new_w / 2.0;
        }
        var params = OpenLayers.Util.extend({}, geolevel.params);
        delete params.TILES;
        delete params.TILESORIGIN;
        params.HEIGHT = _options.height;
        params.WIDTH = _options.width;
        params.BBOX = sz_array.join(',');
        geogurl = geolevel.getFullRequestString(params).replace(new RegExp('gwc/service/'),'');

        console.log(geogurl);

        params.LAYERS = disturl;
        params.CQL=districts.join('%20or%20');
        disturl = geolevel.getFullRequestString(params).replace(new RegExp('gwc/service/'),'');

        console.log(disturl);

        cen.transform(new OpenLayers.Projection('EPSG:900913'),new OpenLayers.Projection('EPSG:4326'));
        while (_options.map.getResolution() * res < 156543.0339) {
            zoom++;
            res *= 2;
        }
        osmurl += '&center=' + cen.lat + ',' + cen.lon
        osmurl += '&zoom=' + zoom;
        osmurl += '&size=' + _options.width + 'x' + _options.height;

        console.log(osmurl);

        $(document.body).append('<form id="printForm" method="POST" action="../print/">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + $('#csrfmiddlewaretoken').val() + '"/>' +
            '<input type="hidden" name="height" value="' + _options.height + '"/>' +
            '<input type="hidden" name="width" value="' + _options.width + '"/>' +
            '<input type="hidden" name="basemap" value="' + osmurl + '"/>' +
            '<input type="hidden" name="geography" value="' + geogurl + '"/>' +
            '<input type="hidden" name="districts" value="' + disturl + '"/>' +
            '</form>');
        $('#printForm').submit();
    };

    return _self;
};

