/*
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

   This file is part of The Public Mapping Project
   http://sourceforge.net/projects/publicmapping/

   Purpose:
       This script file creates the map and controls all behaviors of the
       editing tools.
   
   Author: 
        Andrew Jennings, David Zwarg
*/

/*
 * Create an OpenLayers.Layer.WMS type layer.
 *
 * @param name The name of the layer (appears in the layer switcher).
 * @param layer The layer name (or array of names) served by the WMS server
 * @param extents The extents of the layer -- must be used for GeoWebCache.
 */
function createLayer( name, layer, srs, extents, transparent, visibility, isBaseLayer ) {
    return new OpenLayers.Layer.WMS( name,
        window.location.protocol + '//' + MAP_SERVER + '/geoserver/gwc/service/wms',
        {
          srs: srs,
          layers: layer,
          tiles: 'true',
          tilesOrigin: extents.left + ',' + extents.bottom,
          format: 'image/png',
          transparent: transparent
        },
        {
            visibility: visibility,
            isBaseLayer: isBaseLayer,
            displayOutsideMaxExtent: true
        }
    );
}

/* 
 * Get the value of the "Show Layer by:" dropdown.
 */
function getShowBy() {
    return $('#showby').val();
}

/*
 * Get the value of the "Show Boundaries:" dropdown.
 */
function getBoundLayer() {
    return $('#boundfor').val();
}

/*
 * Get the value of the "Show Districts by:" dropdown. This returns
 * an object with a 'by' and 'modified' property, since the selection
 * of this dropdown may also be 'None', 'Compactness' or 'Contiguity'
 *  but for performance and query reasons, the subject ID may not be empty.
 */
function getDistrictBy() {
    var orig = $('#districtby').val();
    var mod = new RegExp('^(.*)\.(None|Compactness|Contiguity)').test(orig);
    if (mod) {
        orig = RegExp.$1;
        mod = RegExp.$2;
    }
    return { by: orig, modified: mod }; 
}

/**
 * Get the value of the history cursor.
 */
function getPlanVersion() {
    var ver = $('#history_cursor').val();
    return ver;
}


/*
 * The URLs for updating the calculated geography and demographics.
 */
var geourl = '/districtmapping/plan/' + PLAN_ID + '/geography';
var demourl = '/districtmapping/plan/' + PLAN_ID + '/demographics';

/**
 * Get the OpenLayers filters that describe the version and subject
 * criteria for the district layer.
 */
function getVersionAndSubjectFilters() {
    var dby = getDistrictBy();
    var ver = getPlanVersion();
    return new OpenLayers.Filter.Logical({
        type: OpenLayers.Filter.Logical.AND,
        filters: [
            new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'version',
                value: ver
            }),
            new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'subject',
                value: dby.by
            })
        ]
    });
}

/**
 * Add proper class names so css may style the PanZoom controls.
 */
function doMapStyling() {
    $('#OpenLayers\\.Control\\.PanZoomBar_3_panup').addClass('olControlPan olControlPanUpItemInactive');
    $('#OpenLayers\\.Control\\.PanZoomBar_3_panright').addClass('olControlPan olControlPanRightItemInactive');
    $('#OpenLayers\\.Control\\.PanZoomBar_3_pandown').addClass('olControlPan olControlPanDownItemInactive');    
    $('#OpenLayers\\.Control\\.PanZoomBar_3_panleft').addClass('olControlPan olControlPanLeftItemInactive');
    $('#OpenLayers\\.Control\\.PanZoomBar_3_zoomin').addClass('olControlZoom olControlZoomInInactive');   
    $('#OpenLayers\\.Control\\.PanZoomBar_3_zoomout').addClass('olControlZoom olControlZoomOutInactive'); 
    $('#OpenLayers\\.Control\\.PanZoomBar_3_OpenLayers\\.Map_5').addClass('olControlZoom olControlZoomGrabInactive'); 
    $('#OpenLayers_Control_PanZoomBar_ZoombarOpenLayers\\.Map_5').addClass('olControlZoom olControlZoomBarInactive');
}

/*
 * Resize the map. This is a fix for IE 7, which does not assign a height
 * to the map div if it is not explicitly set.
 */
function initializeResizeFix() {
    var vp = $('.olMapViewport')[0];
    if( vp.clientHeight > 0 ) {
        return;
    }

    var resizemap = function() {
        var mapElem = $('#mapandmenu')[0]
        if(!window.innerHeight) {
            mapElem.style.height = (window.document.body.clientHeight - 90) + 'px';
            vp.style.height = (window.document.body.clientHeight - 150) + 'px';
        }
    };
   
    resizemap();
    window.onresize = resizemap;
}

/* 
 * Create a div for tooltips on the map itself; this is used
 * when the info tool is activated.
 */
function createMapTipDiv() {
    var tipdiv = document.createElement('div');
    var tipelem = document.createElement('h1');
    tipelem.appendChild(document.createTextNode(BODY_MEMBER+'Name'));
    tipdiv.appendChild(tipelem);
    tipelem = document.createElement('div');
    tipelem.id = 'tipclose';
    tipelem.onclick = function(e){
        OpenLayers.Event.stop(e || event);
        tipdiv.style.display = 'none';
    };
    tipelem.appendChild(document.createTextNode('[x]'));
    tipdiv.appendChild(tipelem);
    tipelem = document.createElement('div');
    tipelem.appendChild(document.createTextNode('Demographic 1:'));
    tipdiv.appendChild(tipelem);
    tipelem = document.createElement('div');
    tipelem.appendChild(document.createTextNode('Demographic 2:'));
    tipdiv.appendChild(tipelem);
    tipelem = document.createElement('div');
    tipelem.appendChild(document.createTextNode('Demographic 3:'));
    tipdiv.appendChild(tipelem);
    tipdiv.style.zIndex = 100000;
    tipdiv.style.position = 'absolute';
    tipdiv.style.opacity = '0.8';
    tipdiv.className = 'tooltip';

    return tipdiv;
}

function createDistrictTipDiv() {
    var tipdiv = document.createElement('div');
    var tipelem = document.createElement('h1');
    tipelem.appendChild(document.createTextNode(BODY_MEMBER+'Name'));
    tipdiv.appendChild(tipelem);
    tipelem = document.createElement('div');
    tipelem.id = 'tipclose';
    tipelem.onclick = function(e){
        OpenLayers.Event.stop(e || event);
        tipdiv.style.display = 'none';
    };
    tipelem.appendChild(document.createTextNode('[x]'));
    tipdiv.appendChild(tipelem);

    tipdiv.style.zIndex = 100000;
    tipdiv.style.position = 'absolute';
    tipdiv.style.opacity = '0.8';
    tipdiv.style.width = '85px';
    tipdiv.className = 'tooltip districtidtip';

    return tipdiv;
}


/**
 * Initialize the map from WMS GetCapabilities.
 */
function init() {
    // if the draw tab is disabled, don't init any map jazz.
    if ($('#tab_draw').hasClass('ui-state-disabled')){
        return;
    }

    // default map_server is on same host unless otherwise specified 
    if (MAP_SERVER=="") {
	MAP_SERVER=window.location.host
    }

    var url = window.location.protocol + '//' + MAP_SERVER + '/geoserver/ows?service=wms&' +
        'version=1.1.1&request=GetCapabilities&namespace=' + NAMESPACE;

    if (window.location.host != MAP_SERVER) {
        OpenLayers.ProxyHost= "/proxy?url=";
        url = OpenLayers.ProxyHost + encodeURIComponent(url);
    }

    // set the version cursor
    $('#history_cursor').val(PLAN_VERSION);

    $.ajax({
        url: url,
        type: 'GET',
        // success does not get called by jquery in IE,
        // use complete instead
        complete: function(xhr, textStatus) {
            var data = null;
            if (xhr.responseXML == null) {
                var parser = new DOMParser();
                data = parser.parseFromString(xhr.responseText, 'text/xml');
            }
            else if (xhr.responseXML.childNodes.length == 0) {
                data = new ActiveXObject('Microsoft.XMLDOM');
                data.async = 'false';
                data.loadXML(xhr.responseText);
            }
            else {
                data = xhr.responseXML;
            }
                
            // get the layers in the response
            var layers = $('Layer > Layer',data);
            for (var i = 0; i < layers.length; i++) {
                // get the title of the layer
                var title = $('> Title',layers[i])[0].firstChild.nodeValue;
                var name = $('> Name', layers[i])[0].firstChild.nodeValue;

                // get the SRS and extent of our snap layers, then init the map
                if (title == SNAP_LAYERS[0].layer) {
                    var bbox = $('> BoundingBox',layers[i]);
                    var srs = bbox.attr('SRS');
                    var extent = new OpenLayers.Bounds(
                        bbox.attr('minx'),
                        bbox.attr('miny'),
                        bbox.attr('maxx'),
                        bbox.attr('maxy')
                    );
                    mapinit( srs, extent );
                    return;
                }
            }
        }
    });
}

/*
 * Initialize the map with extents and SRS pulled from WMS.
 */
function mapinit(srs,maxExtent) {

    // The assignment mode -- the map is initially in navigation mode,
    // so the assignment mode is null.
    var assignMode = null;

    // This projection is web mercator
    var projection = new OpenLayers.Projection(srs);

    // Explicitly create the navigation control, since
    // we'll want to deactivate it in the future.
    var navigate = new OpenLayers.Control.Navigation({
        autoActivate: true,
        handleRightClicks: true
    });

    // Dynamically compute the resolutions, based on the map extents.
    // NOTE: Geoserver computes the resolution with the top and the bottom
    // components of the extent, NOT the left/right.
    var rez = [(maxExtent.top - maxExtent.bottom) / 256.0];
    while (rez.length < 12) {
        rez.push( rez[rez.length - 1] / 2.0 );
    }

    // Create a slippy map.
    var olmap = new OpenLayers.Map('map', {
        // The resolutions here must match the settings in geowebcache.
	resolutions: rez,
        maxExtent: maxExtent,
        projection: projection,
        units: 'm',
        panMethod: null,
        controls: [
            navigate,
            new OpenLayers.Control.PanZoomBar(),
            new OpenLayers.Control.KeyboardDefaults()
        ]
    });

    // These layers are dependent on the layers available in geowebcache
    var layers = [];
    for (i in MAP_LAYERS) {
        var layerName = MAP_LAYERS[i];
        if (layerName.indexOf('boundaries') == -1) {
            layers.push(createLayer( layerName, layerName, srs, maxExtent, false, true, true ));
        } else {
            layers.push(createLayer( layerName, layerName, srs, maxExtent, true, false, false ));
        }
    }

    // The strategy for loading the districts. This is effectively
    // a manual refresh, with no automatic reloading of district
    // boundaries except when explicitly loaded.
    var districtStrategy = new OpenLayers.Strategy.Fixed();

    // The style for the districts. This serves as the base
    // style for all rules that apply to the districtLayer
    var districtStyle = {
        fill: true,
        fillOpacity: 0.00,
        strokeColor: '#ee9900',
        strokeOpacity: 1,
        strokeWidth: 2,
        label: '${name}',
        fontColor: '#663300',
        fontSize: '10pt',
        fontFamily: 'Arial,Helvetica,sans-serif',
        fontWeight: '800',
        labelAlign: 'cm'
    };
    
    // A vector layer that holds all the districts in
    // the current plan.
    var districtLayer = new OpenLayers.Layer.Vector(
        'Current Plan',
        {
            strategies: [
                districtStrategy
            ],
            protocol: new OpenLayers.Protocol.HTTP({
                url: '/districtmapping/plan/' + PLAN_ID + '/district/versioned',
                format: new OpenLayers.Format.GeoJSON()
            }),
            styleMap: new OpenLayers.StyleMap(new OpenLayers.Style(districtStyle)),
            projection: projection,
            filter: getVersionAndSubjectFilters()
        }
    );

    // Create a vector layer to hold the current selection
    // of features that are to be manipulated/added to a district.
    var selection = new OpenLayers.Layer.Vector('Selection',{
        styleMap: new OpenLayers.StyleMap({
            "default": new OpenLayers.Style(
                OpenLayers.Util.applyDefaults(
                    { 
                        fill: true, 
                        fillOpacity: 0.0,
                        strokeColor: '#ffff00', 
                        strokeWidth: 3 
                    }, 
                    OpenLayers.Feature.Vector.style["default"]
                )
            ),
            "select":  new OpenLayers.Style(
                OpenLayers.Util.applyDefaults(
                    { 
                        fill: true, 
                        fillColor: '#ee9900',
                        strokeColor: '#ee9900'
                    }, 
                    OpenLayers.Feature.Vector.style["select"]
                )
            ),
            "error": new OpenLayers.Style(
                OpenLayers.Util.applyDefaults(
                    {
                        fill: false,
                        strokeColor: '#ee0000'
                    },
                    OpenLayers.Feature.Vector.style["select"]
                )
            )
        })
    });

    // add these layers to the map
    layers.push(districtLayer);
    layers.push(selection);
    olmap.addLayers(layers);

    /**
     * Get information about the snap layer that should be used, according
     * to the current zoom level.
     */
    var getSnapLayer = function() {
        var zoom = 0;
        if (typeof(olmap) != 'undefined') {
            zoom = olmap.zoom;
        }
        var min_layer = { min_zoom: -1 };
        for (var i in SNAP_LAYERS) {
            var snap_layer = SNAP_LAYERS[i];
            var my_min = snap_layer.min_zoom;
            if (zoom >= my_min && my_min > min_layer.min_zoom) {
                min_layer = snap_layer;
            }
        }
        return { layer: min_layer.layer, level:min_layer.level, display:min_layer.name };
    }

    // Create a protocol that is used by all editing controls
    // that selects geography at the specified snap layer.
    var getProtocol = new OpenLayers.Protocol.WFS({
        url: window.location.protocol + '//' + MAP_SERVER + '/geoserver/wfs',
        featureType: getSnapLayer().layer,
        featureNS: NS_HREF,
        featurePrefix: NAMESPACE,
        srsName: srs,
        geometryName: 'geom',
	maxFeatures: FEATURE_LIMIT + 1
    });

    var idProtocol = new OpenLayers.Protocol.WFS({
        url: window.location.protocol + '//' + MAP_SERVER + '/geoserver/wfs',
        featureType: 'identify_geounit',
        featureNS: NS_HREF,
        featurePrefix: NAMESPACE,
        srsName: srs,
        geometryName: 'geom'
    });

    // Create a simple point and click control for selecting
    // geounits one at a time.
    var getControl = new OpenLayers.Control.GetFeature({
        autoActivate: false,
        protocol: getProtocol,
        multipleKey: 'shiftKey',
        toggleKey: 'ctrlKey',
        filterType: OpenLayers.Filter.Spatial.INTERSECTS
    });

    // Create a rectangular drag control for selecting
    // geounits that intersect a box.
    var boxControl = new OpenLayers.Control.GetFeature({
        autoActivate: false,
        protocol: getProtocol,
        click: false,
        box: true,
        multipleKey: 'shiftKey',
        toggleKey: 'ctrlKey',
        filterType: OpenLayers.Filter.Spatial.INTERSECTS
    });

    // Reload the information tabs and reload the filters
    var updateInfoDisplay = function() {
        $('.geography').load(geourl, {  
            demo: getDistrictBy().by,
            version: getPlanVersion()
        }, function() {
            loadTooltips();
            sortByVisibility(true);
        });            

        $('.demographics').load(demourl, {
            version: getPlanVersion()
        }, function() {
            loadTooltips();
            sortByVisibility(true);
        });            

        districtLayer.filter = getVersionAndSubjectFilters();
        districtLayer.strategies[0].load();
    };

    // An assignment function that adds geounits to a district
    var assignOnSelect = function(feature) {
        if (selection.features.length == 0) {
            $('#assign_district').val('-1');
            return;
        }

        var district_id = feature.data.district_id;
        var geolevel_id = selection.features[0].attributes.geolevel_id;
        var geounit_ids = [];
        for (var i = 0; i < selection.features.length; i++) {
            geounit_ids.push( selection.features[i].attributes.id );
        }
        geounit_ids = geounit_ids.join('|');
        OpenLayers.Element.addClass(olmap.viewPortDiv,'olCursorWait');
        $('#working').dialog('open');
        $.ajax({
            type: 'POST',
            url: '/districtmapping/plan/' + PLAN_ID + '/district/' + district_id + '/add',
            data: {
                geolevel: geolevel_id,
                geounits: geounit_ids,
                version: getPlanVersion()
            },
            success: function(data, textStatus, xhr) {
                var mode = data.success ? 'select' : 'error';
                if (data.success) {
                    // update the max version of this plan
                    PLAN_VERSION = data.version;

                    // set the version cursor
                    $('#history_cursor').val(data.version);

                    // update the UI buttons to show that you can
                    // perform an undo now, but not a redo
                    $('#history_redo').addClass('disabled');
                    $('#history_undo').removeClass('disabled');

                    updateInfoDisplay();

                    $('#saveplaninfo').trigger('planSaved', [ data.edited ]);
                }
                else {
                    OpenLayers.Element.removeClass(olmap.viewPortDiv, 'olCursorWait');
                    $('#working').dialog('close');
                }

                for (var i = 0; i < selection.features.length; i++) {
                    selection.drawFeature(selection.features[i], mode);
                }

                if (assignMode == null) {
                    $('#assign_district').val('-1');
                }
                else if (assignMode == 'dragdrop') {
                    $('#assign_district').val('-1');
                    dragdropControl.deactivate();
                    dragdropControl.resumeTool.activate();
                }
            },
            error: function(xhr, textStatus, error) {
                window.status = 'failed to select';
            }
        });
    };

    // When the selection is changed, perform the addition or subtraction
    // to the current geounit selection. Also, if the assignment mode is
    // either 'anchor' or 'dragdrop', do some more processing.
    var unitsSelected = function(features, subtract) {
        if (subtract) {
            var removeme = [];
            for (var i = 0; i < selection.features.length; i++) {
                for (var j = 0; j < features.length; j++) {
                    if (selection.features[i].data.id == features[j].data.id) {
                        removeme.push(selection.features[i]);
                    }
                }
            }
            selection.removeFeatures(removeme);
        }
        else {
	    // Check to make sure we haven't exceeded the FEATURE_LIMIT in this selection or total selection
            if (features.length > FEATURE_LIMIT) {
                $('<div id="toomanyfeaturesdialog">You cannot select that many features at once.\n\nConsider drawing a smaller area with the selection tool.</div>').dialog({
                    modal: true,
                    autoOpen: true,
                    title: 'Sorry',
                    buttons: { 
                        'OK': function() {
                        $('#toomanyfeaturesdialog').remove();
                        }
                    }
                });
                return;
            } else if (features.length + selection.features.length > FEATURE_LIMIT) {
                $('<div id="toomanyfeaturesdialog">You cannot select any more features.\n\nConsider assigning your current selection to a district first.</div>').dialog({
                    modal: true,
                    autoOpen: true,
                    title: 'Sorry',
                    buttons: { 
                        'OK': function() {
                        $('#toomanyfeaturesdialog').remove();
                        }
                    }
                });
                return;
            }

            var addme = [];
            for (var i = 0; i < features.length; i++) {
                var match = false;
                for (var j = 0; j < selection.features.length && !match; j++) {
                    if (features[i].data.id == selection.features[j].data.id) {
                        match = true;
                    }
                }
                if (!match) {
		    addme.push(features[i]);
                }
            }
            selection.addFeatures(addme);

            // this is necessary because a feature may be selected more
            // than once, and the js feature object is different, but the
            // actual feature itself is the same geometry and attributes.
            for (var i = 0; i < addme.length; i++) {
                selection.features[addme[i].fid || addme[i].id] = addme[i];
            }
        }

        if (assignMode == null) {
            return;
        }
        else if (assignMode == 'anchor') {
            var d_id = $('#assign_district').val();
            if (parseInt(d_id,10) > 0) {
                var feature = { data:{ district_id: d_id } };
                assignOnSelect(feature);
            }
        }
        else if (assignMode == 'dragdrop') {
            var active = olmap.getControlsBy('active',true);
            var currentTool = null;
            for (var i = 0; i < active.length && currentTool == null; i++) {
                if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                    currentTool = active[i];
                }
            }
            currentTool.deactivate();

            dragdropControl.resumeTool = currentTool;
            dragdropControl.activate();
        }
    };

    // Create a polygon select control for free-form selections.
    var polyControl = new OpenLayers.Control.DrawFeature( 
        selection,
        OpenLayers.Handler.Polygon,
        {
            handlerOptions: {
                freehand: true,
                freehandToggle: null
            },
            featureAdded: function(feature){
                // WARNING: not a part of the API!
                var append = this.handler.evt.shiftKey;
                var subtract = this.handler.evt.ctrlKey && (assignMode == null);
                var newOpts = getControl.protocol.options;
                newOpts.featureType = getSnapLayer().layer;
                getControl.protocol = new OpenLayers.Protocol.WFS( newOpts );
                getControl.protocol.read({
                    filter: new OpenLayers.Filter.Spatial({
                        type: OpenLayers.Filter.Spatial.INTERSECTS,
                        value: feature.geometry,
                        projection: getProtocol.options.srsName
                    }),
                    callback: function(rsp){
                        // first, remove the lasso feature
                        var lasso = selection.features[selection.features.length - 1];
                        selection.removeFeatures([lasso]);

                        if (!(append || subtract)){
                            // if this is a new lasso, remove all the 
                            // old selected features
                            selection.removeFeatures(selection.features);
                        }

                        unitsSelected( rsp.features, subtract );
                    }
                });
            }
        }
    );

    // set this timeout function, since jquery is apparently not ready
    // to select the elements based on this class during regular init.
    // also, the reference to the polyControl is used in this init method
    setTimeout(function(){
        var jtmp = $('.olHandlerBoxSelectFeature');

        var polySelectStyle = {
            pointRadius: 0,
            strokeWidth: parseInt(jtmp.css('borderTopWidth').slice(0,1),10),
            strokeColor: jtmp.css('borderTopColor'),
            strokeOpacity: parseFloat(jtmp.css('opacity')),
            fillColor: jtmp.css('background-color'),
            fillOpacity: parseFloat(jtmp.css('opacity'))
        };

        polyControl.handler.style = polySelectStyle;
    }, 100);

    // Create a tooltip inside of the map div
    var tipdiv = createMapTipDiv();
    olmap.div.insertBefore(tipdiv,olmap.div.firstChild);

    // Create a control that shows the details of the district
    // underneath the cursor.
    var idControl = new IdGeounit({
        autoActivate: false,
        protocol: idProtocol
    });

    var districtIdDiv = createDistrictTipDiv();
    olmap.div.insertBefore(districtIdDiv,olmap.div.firstChild);
    var districtIdControl = new OpenLayers.Control.SelectFeature(
        districtLayer,
        {
            hover: false,
            onSelect: (function(){
                var showTip = function(tipFeature, pixel) {
                    $(districtIdDiv.firstChild).text(tipFeature.attributes.name);

                    var leftOffset = $(districtIdDiv).width() + 15;
                    var topOffset = $(districtIdDiv).height() + 15;
                    if (pixel.x < leftOffset) { 
                        pixel.x = leftOffset;
                    }
                    else if (pixel.x > olmap.div.clientWidth - leftOffset) {
                        pixel.x = olmap.div.clientWidth - leftOffset;
                    }
                    if (pixel.y < topOffset) {
                        pixel.y = topOffset;
                    }
                    else if (pixel.y > (olmap.div.clientHeight-29) - topOffset) {
                        pixel.y = (olmap.div.clientHeight-29) - topOffset;
                    }
                    $(districtIdDiv).css('top',pixel.y - topOffset);
                    $(districtIdDiv).css('left',pixel.x - leftOffset);
                    districtIdDiv.style.display = 'block';

                    // hide the other tip
                    tipdiv.style.display = 'none';
                };
                return function(feature, event){
                    window.status = feature.attributes.name;
                    var pixel = this.handlers.feature.evt.xy;
                    showTip(feature, pixel);
                };
            })(),
            onUnselect: function(feature) {
                districtIdDiv.style.display = 'none';
            }
        }
    );
    districtIdControl.events.register('deactivate', districtIdControl, function() {
        districtIdDiv.style.display = 'none';
    });

    // Get the feature at the point in the layer.
    var featureAtPoint = function(pt, lyr) {
        for (var i = 0; i < lyr.features.length; i++) {
            if (lyr.features[i].geometry != null &&
                pt.intersects(lyr.features[i].geometry)) {
                return lyr.features[i];
            }
        }

        return null;
    };

    // Test if the provided point lays within the features in the provided
    // layer.
    var pointInFeatures = function(pt, lyr) {
        return featureAtPoint(pt, lyr) != null;
    };

    // Create a control that shows where a drag selection is
    // traveling.
    var dragdropControl = new OpenLayers.Control.DragFeature(
        selection,
        {
            documentDrag: true,
            onStart: function(feature, pixel) {
                var ll = olmap.getLonLatFromPixel(pixel);
                dragdropControl.lastPt = new OpenLayers.Geometry.Point(ll.lon, ll.lat);
            },
            onDrag: function(feature, pixel) {
                var ll = olmap.getLonLatFromPixel(pixel);
                var pt = new OpenLayers.Geometry.Point(ll.lon, ll.lat);
                var dist = featureAtPoint(pt, districtLayer);
                if (dist == null) {
                    dist = { data: { district_id: 1 } };
                }
                $('#assign_district').val(dist.data.district_id);
                for (var i = 0; i < selection.features.length; i++) {
                    if (selection.features[i].fid != feature.fid) {
                        selection.features[i].geometry.move(
                            pt.x - dragdropControl.lastPt.x,
                            pt.y - dragdropControl.lastPt.y
                        );
                        selection.drawFeature(selection.features[i]);
                    }
                }
                dragdropControl.lastPt = pt;
            },
            onComplete: function(feature, pixel) {
                var ll = olmap.getLonLatFromPixel(pixel);
                var pt = new OpenLayers.Geometry.Point(ll.lon, ll.lat);
                
                if (pointInFeatures(pt, districtLayer)) {
                    var dfeat = { data:{ district_id: $('#assign_district').val() } };
                    assignOnSelect(dfeat);
                }
                else {
                    selection.removeFeatures(selection.features);

                    $('#assign_district').val('-1');               
                    dragdropControl.deactivate();
                    dragdropControl.resumeTool.activate();
                }
            }
        }
    );

    // A callback to create a popup window on the map after a peice
    // of geography is selected.
    var idFeature = function(e) {
        var snapto = getSnapLayer().layer;

        // get the range of geolevels
        var maxGeolevel = 0, minGeolevel = 9999;
        for (var i = 0; i < SNAP_LAYERS.length; i++) {
            if (snapto == 'simple_' + SNAP_LAYERS[i].level) {
                minGeolevel = SNAP_LAYERS[i].geolevel;
            }
            maxGeolevel = Math.max(maxGeolevel, SNAP_LAYERS[i].geolevel);
        }
        // get the breadcrumbs to this geounit, starting at the
        // largest area (lowest geolevel) first, down to the
        // most specific geolevel
        var crumbs = {};
        var ctics = {};
        var tipFeature = e.features[0];
        for (var glvl = maxGeolevel; glvl >= minGeolevel; glvl--) {
            for (var feat = 0; feat < e.features.length; feat++) {
                if (e.features[feat].data.geolevel_id == glvl) {
                    crumbs[e.features[feat].data.id] = e.features[feat].data.name;
                }
                if (e.features[feat].data.geolevel_id == minGeolevel) {
                    tipFeature = e.features[feat];
                    for (var demo = 0; demo < DEMOGRAPHICS.length; demo++) {
                        if (e.features[feat].data.subject_id == DEMOGRAPHICS[demo].id) {
                            ctics[DEMOGRAPHICS[demo].text] = parseFloat(e.features[feat].data.number);
                        }
                    }
                }
            }
        }

        // truncate the breadcrumbs into a single string
        var place = [];
        for (var key in crumbs) {
            place.push(crumbs[key]);
        }
        place = place.join(' / ');

        var centroid = tipFeature.geometry.getCentroid();
        var lonlat = new OpenLayers.LonLat( centroid.x, centroid.y );
        var pixel = olmap.getPixelFromLonLat(lonlat);
        tipdiv.style.display = 'block';
        tipdiv.childNodes[0].childNodes[0].nodeValue = place;
        var select = $('#districtby')[0];
        var value = parseInt(tipFeature.attributes.number, 10);

        var node = 2;
        for (var key in ctics) {
            tipdiv.childNodes[node].firstChild.nodeValue = 
                key + ': ' + ctics[key].toLocaleString();
            node ++;
        }

        var halfWidth = tipdiv.clientWidth/2;
        var halfHeight = tipdiv.clientHeight/2;
        if (pixel.x < halfWidth) { 
            pixel.x = halfWidth;
        }
        else if (pixel.x > olmap.div.clientWidth - halfWidth) {
            pixel.x = olmap.div.clientWidth - halfWidth;
        }
        if (pixel.y < halfHeight) {
            pixel.y = halfHeight;
        }
        else if (pixel.y > (olmap.div.clientHeight-29) - halfHeight) {
            pixel.y = (olmap.div.clientHeight-29) - halfHeight;
        }

        tipdiv.style.left = (pixel.x - halfWidth) + 'px';
        tipdiv.style.top = (pixel.y - halfHeight) + 'px';
        if (tipdiv.pending) {
            clearTimeout(tipdiv.timeout);
            tipdiv.pending = false;
        }

        // hide the other tip
        districtIdDiv.style.display = 'none';
    };

    // A callback for feature selection in different controls.
    var featuresSelected = function(e){
        var subtract = e.object.modifiers.toggle && (assignMode == null);

        unitsSelected(e.features, subtract);
    };


    /*
    * This will return the maps's truly visible bounds; if the info
    * tabs on the right are up, that's the usual map bounds. If the 
    * info tabs are showing, it's the visible area of the map to the 
    * left of those tabs
    */
    var getVisibleBounds = function() {
        // Checking for visibility sometimes causes OpenLayers unhappiness
        try {
            if ($('.map_menu_content:visible').length > 0) {
                var offset = $('#map_menu_header').position();
                var bounds = olmap.getExtent();
                var lonLat = olmap.getLonLatFromPixel(new OpenLayers.Pixel(offset.left, offset.top));
                bounds.right = lonLat.lon;
                return bounds;
            }
        } catch (exception) {
            // that's OK - nothing we can do here
        }
        return undefined;
    }
    
    /*
    * This method is useful to determine whether an item is visible
    * to the user - pass in the bounds from getVisibleBounds if the 
    * info tabs are showing
    */ 
    var featureOnScreen = function(feature, bounds) {
        try {
            if (bounds && feature.geometry) {
                return feature.geometry.intersects(bounds.toGeometry());
            } else {
                return feature.onScreen();
            }
        } catch (exception) {
            return false;
        }
    }

    // Connect the featuresSelected callback above to the featureselected
    // events in the point and rectangle control.
    getControl.events.register('featuresselected', 
        getControl,
        featuresSelected);
    boxControl.events.register('featuresselected', 
        boxControl, 
        featuresSelected);
    idControl.events.register('featuresselected', 
        idControl, 
        idFeature);

    // A callback for deselecting features from different controls.
    var featureUnselected = function(e){
        selection.removeFeatures([e.feature]);
    };

    // Connect the featureUnselected callback above to the featureunselected
    // events in the point and rectangle control.
    getControl.events.register('featureunselected', 
        this, 
        featureUnselected);
    boxControl.events.register('featureunselected', 
        this, 
        featureUnselected);

    // Connect a method for indicating work when the district layer
    // is reloaded.
    districtLayer.events.register('loadstart',districtLayer,function(){
        OpenLayers.Element.addClass(olmap.viewPortDiv, 'olCursorWait');
    });


    // This object holds the mean and standard deviation for the 
    // compactness scores, calculated when the features are loaded.
    var compactnessAvg = {};


    var getCompactnessAvg = function(features) {
        var average = function(a){
            //+ Carlos R. L. Rodrigues
            //@ http://jsfromhell.com/array/average [rev. #1]
            var r = {mean: 0, variance: 0, deviation: 0}, t = a.length;
            for(var m, s = 0, l = t; l--; s += a[l]);
            for(m = r.mean = s / t, l = t, s = 0; l--; s += Math.pow(a[l] - m, 2));
            return r.deviation = Math.sqrt(r.variance = s / t), r;
        };

        var scores = [];
        for (var i = 0; i < features.length; i++) {
            var feature = features[i];
            scores.push(feature.attributes.compactness);
        }
        return average(scores);

    };

    // Get the OpenLayers styling rules for the map, given the district 
    // layer and/or modification (e.g. No styling compactness) taken from
    // the District By: dropdown.
    var getStylingRules = function(typeName, dby) {
        var rules = [];
        var lowestColor = $('.farunder').css('background-color');
        var lowerColor = $('.under').css('background-color');
        var upperColor = $('.over').css('background-color');
        var highestColor = $('.farover').css('background-color');
        if (typeName == 'demographics') {
            rules = [
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.LESS_THAN_OR_EQUAL_TO,
                        property: 'number',
                        value: RULES[dby.by].lowest
                    }),
                    symbolizer: {
                        fillColor: lowestColor,
                        fillOpacity: 0.5
                    }
                }),
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.BETWEEN,
                        property: 'number',
                        lowerBoundary: RULES[dby.by].lowest,
                        upperBoundary: RULES[dby.by].lower
                    }),
                    symbolizer: {
                        fillColor: lowerColor,
                        fillOpacity: 0.5
                    }
                }),
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.BETWEEN,
                        property: 'number',
                        lowerBoundary: RULES[dby.by].lower,
                        upperBoundary: RULES[dby.by].upper
                    })
                }),
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.BETWEEN,
                        property: 'number',
                        lowerBoundary: RULES[dby.by].upper,
                        upperBoundary: RULES[dby.by].highest
                    }),
                    symbolizer: {
                        fillColor: upperColor,
                        fillOpacity: 0.5
                    }
                }),
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.GREATER_THAN_OR_EQUAL_TO,
                        property: 'number',
                        value: RULES[dby.by].highest
                    }),
                    symbolizer: {
                        fillColor: highestColor,
                        fillOpacity: 0.5
                    }
                })
            ];
        } else if (typeName == 'Contiguity') {
            rules = [
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.EQUAL_TO,
                        property: 'contiguous',
                        value: false
                    }),
                    symbolizer: {
                        fillColor: highestColor,
                        fillOpacity: 0.5
                    }
                }),
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.NOT_EQUAL_TO,
                        property: 'contiguity',
                        value: false
                    })
                })
        
            ];
        } else if (typeName == 'Compactness') {
            if (compactnessAvg) {
                var upper = compactnessAvg.mean + (2 * compactnessAvg.deviation);
                var lower = compactnessAvg.mean - (2 * compactnessAvg.deviation); 
                rules = [
                    new OpenLayers.Rule({
                        filter: new OpenLayers.Filter.Comparison({
                            type: OpenLayers.Filter.Comparison.LESS_THAN,
                            property: 'compactness',
                            value: lower 
                        }),
                        symbolizer: {
                            fillColor: lowestColor,
                            fillOpacity: 0.5
                        }
                    }),
                    new OpenLayers.Rule({
                        filter: new OpenLayers.Filter.Comparison({
                            type: OpenLayers.Filter.Comparison.BETWEEN,
                            property: 'compactness',
                            lowerBoundary: lower,
                            upperBoundary: upper
                        })
                    }),
                    new OpenLayers.Rule({
                        filter: new OpenLayers.Filter.Comparison({
                            type: OpenLayers.Filter.Comparison.GREATER_THAN,
                            property: 'compactness',
                            value: upper 
                        }),
                        symbolizer: {
                            fillColor: highestColor,
                            fillOpacity: 0.5
                        }
                    }),
                ];
            }

        }
        return rules;
    };
    // Recompute the rules for the district styling prior to the adding
    // of the features to the district layer.  This is done at this time
    // to prevent 2 renderings from being triggered on the district layer.
    districtLayer.events.register('beforefeaturesadded',districtLayer,function(context){
        var newOptions = OpenLayers.Util.extend({}, districtStyle);
        var dby = getDistrictBy();
        var rules = []
        if (!dby.modified) {
            rules = getStylingRules('demographics', dby);
        } else {
            rules = getStylingRules(dby.modified, dby);
        }
        
        var newStyle = new OpenLayers.Style(newOptions,{
            rules:rules
        });
        districtLayer.styleMap = new OpenLayers.StyleMap(newStyle);
    });

    // Connect an event to the district layer that updates the 
    // list of possible districts to assign to.
    // TODO: this doesn't account for districts with null geometries
    // which will not come back from the WFS query
    districtLayer.events.register('loadend',districtLayer,function(){
        OpenLayers.Element.removeClass(olmap.viewPortDiv, 'olCursorWait');
        selection.removeFeatures(selection.features);
        
        var sorted = districtLayer.features.slice(0,districtLayer.features.length);
        sorted.sort(function(a,b){
            return a.attributes.name > b.attributes.name;
        });
        compactnessAvg = getCompactnessAvg(sorted);

        // get the maximum version of all districts. If walking backward,
        // it may be possible that the version you requested (let's say
        // you requested version 3 of a plan) doesn't have any districts.
        // This will happen if a user performs many undo steps, then edits
        // the plan. In this case, the maximum version will be LESS than
        // the version requested.
        //
        // Also, populate the 'Assigning Tools' dropdown with the list
        // of current districts.
        var max_version = 0;
        $('#assign_district option').detach();
        $('#assign_district')
            .append('<option value="-1">-- Select One --</option>')
            .append('<option value="1">Unassigned</option>');
        for (var dist in districtLayer.features) {
            var district = districtLayer.features[dist];
            max_version = Math.max(district.attributes.version,max_version);
            if (district.attributes.name != 'Unassigned') {
                $('#assign_district')
                    .append('<option value="' + district.attributes.district_id + '">' + district.attributes.name + '</option>');
            }
        }
        if ($('#assign_district option').length < MAX_DISTRICTS + 1) {

            $('#assign_district')
                .append('<option value="new">New ' + BODY_MEMBER + '</option>');
        }

        var all_options = $('#assign_district option').detach();
        // sort the options
        all_options.sort(function(a,b){
            if (a.value == 'new') {
                return 1;
            } else if (b.value == 'new') {
                return -1;
            } else {
                return parseInt(a.value,10) > parseInt(b.value,10);
            }
        });
        all_options.appendTo('#assign_district');

        $('#assign_district').val(-1);

        // set the version cursor to the max version. In situations where
        // there has been an edit on an undo, the version cursor in not
        // continuous across all versions of the plan.
        var cursor = $('#history_cursor');
        var cval = cursor.val();
        if (cval != max_version) {
            // Purge all versions that are in the history that are missing.
            // You can get here after editing a plan for a while, then
            // performing some undos, then editing again. You will be
            // bumped up to the latest version of the plan, but there will
            // be 'phantom' versions between the undo version basis and the
            // current plan version.
            while (cval > max_version) {
                delete PLAN_HISTORY[cval--];
            }
        }
        PLAN_HISTORY[max_version] = true;
        cursor.val(max_version);

        if (max_version == 0) {
            $('#history_undo').addClass('disabled');
        }

        var working = $('#working');
        if (working.dialog('isOpen')) {
            working.dialog('close');
        }
    });

    olmap.events.register('movestart',olmap,function(){
        districtIdDiv.style.display = 'none';
        tipdiv.style.display = 'none';
    });

    // When the navigate map tool is clicked, disable all the 
    // controls except the navigation control.
    $('#navigate_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        navigate.activate();
        $('#dragdrop_tool').removeClass('toggle');
        $('#anchor_tool').removeClass('toggle');
        assignMode = null;
        $('#assign_district').val(-1);
        tipdiv.style.display = 'none';
        districtIdDiv.style.display = 'none';
    });

    // When the identify map tool is clicked, disable all the
    // controls except the identify control.
    $('#identify_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        idControl.activate();
        $('#dragdrop_tool').removeClass('toggle');
        $('#anchor_tool').removeClass('toggle');
        assignMode = null;
        $('#assign_district').val(-1);
    });

    // When the district id  map tool is clicked, disable all the
    // controls except the district id control.
    $('#district_id_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        districtIdControl.activate();
        $('#dragdrop_tool').removeClass('toggle');
        $('#anchor_tool').removeClass('toggle');
        assignMode = null;
        $('#assign_district').val(-1);
    });
    // When the single pick tool is clicked, disable all the
    // controls except for the single pick tool.
    $('#single_drawing_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        getControl.activate();
        getControl.features = selection.features;
        tipdiv.style.display = 'none';
        districtIdDiv.style.display = 'none';
    });

    // When the rectangle selection tool is clicked, disable all the
    // controls except for the rectangle selection tool.
    $('#rectangle_drawing_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        boxControl.activate();
        boxControl.features = selection.features;
        tipdiv.style.display = 'none';
        districtIdDiv.style.display = 'none';
    });

    // When the polygon selection tool is clicked, disable all the
    // controls except for the polygon selection tool.
    $('#polygon_drawing_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        polyControl.activate();
        tipdiv.style.display = 'none';
        districtIdDiv.style.display = 'none';
    });

    // When the assignment tool is clicked, disable all the
    // controls except for the assignment tool.  
    $('#dragdrop_tool').click(function(evt){
        var me = $(this);
        var selectionAlready = false;
        if (me.hasClass('toggle')) {
            me.removeClass('toggle');
            assignMode = null;
            dragdropControl.deactivate();
            if (dragdropControl.resumeTool) {
                dragdropControl.resumeTool.activate();
            }
        }
        else {
            me.addClass('toggle');
            assignMode = 'dragdrop';
            if (selection.features.length > 0) {
                var active = olmap.getControlsBy('active',true);
                dragdropControl.resumeTool = null;
                for (var i = 0; i < active.length && dragdropControl.resumeTool == null; i++) {
                    if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                        dragdropControl.resumeTool = active[i];
                        active[i].deactivate();
                    }
                }
                dragdropControl.activate();
                selectionAlready = true;
            }
        }
        $('#navigate_map_tool').removeClass('toggle');
        navigate.deactivate();
        $('#identify_map_tool').removeClass('toggle');
        idControl.deactivate();
        $('#district_id_map_tool').removeClass('toggle');
        districtIdControl.deactivate();
        $('#anchor_tool').removeClass('toggle');
        tipdiv.style.display = 'none';
        districtIdDiv.style.display = 'none';

        // enable single select tool if no selection tool is enabled
        if (!(getControl.active || boxControl.active || polyControl.active) && !selectionAlready) {
            getControl.activate();
            $('#single_drawing_tool').addClass('toggle');
        }
    });

    $('#anchor_tool').click(function(evt){
        var me = $(this);
        if (me.hasClass('toggle')) {
            me.removeClass('toggle');
            assignMode = null;
            $('#assign_district').val(-1);
        }
        else {
            me.addClass('toggle');
            assignMode = 'anchor';

            var anchorTip = $('#anchor_tool').data('tooltip');
            anchorTip.hide();
            var assignTip = $('#assign_district').data('tooltip');
            assignTip.show();
            // must show before grabbing text
            var origText = assignTip.getTip().text();
            assignTip.getTip().text('Select the destination district');
            setTimeout(function(){
                assignTip.getTip().hide();
                assignTip.getTip().text(origText);
            }, 5000);
        }
        $('#navigate_map_tool').removeClass('toggle');
        navigate.deactivate();
        $('#identify_map_tool').removeClass('toggle');
        idControl.deactivate();
        $('#district_id_map_tool').removeClass('toggle');
        districtIdControl.deactivate();
        $('#dragdrop_tool').removeClass('toggle');
        tipdiv.style.display = 'none';
        districtIdDiv.style.display = 'none';

        // enable single select tool if no selection tool is enabled
        if (!(getControl.active || boxControl.active || polyControl.active)) {
            getControl.activate();
            $('#single_drawing_tool').addClass('toggle');
        }
    });

    // Add the created controls to the map
    olmap.addControls([
        getControl,
        boxControl,
        polyControl,
        new GlobalZoom(),
        idControl,
        districtIdControl,
        dragdropControl
    ]);

    // get a format parser for SLDs and the legend
    var sldFormat = new OpenLayers.Format.SLD();

    // a method that will read the named layer, and return
    // the default style
    var getDefaultStyle = function(sld, layerName) {
        var styles = sld.namedLayers[layerName].userStyles;
        var style = { isDefault:false };
        for(var i=0; i<styles.length && !style.isDefault; ++i) {
            style = styles[i];
        }
        return style;
    }

    //
    // get the styles associated with the current map configuration
    //
    var getMapStyles = (function() {
        var styleCache = {};
        var callbackStyle = function(sld) {
            var userStyle = getDefaultStyle(sld,getShowBy());
            $('#legend_title').empty().append(userStyle.title);

            var lbody = $('#basemap_legend tbody');
            lbody.empty();

            var rules = userStyle.rules;
            for (var i = 0; i < rules.length; i++) {
                var rule = rules[i];
                if (!('Polygon' in rule.symbolizer)) {
                    continue;
                }

                var div = $('<div/>');
                div.css('background-color',rule.symbolizer.Polygon.fillColor);
                div.css('border-width',rule.symbolizer.Polygon.strokeWidth);
                div.css('border-color',rule.symbolizer.Polygon.strokeColor);
                div.addClass('swatch');
                div.addClass('basemap_swatch');
                var swatch = $('<td/>');
                swatch.width(32);
                swatch.append(div);

                var row = $('<tr/>');
                row.append(swatch);

                var title = $('<td/>');
                title.append( rule.title );

                row.append(title);

                lbody.append(row);
            }
        };

        return function() {
            var snap = getSnapLayer().layer.split('simple_')[1];
            var show = getShowBy();

            styleUrl = '/sld/' + snap + '_' + show + '.sld';

            if (styleUrl in styleCache) {
                if (styleCache[styleUrl]) {
                    callbackStyle(styleCache[styleUrl]);
                    return;
                }
            } else {
                styleCache[styleUrl] = false;
            }

            OpenLayers.Request.GET({
                url: styleUrl,
                method: 'GET',
                callback: function(xhr){
                    var sld = sldFormat.read(xhr.responseXML || xhr.responseText);
                    styleCache[styleUrl] = sld;
                    callbackStyle(sld);
                }
            });
        };
    })();

    //
    // Update the part of the legend associated with the 
    // Show Boundaries: control
    //
    var updateBoundaryLegend = function() {
        var boundary = getBoundLayer();
        if (boundary == '') {
            $('#boundary_legend').hide();
             return;
        }

        OpenLayers.Request.GET({
            url: '/sld/' + boundary.substr(4) + '.sld',
            method: 'GET',
            callback: function(xhr){
                var sld = sldFormat.read(xhr.responseXML || xhr.responseText);
                var userStyle = getDefaultStyle(sld,'Boundaries');
                $('#boundary_title').empty().append(userStyle.title);

                var lbody = $('#boundary_legend tbody');
                lbody.empty();

                var rules = userStyle.rules;
                for (var i = 0; i < rules.length; i++) {
                    var rule = rules[i];
                    if (!('Polygon' in rule.symbolizer)) {
                        continue;
                    }

                    var div = $('<div/>');
                    div.css('border-color',rule.symbolizer.Polygon.strokeColor);
                    div.addClass('swatch');
                    div.addClass('boundary_swatch');
                    var swatch = $('<td/>');
                    swatch.width(32);
                    swatch.append(div);

                    var row = $('<tr/>');
                    row.append(swatch);

                    var title = $('<td/>');
                    title.append( rule.title );

                    row.append(title);

                    lbody.append(row);
                    $('#boundary_legend').show();
                }
            }
        });
    };

    //
    // Update the styles of the districts based on the 'Show District By'
    // dropdown in the menu.
    //
    var makeDistrictLegendRow = function(id, cls, label) {
        var div = $('<div id="' + id + '">&nbsp;</div>');
        div.addClass('swatch');
        div.addClass('district_swatch');
        div.addClass(cls)
        var swatch = $('<td/>');
        swatch.width(32);
        swatch.append(div);

        var row = $('<tr/>');
        row.append(swatch);

        var title = $('<td/>');
        title.append( label );

        row.append(title);

        return row;
    };
    
    var updateDistrictStyles = function() {
        var distDisplay = getDistrictBy();
        var lbody = $('#district_legend tbody');

        if (distDisplay.modified == 'None') {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_within','target','Boundary');

            lbody.append(row);
        }
        else if (distDisplay.modified == 'Contiguity') {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_farover','farover','Noncontiguous');
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target','Contiguous');
            lbody.append(row);
        }
        else if (distDisplay.modified == 'Compactness') {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_farover','farover','Very Compact');
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target','Average');
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_farunder','farunder','Hardly Compact');
            lbody.append(row);
        }
        else {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_farover','farover','Far Over Target');
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_over','over','Over Target');
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target','Within Target');
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_under','under','Under Target');
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_farunder','farunder','Far Under Target');
            lbody.append(row);
        }
    };

    // Logic for the 'Snap Map to' dropdown, note that this logic
    // calls the boundsforChange callback
    var changeSnapLayer = function(evt) {
        var newOpts = getControl.protocol.options;
        var show = getShowBy();
        var snap = getSnapLayer();
        var layername = NAMESPACE + ':demo_' + snap.level;
        if (show != 'none') {
            layername += '_' + show;
        }
        var layers = olmap.getLayersByName(layername);

        newOpts.featureType = snap.layer;
        getControl.protocol = 
            boxControl.protocol = new OpenLayers.Protocol.WFS( newOpts );
        olmap.setBaseLayer(layers[0]);
        doMapStyling();
        $('#showby').siblings('label').text('Show ' + snap.display + ' by:');
        getMapStyles();
        updateBoundaryLegend();
    };

    // Logic for the 'Show Map by' dropdown
    $('#showby').change(function(evt){
        var snap = getSnapLayer();
        var show = evt.target.value;
        var layername = NAMESPACE + ':demo_' + snap.level;
        if (show != 'none') {
            layername += '_' + show;
        }

        var layers = olmap.getLayersByName(layername);
        olmap.setBaseLayer(layers[0]);
        doMapStyling();
        getMapStyles();
        updateBoundaryLegend();

        // Since keyboard defaults are on, if focus remains on this
        // dropdown after change, the keyboard may change the selection
        // inadvertently
        $('#showby').blur();
    });

    // Logic for the 'Show Districts by' dropdown
    $('#districtby').change(function(evt){
        districtLayer.filter = getVersionAndSubjectFilters();
        districtLayer.strategies[0].load();

        // Since keyboard defaults are on, if focus remains on this
        // dropdown after change, the keyboard may change the selection
        // inadvertently
        $('#districtby').blur();
    });

    boundaryLayer = {};
    $('#boundfor').change(function(evt){
        try {
            boundaryLayer.setVisibility(false);
        } catch (err) {
            // That's ok - just initializing.
        }
        var name = getBoundLayer();
        if (name != '') {
            var layer = olmap.getLayersByName(name)[0];
            olmap.setLayerIndex(layer, 1);
            boundaryLayer = layer;
            layer.setVisibility(true);
        }
        doMapStyling();
        getMapStyles();
        updateBoundaryLegend();

        // Since keyboard defaults are on, if focus remains on this
        // dropdown after change, the keyboard may change the selection
        // inadvertently
        $('#boundfor').blur();
    });

    // Logic for the 'Assign District to' dropdown
    $('#assign_district').change(function(evt){
        if (this.value == '-1'){
            return true;
        }
        else if (this.value == 'new'){
            createNewDistrict();
        }
        else if (assignMode == null) {
            var feature = { data:{ district_id: this.value } };
            assignOnSelect(feature);
        }

        // Since keyboard defaults are on, if focus remains on this
        // dropdown after change, the keyboard may change the selection
        // inadvertently
        $('#assign_district').blur();
    });

    // Logic for the history back button
    $('#history_undo').click(function(evt){
        var cursor = $('#history_cursor');
        var ver = cursor.val();
        if (ver > 0) {
            ver--;
            PLAN_HISTORY[ver] = true;

            if (ver == 0) {
                $(this).addClass('disabled');
            }
            cursor.val(ver);

            $('#history_redo').removeClass('disabled');

            updateInfoDisplay();
        }
    });

    // Logic for history redo button
    $('#history_redo').click(function(evt){
        var cursor = $('#history_cursor');
        var ver = cursor.val();
        if (ver < PLAN_VERSION) {
            ver++;
            while (!(ver in PLAN_HISTORY)) {
                ver++;
            }
            if (ver == PLAN_VERSION) {
                $(this).addClass('disabled');
            }
            cursor.val(ver);

            $('#history_undo').removeClass('disabled');

            updateInfoDisplay();
        }
    });

    /*
    * Ask the user for a new district name, then assign the current 
    * selection to the new district upon successful creation of the
    * district
    */
    var createNewDistrict = function() {
        if (selection.features.length == 0) {
            $('#assign_district').val('-1');
            return;
        }

        // Once we have the district name, post a request to the 
        // server to create it in the DB
        var createDistrict = function(district_id) {
            var geolevel_id = selection.features[0].attributes.geolevel_id;
            var geounit_ids = [];
            for (var i = 0; i < selection.features.length; i++) {
                geounit_ids.push( selection.features[i].attributes.id );
            }
            geounit_ids = geounit_ids.join('|');
            OpenLayers.Element.addClass(olmap.viewPortDiv,'olCursorWait');
            $('#working').dialog('open');
            $.ajax({
                type: 'POST',
                url: '/districtmapping/plan/' + PLAN_ID + '/district/new',
                data: {
                    district_id: district_id,
                    geolevel: geolevel_id,
                    geounits: geounit_ids,
                    version: getPlanVersion()
                },
                success: function(data, textStatus, xhr) {
                    // update the max version of this plan
                    PLAN_VERSION = data.version;

                    $('#history_cursor').val(data.version);

                    // update the UI buttons to show that you can
                    // perform an undo now, but not a redo
                    $('#history_redo').addClass('disabled');
                    $('#history_undo').removeClass('disabled');

                    updateInfoDisplay();

                    $('#working').dialog('close');
                    $('#assign_district').val('-1');
                    OpenLayers.Element.removeClass(olmap.viewPortDiv,'olCursorWait'); 
                }
            });
        };

        // create a list of available districts, based on the districts
        // that are already in the plan
        var options = $('#assign_district')[0].options;
        var avail = []
        for (var d = 1; d < MAX_DISTRICTS; d++) {
            var dtaken = false;
            for (var o = 0; o < options.length && !dtaken; o++) {
                dtaken = dtaken || ( options[o].text == BODY_MEMBER + d)
            }
            if (!dtaken) {
                avail.push('<option value="'+(d+1)+'">'+BODY_MEMBER+d+'</option>');
            }
        }

        // Create a dialog to get the new district's name from the user.
        // On close, destroy the dialog.
        $('<div id="newdistrictdialog">Please select a district name:<br/><select id="newdistrictname">' + avail.join('') + '</select></div>').dialog({
            modal: true,
            autoOpen: true,
            title: 'New District',
            buttons: { 
                'OK': function() { 
                    createDistrict($('#newdistrictname').val()); 
                    $(this).dialog("close"); 
                    $('#newdistrictdialog').remove(); 
                },
                'Cancel': function() { 
                    $(this).dialog("close"); 
                    $('#newdistrictdialog').remove(); 
                    $('#assign_district').val('-1');
                }
            }
         });
    };

    /*
    * After the map has finished moving, this method updates the jQuery
    * data attributes of the geography and demographics tables if 
    * different districts are now visible
    */
    olmap.prevVisibleDistricts = '';
    var sortByVisibility = function(force) {
        var visibleDistricts = '';
        var visible, notvisible = '';
        for (feature in districtLayer.features) {
            var feature = districtLayer.features[feature];
            var inforow = $('.inforow_' + feature.attributes.district_id);
            if (featureOnScreen(feature, getVisibleBounds())) {
                inforow.data('isVisibleOnMap', true);
                visibleDistricts += feature.id;
            } else {
                inforow.data('isVisibleOnMap', false);
            }
        }
        if (visibleDistricts != olmap.prevVisibleDistricts || force) {
            var demosorter = viewablesorter({ target: '#demographic_table tbody' }).init();
            var geosorter = viewablesorter({ target: '#geography_table tbody' }).init();
            demosorter.sortTable();
            geosorter.sortTable();
            olmap.prevVisibleDistricts = visibleDistricts;
        }

        updateDistrictStyles();
    };

    districtLayer.events.register("loadend", districtLayer, sortByVisibility);
    olmap.events.register("moveend", olmap, sortByVisibility);
    
    // Add the listeners for editing whenever a base layer is changed
    // or the zoom level is changed
    olmap.events.register("changebaselayer", olmap, changeSnapLayer);
    olmap.events.register("zoomend", olmap, changeSnapLayer);
   
    // triggering this event here will configure the map to correspond
    // with the initial dropdown values (jquery will set them to different
    // values than the default on a reload). A desirable side effect is
    // that the map styling and legend info will get loaded, too, so there
    // is no need to explicitly perform doMapStyling() or getMapStyles()
    // in this init method.
    changeSnapLayer();

    // Set the initial map extents to the bounds around the study area.
    olmap.zoomToExtent(maxExtent);
    OpenLayers.Element.addClass(olmap.viewPortDiv, 'olCursorWait');

    // set up sizing for dynamic map size that fills the pg
    initializeResizeFix();
}

IdGeounit = OpenLayers.Class(OpenLayers.Control.GetFeature, {
    /*
     * Initialize this control, enabling multiple selects with a single
     * click.
     */
    initialize: function(options) {
        options = options || {};
        OpenLayers.Util.extend(options, {
            multiple: true,
            clickTolerance: 0.5,
            maxFeatures: 25,
            filterType: OpenLayers.Filter.Spatial.INTERSECTS
        });

        // concatenate events specific to vector with those from the base
        this.EVENT_TYPES =
            OpenLayers.Control.GetFeature.prototype.EVENT_TYPES.concat(
            OpenLayers.Control.prototype.EVENT_TYPES
        );

        options.handlerOptions = options.handlerOptions || {};

        OpenLayers.Control.prototype.initialize.apply(this, [options]);
        
        this.features = {};

        this.handlers = {};
        
        this.handlers.click = new OpenLayers.Handler.Click(this,
            {click: this.selectClick}, this.handlerOptions.click || {});
    },

    selectClick: function(evt) {
        // Set the cursor to "wait" to tell the user we're working on their click.
        OpenLayers.Element.addClass(this.map.viewPortDiv, "olCursorWait");
                        
        var bounds = this.pixelToBounds(evt.xy);
                                        
        this.setModifiers(evt);
        this.request(bounds, {single: false});
    },

    CLASS_NAME: 'IdGeounit'
});

GlobalZoom = OpenLayers.Class(OpenLayers.Control, { 
  // DOM Elements
    
    /** 
     * Property: controlDiv
     * {DOMElement}
     */
    controlDiv: null,

    /*
     * Constructor: GlobalZoom
     * 
     * Parameters:
     * options - {Object}
     */
    initialize: function(options) {
        OpenLayers.Control.prototype.initialize.apply(this, arguments);
    },

    /**
     * APIMethod: destroy 
     */    
    destroy: function() {
        OpenLayers.Event.stopObservingElement(this.controlDiv);
        OpenLayers.Control.prototype.destroy.apply(this, arguments);
    },

    /** 
     * Method: setMap
     *
     * Properties:
     * map - {<OpenLayers.Map>} 
     */
    setMap: function(map) {
        OpenLayers.Control.prototype.setMap.apply(this, arguments);
    },

    /**
     * Method: onZoomToExtent
     *
     * Parameters:
     * e - {Event}
     */
    onZoomToExtent: function(e) {
        this.map.zoomToMaxExtent();
        OpenLayers.Event.stop(e);
    },

    /**
     * Method: draw
     *
     * Returns:
     * {DOMElement} A reference to the DIV DOMElement containing the 
     *     switcher tabs.
     */  
    draw: function() {
        OpenLayers.Control.prototype.draw.apply(this);

        this.loadContents();

        // populate div with current info
        this.redraw();    

        return this.div;
    },
    
    /** 
     * Method: redraw
     * Goes through and takes the current state of the Map and rebuilds the
     *     control to display that state. Groups base layers into a 
     *     radio-button group and lists each data layer with a checkbox.
     *
     * Returns: 
     * {DOMElement} A reference to the DIV DOMElement containing the control
     */  
    redraw: function() {
        return this.div;
    },

    /** 
     * Method: loadContents
     * Set up the labels and divs for the control
     */
    loadContents: function() {

        //configure main div

        OpenLayers.Event.observe(this.div, "click", 
            OpenLayers.Function.bindAsEventListener(
                this.onZoomToExtent, this) );

        // layers list div        
        this.controlDiv = document.createElement("div");
        this.controlDiv.id = this.id + "_controlDiv";
        OpenLayers.Element.addClass(this.controlDiv, "controlDiv");

        this.div.appendChild(this.controlDiv);
    },
    
    CLASS_NAME: "GlobalZoom"
});

