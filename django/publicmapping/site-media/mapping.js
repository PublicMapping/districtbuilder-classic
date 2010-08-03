/*
 * Create an OpenLayers.Layer.WMS type layer.
 *
 * @param name The name of the layer (appears in the layer switcher).
 * @param layer The layer name (or array of names) served by the WMS server.
 * @param extents The extents of the layer -- must be used for GeoWebCache.
 */
function createLayer( name, layer, extents ) {
    return new OpenLayers.Layer.WMS( name,
        'http://' + MAP_SERVER + '/geoserver/gwc/service/wms',
        { srs: 'EPSG:3785',
          layers: layer,
          tiles: 'true',
          tilesOrigin: extents.left + ',' + extents.bottom,
          format: 'image/png'
        },
        {
            displayOutsideMaxExtent: true
        }
    );
}

/*
 * Get the value of the "Snap Map to:" dropdown.
 */
function getSnapLayer() {
    var orig = $('#snapto').val();
    var items = orig.split(';');
    return { layer: items[0], level: items[1] };
}

/* 
 * Get the value of the "Show Layer by:" dropdown.
 */
function getShowBy() {
    return $('#showby').val();
}

/*
 * Get the value of the "Show Boundaries for:" dropdown.
 */
//function getBoundLayer() {
//    return $('#boundfor').val();
//}

/*
 * Get the value of the "Show Districts by:" dropdown. This returns
 * an object with a 'by' and 'modified' property, since the selection
 * of this dropdown may also be 'None' but for performance and query
 * reasons, the subject ID may not be empty.
 */
function getDistrictBy() {
    var orig = $('#districtby').val();
    var mod = new RegExp('^(.*)\.None').test(orig);
    if (mod) {
        orig = RegExp.$1;
    }
    return { by: orig, modified: mod }; 
}

/*
 * The URLs for updating the calculated geography and demographics.
 */
var geourl = '/districtmapping/plan/' + PLAN_ID + '/geography';
var demourl = '/districtmapping/plan/' + PLAN_ID + '/demographics';

function getPlanAndSubjectFilters() {
    var dby = getDistrictBy();
    return new OpenLayers.Filter.Logical({
        type: OpenLayers.Filter.Logical.AND,
        filters: [
            new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'plan_id',
                value: PLAN_ID
            }),
            new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'subject_id',
                value: dby.by
            })
        ]
    });
}

function doMapStyling() {
    //adding proper class names so css may style the PanZoom controls
    $('#OpenLayers\\.Control\\.PanZoomBar_3_panup').addClass('olControlPan olControlPanUpItemInactive');
    $('#OpenLayers\\.Control\\.PanZoomBar_3_panright').addClass('olControlPan olControlPanRightItemInactive');
    $('#OpenLayers\\.Control\\.PanZoomBar_3_pandown').addClass('olControlPan olControlPanDownItemInactive');    
    $('#OpenLayers\\.Control\\.PanZoomBar_3_panleft').addClass('olControlPan olControlPanLeftItemInactive');
    $('#OpenLayers\\.Control\\.PanZoomBar_3_zoomin').addClass('olControlZoom olControlZoomInInactive');   
    $('#OpenLayers\\.Control\\.PanZoomBar_3_zoomout').addClass('olControlZoom olControlZoomOutInactive'); 
    $('#OpenLayers\\.Control\\.PanZoomBar_3_OpenLayers\\.Map_4').addClass('olControlZoom olControlZoomGrabInactive'); 
    $('#OpenLayers_Control_PanZoomBar_ZoombarOpenLayers\\.Map_4').addClass('olControlZoom olControlZoomBarInactive');     
}


/*
 * Initialize the map. This method is called by the onload page event.
 */
function init() {
    OpenLayers.ProxyHost= "/proxy?url=";

    // set up sizing for dynamic map size that fills the pg
    //resizemap();
    //window.onresize = resizemap;

    // The extents of the layers. These extents will depend on the study
    // area; the following are the bounds for the web cache around Ohio.
    // TODO Make the initial layer extents configurable. Maybe fetch them
    // from geowebcache
    var layerExtent = new OpenLayers.Bounds(
        -9442154.0,
        4636574.5,
        -8868618.0,
        5210110.5
    );

    // This projection is web mercator
    var projection = new OpenLayers.Projection('EPSG:3785');

    // Explicitly create the navigation control, since
    // we'll want to deactivate it in the future.
    var navigate = new OpenLayers.Control.Navigation({
        autoActivate: true,
        handleRightClicks: true
    });

    // Create a slippy map.
    var olmap = new OpenLayers.Map('map', {
        // The resolutions here must match the settings in geowebcache.
        // TODO Fetch these resolutions from geowebcache
	resolutions: [2035.2734375, 1017.63671875, 508.818359375, 254.4091796875, 127.20458984375, 63.602294921875, 31.8011474609375, 15.90057373046875, 7.950286865234375, 3.9751434326171875, 1.9875717163085938, 0.9937858581542969, 0.49689292907714844, 0.24844646453857422, 0.12422323226928711, 0.062111616134643555, 0.031055808067321777, 0.015527904033660889, 0.007763952016830444, 0.003881976008415222, 0.001940988004207611, 9.704940021038055E-4, 4.8524700105190277E-4, 2.4262350052595139E-4, 1.2131175026297569E-4],
        maxExtent: layerExtent,
        projection: projection,
        units: 'm',
        controls: [
            navigate,
            new OpenLayers.Control.PanZoomBar()
        ]
    });

    // These layers are dependent on the layers available in geowebcache
    // TODO Fetch a list of layers from geowebcache
    var layers = [];
    for (layer in MAP_LAYERS) {
        layers.push(createLayer( MAP_LAYERS[layer], MAP_LAYERS[layer], layerExtent ));
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
        fontColor: '#ffffff',
        fontSize: '11px',
        fontFamily: 'Arial,Helvetica,sans-serif',
        fontWeight: '400',
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
            protocol: new OpenLayers.Protocol.WFS({
                url: 'http://' + MAP_SERVER + '/geoserver/wfs',
                featureType: 'simple_district',
                featureNS: 'http://gmu.azavea.com/',
                featurePrefix: 'gmu',
                geometryName: 'geom',
                srsName: 'EPSG:3785' 
            }),
            styleMap: new OpenLayers.StyleMap(new OpenLayers.Style(districtStyle)),
            projection: projection,
            filter: getPlanAndSubjectFilters()
        }
    );

    // Create a vector layer to hold the current selection
    // of features that are to be manipulated/added to a district.
    var selection = new OpenLayers.Layer.Vector('Selection',{
        styleMap: new OpenLayers.StyleMap({
            "default": new OpenLayers.Style(
                OpenLayers.Util.applyDefaults(
                    { 
                        fill: false, 
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

    // Create a protocol that is used by all editing controls
    // that selects geography at the specified snap layer.
    var getProtocol = new OpenLayers.Protocol.WFS({
        url: 'http://' + MAP_SERVER + '/geoserver/wfs',
        featureType: getSnapLayer().layer,
        featureNS: 'http://gmu.azavea.com/',
        featurePrefix: 'gmu',
        srsName: 'EPSG:3785',
        geometryName: 'geom'
    });

    var idProtocol = new OpenLayers.Protocol.WFS({
        url: 'http://' + MAP_SERVER + '/geoserver/wfs',
        featureType: 'identify_geounit',
        featureNS: 'http://gmu.azavea.com/',
        featurePrefix: 'gmu',
        srsName: 'EPSG:3785',
        geometryName: 'geom'
    });

    // Create a simple point and click control for selecting
    // geounits one at a time.
    var getControl = new OpenLayers.Control.GetFeature({
        autoActivate: false,
        protocol: getProtocol,
        multipleKey: 'shiftKey',
        toggleKey: 'ctrlKey'
    });

    // Create a rectangular drag control for selecting
    // geounits that intersect a box.
    var boxControl = new OpenLayers.Control.GetFeature({
        autoActivate: false,
        protocol: getProtocol,
        click: false,
        box: true,
        multipleKey: 'shiftKey',
        toggleKey: 'ctrlKey'
    });

    // Update the statistics for the plan.
    var updateStats = function() {
        if (! $('#working').dialog('isOpen')){ 
            $('#working').dialog('open');
        }

        $.ajax({ 
            url: '/districtmapping/plan/' + PLAN_ID + '/updatestats', 
            success: function() {
                $('.geography').load(geourl, {demo: getDistrictBy().by}, loadTooltips);
                $('.demographics').load(demourl, loadTooltips);

                districtLayer.destroyFeatures();
                districtLayer.filter = getPlanAndSubjectFilters();
                districtLayer.strategies[0].load();
            }
        });
    } 

    // Reload the information tabs and reload the filters
    var updateInfoDisplay = function() {
        $('.geography').load(geourl, {demo: getDistrictBy().by}, loadTooltips);
        $('.demographics').load(demourl, loadTooltips);

        districtLayer.destroyFeatures();
        districtLayer.filter = getPlanAndSubjectFilters();
        districtLayer.strategies[0].load();
    };

    // An assignment function that adds geounits to a district
    var assignOnSelect = function(feature) {
        if (selection.features.length == 0)
            return;

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
                geounits: geounit_ids
            },
            success: function(data, textStatus, xhr) {
                var mode = data.success ? 'select' : 'error';
                if (data.success) {
                    updateInfoDisplay();
                }
                else {
                    OpenLayers.Element.removeClass(olmap.viewPortDiv, 'olCursorWait');
                    $('#working').dialog('close');
                }

                for (var i = 0; i < selection.features.length; i++) {
                    selection.drawFeature(selection.features[i], mode);
                }

                $('#assign_district').val('-1');
            },
            error: function(xhr, textStatus, error) {
                window.status = 'failed to select';
            }
        });
    };

    // Create a control that assigns all currently selected
    // (by way of single, rectangle, or polygon tools) units
    // to a district on the map.
    var assignControl = new OpenLayers.Control.SelectFeature(
        districtLayer,
        {
            autoActivate: false,
            onSelect: assignOnSelect
        }
    );

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
                var subtract = this.handler.evt.ctrlKey;
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

                        if (subtract) {
                            var removeMe = [];
                            for (var i = 0; i < rsp.features.length; i++) {
                                var rspFeature = rsp.features[i];
                                for (var j = 0; j < selection.features.length; j++) {
                                    if (selection.features[j].data.id == rspFeature.data.id) {
                                        removeMe.push(selection.features[j]);
                                    }
                                }
                            }
                            selection.removeFeatures(removeMe);
                        }
                        else {
                            // check the selection feature IDs against the
                            // feature IDs from our feature query, so that
                            // features are not added to the selection more
                            // than once
                            for (var i = 0; i < rsp.features.length; i++) {
                                var addflag = true;
                                var rspFeature = rsp.features[i];
                                for (var j = 0; j < selection.features.length; j++) {
                                    if (selection.features[j].data.id == rspFeature.data.id) {
                                        addflag = false;
                                    }
                                }
                                if (addflag) {
                                    selection.addFeatures([rspFeature]);
                                    selection.features[rspFeature.fid || rspFeature.id] = rspFeature;
                                }
                            }
                        }
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

    // Create a div for tooltips on the map itself; these are used
    // when the info tool is activated.
    var tipdiv = document.createElement('div');
    var tipelem = document.createElement('h1');
    tipelem.appendChild(document.createTextNode('District Name'));
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
    olmap.div.insertBefore(tipdiv,olmap.div.firstChild);

    // Create a control that shows the details of the district
    // underneath the cursor.
    var idControl = new IdGeounit({
        autoActivate: false,
        protocol: idProtocol
    });

    // A callback to create a popup window on the map after a peice
    // of geography is selected.
    var idFeature = function(e) {
        var snapto = getSnapLayer().layer;

        // get the range of geolevels
        var maxGeolevel = 0, minGeolevel = 9999;
        for (var i = 0; i < SNAP_LAYERS.length; i++) {
            if (snapto == 'simple_' + SNAP_LAYERS[i].level) {
                maxGeolevel = SNAP_LAYERS[i].geolevel;
            }
            minGeolevel = Math.min(minGeolevel, SNAP_LAYERS[i].geolevel);
        }
        // get the breadcrumbs to this geounit, starting at the
        // largest area (lowest geolevel) first, down to the
        // most specific geolevel
        var crumbs = {};
        var ctics = {};
        var tipFeature = e.features[0];
        for (var glvl = minGeolevel; glvl <= maxGeolevel; glvl++) {
            for (var feat = 0; feat < e.features.length; feat++) {
                if (e.features[feat].data.geolevel_id == glvl) {
                    crumbs[e.features[feat].data.id] = e.features[feat].data.name;
                }
                if (e.features[feat].data.geolevel_id == maxGeolevel) {
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

        var node = 1;
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
    };

        // A callback for feature selection in different controls.
    var featureSelected = function(e){
        // WARNING: not a part of the API!
        var subtract = false;
        for (var type in this.handlers) {
            if ( this.handlers[type].evt ) {
                subtract = subtract || this.handlers[type].evt.ctrlKey;
            }
            else {
                subtract = subtract || this.handlers[type].dragHandler.evt.ctrlKey;
            }
        }

        if (subtract) {
            var removeme = [];
            for (var i = 0; i < selection.features.length; i++) {
                if (selection.features[i].data.id == e.feature.data.id) {
                    removeme.push(selection.features[i]);
                }
            }
            selection.removeFeatures(removeme);
        }
        else {
            for (var i = 0; i < selection.features.length; i++) {
                if (selection.features[i].data.id == e.feature.data.id) {
                    return;
                }
            }
            selection.addFeatures([e.feature]);
        }
    };

    // Connect the featureSelected callback above to the featureselected
    // events in the point and rectangle control.
    getControl.events.register('featureselected', getControl, featureSelected);
    boxControl.events.register('featureselected', boxControl, featureSelected);
    idControl.events.register('featuresselected', idControl, idFeature);

    // A callback for deselecting features from different controls.
    var featureUnselected = function(e){
        selection.removeFeatures([e.feature]);
    };

    // Connect the featureUnselected callback above to the featureunselected
    // events in the point and rectangle control.
    getControl.events.register('featureunselected', this, featureUnselected);
    boxControl.events.register('featureunselected', this, featureUnselected);

    // Connect a method for indicating work when the district layer
    // is reloaded.
    districtLayer.events.register('loadstart',districtLayer,function(){
        OpenLayers.Element.addClass(olmap.viewPortDiv, 'olCursorWait');
    });

    // Recompute the rules for the district styling prior to the adding
    // of the features to the district layer.  This is done at this time
    // to prevent 2 renderings from being triggered on the district layer.
    districtLayer.events.register('beforefeaturesadded',districtLayer,function(context){
        var lowerColor = $('.under').css('background-color');
        var upperColor = $('.over').css('background-color');
        var newOptions = OpenLayers.Util.extend({}, districtStyle);
        var dby = getDistrictBy();
        var rules = [];
        if (!dby.modified) {
            rules = [
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.LESS_THAN_OR_EQUAL_TO,
                        property: 'number',
                        value: RULES[dby.by].lower
                    }),
                    symbolizer: {
                        fillColor: lowerColor,
                        fillOpacity: 0.5
                    }
                }),
                new OpenLayers.Rule({
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.GREATER_THAN_OR_EQUAL_TO,
                        property: 'number',
                        value: RULES[dby.by].upper
                    }),
                    symbolizer: {
                        fillColor: upperColor,
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
                })
            ];
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

        var working = $('#working');
        if (working.dialog('isOpen')) {
            working.dialog('close');
        }
    });

    olmap.events.register('movestart',olmap,function(){
        tipdiv.style.display = 'none';
    });

    // When the navigate map tool is clicked, disable all the 
    // controls except the navigation control.
    $('#navigate_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            active[i].deactivate();
        }
        navigate.activate();
    });

    // When the identify map tool is clicked, disable all the
    // controls except the identify control.
    $('#identify_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            active[i].deactivate();
        }
        idControl.activate();
    });

    // When the single pick tool is clicked, disable all the
    // controls except for the single pick tool.
    $('#single_drawing_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            active[i].deactivate();
        }
        getControl.activate();
        getControl.features = selection.features;
    });

    // When the rectangle selection tool is clicked, disable all the
    // controls except for the rectangle selection tool.
    $('#rectangle_drawing_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            active[i].deactivate();
        }
        boxControl.activate();
        boxControl.features = selection.features;
    });

    // When the polygon selection tool is clicked, disable all the
    // controls except for the polygon selection tool.
    $('#polygon_drawing_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            active[i].deactivate();
        }
        polyControl.activate();
    });

    // When the assignment tool is clicked, disable all the
    // controls except for the assignment tool.  Also remember the
    // last tool that is active.
    $('#assign_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            active[i].deactivate();
        }
        assignControl.activate();
    });

    // Add the created controls to the map
    olmap.addControls([
        getControl,
        boxControl,
        polyControl,
        assignControl,
        new GlobalZoom(),
        idControl
    ]);

    // get a format parser for SLDs and the legend
    var sldFormat = new OpenLayers.Format.SLD();

    // a method that will read the named layer, and return
    // the default style
    var getDefaultStyle = function(sld, layerName) {
        var styles = sld.namedLayers[layerName].userStyles;
        var style;
        for(var i=0; i<styles.length; ++i) {
            style = styles[i];
            if(style.isDefault) {
                break;
            }
        }
        return style;
    }

    //
    // get the styles associated with the current map configuration
    //
    var getMapStyles = function() {
        var snap = getSnapLayer().layer.split('simple_')[1];
        var show = getShowBy();
        OpenLayers.Request.GET({
            url: '/sld/' + snap + '_' + show + '.sld',
            method: 'GET',
            callback: function(xhr){
                var sld = sldFormat.read(xhr.responseXML || xhr.responseText);
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
            }
        });
    };

    // Logic for the 'Snap Map to' dropdown, note that this logic
    // calls the boundsforChange callback
    $('#snapto').change(function(evt){
        var newOpts = getControl.protocol.options;
        var show = getShowBy();
        var snap = getSnapLayer();
        var layers = olmap.getLayersByName('gmu:demo_' + snap.level + '_' + show);

        newOpts.featureType = snap.layer;
        getControl.protocol = 
            boxControl.protocol = new OpenLayers.Protocol.WFS( newOpts );
        olmap.setBaseLayer(layers[0]);
        doMapStyling();
        getMapStyles();
    });

    // Logic for the 'Show Map by' dropdown
    $('#showby').change(function(evt){
        var boundary = getSnapLayer().level;
        var layers = olmap.getLayersByName('gmu:demo_' + boundary + '_' + evt.target.value);
        olmap.setBaseLayer(layers[0]);
        doMapStyling();
        getMapStyles();
    });

    // Logic for the 'Show Districts by' dropdown
    $('#districtby').change(function(evt){
        districtLayer.destroyFeatures();
        districtLayer.filter = getPlanAndSubjectFilters();
        districtLayer.strategies[0].load();
    });

    // Logic for the 'Assign District to' dropdown
    $('#assign_district').change(function(evt){
        if (this.value == '-1'){
            return;
        }
        else if (this.value == 'new'){
            createNewDistrict();
        }
        else {
            var feature = { data:{ district_id: this.value } };
            assignOnSelect(feature);
        }
    });

    /*
    * Ask the user for a new district name, then assign the current selection to the new district upon 
    * successful creation of the district
    */
    var createNewDistrict = function() {
        // Once we have the district name, post a request to the server to create it in the DB
        var callServer = function(name) {
            $.post('/districtmapping/plan/' + PLAN_ID + '/district/new', { name: name }, assignToNewDistrict, 'json');
        };
        // Take the new district info and add the current selection to that districts
        var assignToNewDistrict = function(data, textStatus, XMLHttpRequest) {
            if (data.success) {
                $('#assign_district').append('<option value="' + data.district_id + '">' + data.district_name + '</option>');
                assignOnSelect({data: data});
            } else {
                $('<div class="error">' + data.message + '</div>').dialog({ title: "Sorry", autoOpen: true });
            }
        };
        // Create a dialog to get the new district's name from the user.  On close, destroy the dialog.
        $('<div id="newdistrictdialog">Please enter a name for your new district<input id="newdistrictname" type="text" /></div>').dialog({
            modal: true,
            autoOpen: true,
            title: 'New District',
            buttons: { 
                'OK': function() { callServer($('#newdistrictname').val()); $(this).dialog("close"); $('#newdistrictdialog').remove(); },
                'Cancel': function() { $(this).dialog("close"); $('#newdistrictdialog').remove(); }
            }
         });
    };

    // A method for manually refreshing the statistics in the sidebar
    $('#updatestatsbtn').click( updateStats );

    // Set the initial map extents to the bounds around the study area.
    // TODO Make these configurable.
    olmap.zoomToExtent(new OpenLayers.Bounds(-9467000,4570000,-8930000,5170000));
    OpenLayers.Element.addClass(olmap.viewPortDiv, 'olCursorWait');

    //apply the PanZoom classes
    doMapStyling();
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

