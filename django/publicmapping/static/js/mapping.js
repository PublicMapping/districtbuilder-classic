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
   https://github.com/PublicMapping/

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

/* 
 * Get the value of the "Show Layer by:" dropdown.
 */

function getShowBy() {
    return $('#showby').val();
}

/*
 * Get the value of the "Show Districts by:" dropdown. This returns
 * an object with a 'by' and 'modified' property, since the selection
 * of this dropdown may also be 'None', 'Compactness' or 'Contiguity'
 *  but for performance and query reasons, the subject ID may not be empty.
 */
function getDistrictBy() {
    var sel = $('#districtby');
    var elem = $($('option', sel)[sel[0].selectedIndex]);
    return { 
        by: parseInt(elem.attr('value'),10),
        name: elem.attr('name')
    };
}

/**
 * Get the value of the history cursor.
 */
function getPlanVersion() {
    var ver = $('#history_cursor').val();
    return ver;
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
        var mapElem = $('#mapandmenu')[0];
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
function createToolTipHeader() {
    var tipDiv = $('<div />').addClass('tooltip');
    tipDiv.append($('<h1 />').text(BODY_MEMBER_LONG + gettext(" Name")));
    tipDiv.append($('<div id="tipclose">[x]</div>').click( function(e) {
        OpenLayers.Event.stop(e || event);
        tipDiv.hide();
    }));
    return tipDiv;

}

function createMapTipDiv() {
    var tipDiv = createToolTipHeader();
    tipDiv.addClass('maptip');
    return tipDiv[0];
}

function createDistrictTipDiv() {
    var tipDiv = createToolTipHeader();
    tipDiv.addClass('districtidtip');
    return tipDiv[0];
}

/**
 * Initialize the map from WMS GetCapabilities.
 */
function init() {
    // if the draw tab is disabled, don't init any map jazz.
    if ($('#tab_draw').hasClass('ui-state-disabled')){
        return;
    }

    // set the version cursor
    $('#history_cursor').val(PLAN_VERSION);

    // set the max extent to be the boundaries of the world in
    // spherical mercator to avoid all geowebcache offset issues
    var max = 20037508.342789244;
    var srs = "EPSG:3857";
    var extent = new OpenLayers.Bounds(-max, -max, max, max);

    // ensure the page is fully loaded before the map is initialized
    $(document).ready(function() {
        mapinit( srs, extent );
    });
}

// Timer used to distinguish between single and double clicks
var clickTimer = null;
// Min and max geolevels used for filtering requests to Geoserver
// and for display of demographic info popup.
var geolevelRange;

/**
 * Toggles the highlighting of a district
 * This is called when the Basic Information rows are clicked on
 */
function toggleDistrict(district_id) {
    if (clickTimer) {
        clearTimeout(clickTimer);
        clickTimer = null;
    }
    clickTimer = setTimeout(function() {
        $(this).trigger('toggle_highlighting', [ district_id ]);
        clickTimer = null;
    }, 200);
    
    // needed for multiple click events on a single element
    return true;
}

/**
 * Zooms to the extent of a district
 * This is called when the Basic Information rows are double clicked on
 */
function zoomToDistrict(district_id) {
    if (clickTimer) {
        clearTimeout(clickTimer);
        clickTimer = null;
    }
    $(this).trigger('zoom_to_district', [ district_id ]);
}

/*
 * Initialize the map with extents and SRS pulled from WMS.
 */
function mapinit(srs,maxExtent) {
    var defaultThematicOpacity = 0.8;
    var thematicLayers = [];

    var createLayer = function( name, layer, srs, extents, transparent, visibility, isThematicLayer ) {
        var newLayer = new OpenLayers.Layer.WMS( name,
            MAP_SERVER_PROTOCOL + '//' + MAP_SERVER + '/geoserver/gwc/service/wms',
            {
                srs: srs,
                layers: layer,
                tiles: 'true',
                tilesOrigin: extents.left + ',' + extents.bottom,
                format: 'image/png',
                transparent: true
            },
            {
                visibility: visibility,
                isBaseLayer: false,
                displayOutsideMaxExtent: true,
                opacity: isThematicLayer ? defaultThematicOpacity : 1.0
            }
        );
        if (isThematicLayer) {
            thematicLayers.push(newLayer);
        }
        return newLayer;
    };

    // Set the visible thematic layer. This is a replacement for
    // directly setting the base layer, which can no longer be done
    // since a base map is now being used.
    var setThematicLayer = function (layer) {
        $(thematicLayers).each(function(i, thematicLayer) {
            if (thematicLayer.visibility) {
                thematicLayer.setVisibility(false);
            }
        });
        if (!layer.visibility) {
            layer.setVisibility(true);
        }
    };

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

    OpenLayers.Control.PanZoom.X = 2;
    OpenLayers.Control.PanZoom.Y = 2;

    // Create a slippy map.
    olmap = new OpenLayers.Map('map', {
        maxExtent: maxExtent,
        projection: projection,
        units: 'm',
        panMethod: null,
        controls: [
            navigate,
            new OpenLayers.Control.PanZoomBar(),
            new OpenLayers.Control.KeyboardDefaults()
         ],

        // Restrict panning to the extent of the study area, with a small buffer
        restrictedExtent: STUDY_BOUNDS.scale(2)
    });

    // These layers are dependent on the layers available in geowebcache
    var layers = [];

    // Calculate the minimum zoom level based on the extent of the study area
    var studyWidthMeters = STUDY_EXTENT[2] - STUDY_EXTENT[0];
    var studyHeightMeters = STUDY_EXTENT[3] - STUDY_EXTENT[1];
    var mapWidthPixels = $('div.olMapViewport').width();
    var mapHeightPixels = $('div.olMapViewport').height();
    var hMetersPerPixel = studyWidthMeters / mapWidthPixels;
    var vMetersPerPixel = studyHeightMeters / mapHeightPixels;
    var maxMetersPerPixel = 156543.033928; // at zoom 0 (20037508.342789244 * 2 / 256)

    // maxmpp / 2^zoom = mpp
    // zoom = log(maxmpp/mpp)/log(2)
    var hlevel = Math.log(maxMetersPerPixel / hMetersPerPixel) / Math.LN2;
    var vlevel = Math.log(maxMetersPerPixel / vMetersPerPixel) / Math.LN2;

    var minZoomLevel = (hlevel < vlevel) ? Math.floor(hlevel) : Math.floor(vlevel);
    var maxZoomLevel = 17; // This level is far enough zoomed to view blocks in any state
    var numZoomLevels = maxZoomLevel - minZoomLevel + 1;

    // Set the base layers
    var getLayer = function(provider, mapType) {
        var options = {};
        var types = {};

        switch (provider) {
            case 'bing':
                options = {
                    minZoomLevel: minZoomLevel,
                    maxZoomLevel: maxZoomLevel,
                    projection: projection,
                    sphericalMercator: true,
                    maxExtent: maxExtent    
                };

                types = {
                    aerial: VEMapStyle.Aerial,
                    hybrid: VEMapStyle.Hybrid,
                    road: VEMapStyle.Road 
                };

                options.type = types[mapType];
                if (options.type) {
                    return new OpenLayers.Layer.VirtualEarth(layerName, options);
                }
                break;

            case 'google':
                options = {
                    numZoomLevels: numZoomLevels,
                    minZoomLevel: minZoomLevel,
                    projection: projection,
                    sphericalMercator: true,
                    maxExtent: maxExtent
                };

                types = {
                    aerial: G_SATELLITE_MAP,
                    hybrid: G_HYBRID_MAP, 
                    road: G_NORMAL_MAP
                };

                options.type = types[mapType];
                if (options.type) {
                    return new OpenLayers.Layer.Google(layerName, options);
                }
                break;

            case 'osm':
                options = {
                    numZoomLevels: numZoomLevels,
                    minZoomLevel: minZoomLevel,
                    projection: projection
                };

                // Only road type is supported. OSM does not have aerial or hybrid views.
                if (mapType === 'road') {
                    return new OpenLayers.Layer.OSM(layerName, null, options);
                }
                break;

            case 'arc':
                var layerInfo = TOPO_LAYER_INFO;
                var resolutions = [];
                for (var i = minZoomLevel; i < maxZoomLevel; i++) {
                    resolutions.push(layerInfo.tileInfo.lods[i].resolution);
                }

                var options = {
                    resolutions: resolutions,                        
                    tileOrigin: new OpenLayers.LonLat(layerInfo.tileInfo.origin.x , layerInfo.tileInfo.origin.y),
                    maxExtent: maxExtent,                        
                    projection: projection,
                    minZoomLevel: minZoomLevel
                };

                // Only road type is supported for now.
                if (mapType === 'road') {
                    var url = window.location.protocol + "//services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer";
                    return new OpenLayers.Layer.ArcGISCache(layerName, url, options);
                }
                break;

            default:
                return null;
        }
    };

    // Map type -> label. Also used for determining if there are multiple of the same type.
    var mapTypes = {
        aerial: { label: gettext('Satellite') },
        hybrid: { label: gettext('Hybrid') },
        road: { label: gettext('Road') }
    };

    // Construct each layer, and assign a label.
    $(BASE_MAPS.split(',')).each(function(i, layerName) {
        var hyphenIndex = layerName.indexOf('-');
        if (hyphenIndex <= 0) {
            return null;
        }
        var provider = (layerName.substring(0, hyphenIndex)).toLowerCase();
        var mapType = (layerName.substring(hyphenIndex + 1)).toLowerCase();
        var layer = getLayer(provider, mapType);
        if (layer) {
            var existing = mapTypes[mapType];
            if (existing.layer) {
                existing.layer.name = mapTypes[mapType].label + " (" + existing.provider + ")";
                layer.name = mapTypes[mapType].label + " (" + provider + ")";
            } else {
                layer.name = mapTypes[mapType].label;
                mapTypes[mapType].layer = layer;
                mapTypes[mapType].provider = provider;
            }
            layers.push(layer);
        }
    });

    // If no base maps are configured, add one that's not visible, simply to utilize
    // the resolution information. No tiles will ever be requested
    if (layers.length === 0) {
        var layer = getLayer('osm', 'road');
        layer.setVisibility(false);
        layers.push(layer);
    }

    // Set up the opacity slider and connect change events to control the base and thematic layer opacities
    $('#opacity_slider').slider({
        value: 100 - defaultThematicOpacity * 100,
        slide: function(event, ui) {
            $(olmap.layers).each(function(i, layer) {
                if (!layer.isBaseLayer) {
                    layer.setOpacity(1 - ui.value / 100);
                }
            });
        }
    });

    // Add a row for each base map to the Basemap Settings container for switching
    $(layers).each(function(i, layer) {
        var container = $('#map_type_content_container');
        var id = 'radio' + i;
        var button = $('<input type="radio" name="basemap" id="' + id + '"' + ((i === 0) ? 'checked=checked' : '') +
                       ' /><label for="' + id + '">' + ((layers.length === 1) ? gettext("Map Transparency") : layer.name) + '</label>');

        // change the base layer when a new one is selected
        button.click(function() {
            olmap.setBaseLayer(layer);
        });
           
        container.append(button);
    });

    // Turn the radios into a buttonset
    $('#map_type_content_container').buttonset();

    // Set the default map type label
    $('#base_map_type').html(layers[0].name);

    // Handle Fix Unassigned requests
    $('#fix_unassigned').click(function(){
        var pleaseWait = $('<div />').text(gettext('Please wait. Fixing unassigned blocks. This may take a couple minutes.')).dialog({
            modal: true,
            autoOpen: true,
            title: gettext('Fixing Unassigned'),
            escapeOnClose: false,
            resizable:false,
            open: function() { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); }                    
        });

        $.ajax({
            type: 'POST',
            url: '/districtmapping/plan/' + PLAN_ID + '/fixunassigned/',
            data: { version: getPlanVersion() },
            success: function(data, textStatus, xhr) {
                pleaseWait.remove();
                if (data.success) {
                    var updateAssignments = true;
                    $('#map').trigger('version_changed', [data.version, updateAssignments]);
                }
                $('<div>' + data.message + '</div>').dialog({
                    modal: false,
                    autoOpen: true,
                    resizable:false,
                    title: (data.success ? gettext('Success') : gettext('Error')),
                    buttons: [{
                        text: gettext('OK'),
                        click: function() { $(this).dialog('close'); }
                    }]
                });
            },
            error: function(xhr, textStatus, error) {
                pleaseWait.remove();
                $('<div />').text(gettext('Error encountered while fixing unassigned')).dialog({
                    modal: true, autoOpen: true, title: gettext('Error'), resizable:false
                });
            }
        });
    });

    // Handle show splits requests
    $('#show_splits_button').click(function(){
        var referenceLayerId = $('#reference_layer_select').val();
        if (!referenceLayerId || (referenceLayerId === 'None')) {
            $('<div />').text(gettext('No reference layer selected.')).dialog({
                modal: true, autoOpen: true, title: gettext('Warning'), resizable:false,
                buttons: [{
                    text: gettext('OK'),
                    click: function(){
                        $(this).dialog('close');
                        $('#choose_layers_button').click();
                    }
                }]
            });
            return;
        }

        var urlSuffix = '';
        if (DB.util.startsWith(referenceLayerId, 'plan')) {
            urlSuffix = 'plan/' + referenceLayerId.substring('plan.'.length);
        } else {
            urlSuffix = 'geolevel/' + referenceLayerId.substring('geolevel.'.length);
        }

        var waitDialog = $('<div />').text(gettext('Please wait. Querying for splits.'))
                .dialog({
            modal: true,
            autoOpen: true,
            title: gettext('Finding Splits'),
            escapeOnClose: false,
            resizable:false,
            open: function() { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); }
        });

        $.ajax({
            type: 'GET',
            url: '/districtmapping/plan/' + PLAN_ID + '/splits/' + urlSuffix + '/',
            data: { version: getPlanVersion() },
            success: function(data, textStatus, xhr) {
                waitDialog.remove();
                if (data.success) {
                    setHighlightedDistricts(data.above_ids);
                    if (data.splits.length === 0) {
                        $('<div />').text(gettext('This plan contains no splits.')).dialog({
                            modal: true, autoOpen: true, title: gettext('No Splits Found'), resizable:false
                        });                
                    }
                } else {
                    $('<div />').text(gettext('Error encountered while querying for splits: ') + data.message).dialog({
                        modal: true, autoOpen: true, title: gettext('Error'), resizable:false
                    });                
                }
            },
            error: function(xhr, textStatus, error) {
                waitDialog.remove();                        
                $('<div />').text(gettext('Error encountered while querying for splits: ') + textStatus).dialog({
                    modal: true, autoOpen: true, title: gettext('Error'), resizable:false
                });                
            }
        });

        return;
    });

    // Change basemap selectoor styling if there is more than 1 choice
    if (layers.length > 1) {
        $('#map_type_settings').addClass('multiple');
        $('#settings_toggle').addClass('multiple');
        $('#map_settings_content').addClass('multiple');
    }

    // Construct map layers, ensuring boundary layers are at the end of the list for proper overlaying
    for (i in MAP_LAYERS) {
        var layerName = MAP_LAYERS[i];
        layers.unshift(createLayer( layerName, layerName, srs, maxExtent, false, true, true ));
    }

    for (i in SNAP_LAYERS) {
        layer = SNAP_LAYERS[i];
        var layerName = 'geolevel.' + layer.geolevel;
        var featureName = NAMESPACE + ':' + layer.level + '_boundaries';
        layers.push(createLayer( layerName, featureName, srs, maxExtent, true, false, false ));

    } 

    // The strategy for loading the districts. This is effectively
    // a manual refresh, with no automatic reloading of district
    // boundaries except when explicitly loaded.
    var districtStrategy = new OpenLayers.Strategy.BBOX({ratio:2});
    var refreshStrategy = new OpenLayers.Strategy.Refresh({force:true});
    var highlightStrategy = new OpenLayers.Strategy.BBOX({ratio:2});

    // The style for the districts. This serves as the base
    // style for all rules that apply to the districtLayer
    var districtStyle = {
        fill: true,
        fillOpacity: 0.01,    // need some opacity for picking districts
        fillColor: '#fdB913', // with ID tool -- fillColor needed, too
        strokeColor: '#fdB913',
        strokeOpacity: .5,
        strokeWidth: 2,
        label: '${label}',
        fontColor: '#663300',
        fontSize: '10pt',
        fontFamily: 'Arial,Helvetica,sans-serif',
        fontWeight: '800',
        labelAlign: 'cm'
    };

    // The style for the highlighted district layer
    var highlightColor = $('.highlighted').css('background-color');
    var highlightStyle = {
        fill: false,
        fillColor: highlightColor,
        strokeColor: highlightColor,
        strokeOpacity: .75,
        strokeWidth: 2
    };

    // The style for reference layers
    var referenceColor = $('.reference').css('background-color');
    var referenceStyle = {
        fill: false,
        strokeColor: referenceColor,
        strokeOpacity: .35,
        strokeWidth: 3,
        label: '${label}',

        // Starts off with labels, but can be toggled with a checkbox
        fontSize: '10pt',
        fontColor: referenceColor,
        fontFamily: 'Arial,Helvetica,sans-serif',
        fontWeight: '800',
        labelAlign: 'cm'
    };

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

        return { 
            layer: min_layer.layer, 
            level: min_layer.level,
            name: min_layer.level,
            display: min_layer.long_description, 
            geolevel: min_layer.geolevel
        };
    }

    /**
     * Get the OpenLayers filters that describe the version and subject
     * criteria for the district layer.
     *
     * geometry is optional, and when passed in adds an additional intersection filter on the geometry.
     * district_ids is an optional array of integers, and when passed in filters by district_ids
     */
    var getVersionAndSubjectFilters = function(extent, geometry, district_ids) {
        var dby = getDistrictBy();
        var ver = getPlanVersion();
        var lyr = getSnapLayer();
        var filters = [
            new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'version',
                value: ver
            }),
            new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'subject',
                value: (dby.by > 0) ? dby.by : 1
            }),
            new OpenLayers.Filter.Spatial({
                type: OpenLayers.Filter.Spatial.BBOX,
                value: extent
            }),
            new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'level',
                value: lyr.geolevel
            })
        ];
        if (geometry) {
            filters.push(new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'geom',
                value: geometry
            }));
        }
        if (district_ids !== undefined) {
            filters.push(new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'district_ids',
                value: district_ids.join(',')
            }));
        }
        return new OpenLayers.Filter.Logical({
            type: OpenLayers.Filter.Logical.AND,
            filters: filters
        });
    };
    
    // A vector layer that holds all the districts in
    // the current plan.
    var districtLayer = new OpenLayers.Layer.Vector(
        'Current Plan',
        {
            strategies: [
                districtStrategy,
                refreshStrategy
            ],
            protocol: new OpenLayers.Protocol.HTTP({
                url: '/districtmapping/plan/' + PLAN_ID + '/district/versioned/',
                format: new OpenLayers.Format.GeoJSON()
            }),
            styleMap: new OpenLayers.StyleMap({'default':new OpenLayers.Style(districtStyle)}),
            projection: projection,
            filter: getVersionAndSubjectFilters(maxExtent),
            opacity: defaultThematicOpacity
        }
    );

    // A vector layer that holds all highlighted districts
    var highlightLayer = new OpenLayers.Layer.Vector(
        'Highlighted Districts',
        {
            strategies: [
                highlightStrategy
            ],
            protocol: new OpenLayers.Protocol.HTTP({
                url: '/districtmapping/plan/' + PLAN_ID + '/district/versioned/',
                format: new OpenLayers.Format.GeoJSON()
            }),
            styleMap: new OpenLayers.StyleMap(new OpenLayers.Style(highlightStyle)),
            projection: projection,
            filter: getVersionAndSubjectFilters(maxExtent, null, [])
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
                        fillColor: '#fdB913',
                        strokeColor: '#fdB913'
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

    // Add these layers to the map
    layers.push(districtLayer);
    layers.push(highlightLayer);
    layers.push(selection);
    olmap.addLayers(layers);

    // If a base map is intentionally not configured, make it invisible, and remove settings tool
    if (!BASE_MAPS) {
        olmap.baseLayer.setVisibility(false);
        $('#map_settings').hide();
    }

    // Create a protocol that is used by all editing controls
    // that selects geography at the specified snap layer.
    var getProtocol = new OpenLayers.Protocol.HTTP({
        url: '/districtmapping/plan/' + PLAN_ID + '/unlockedgeometries/',
        readWithPOST: true,
        format: new OpenLayers.Format.GeoJSON()
    });

    var idProtocol = new OpenLayers.Protocol.WFS({
        url: MAP_SERVER_PROTOCOL + '//' + MAP_SERVER + '/geoserver/wfs',
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

    // Add header for CSRF validation. This is needed, because setting
    // the headers parameter does not work when performing POSTs (it's hardcoded).
    var extendReadForCSRF = function(protocol) {
        OpenLayers.Util.extend(protocol, {
            read: function(options) {
                OpenLayers.Protocol.prototype.read.apply(this, arguments);
                options = OpenLayers.Util.applyDefaults(options, this.options);
                options.params = OpenLayers.Util.applyDefaults(options.params, this.options.params);
                if(options.filter) {
                    options.params = this.filterToParams(options.filter, options.params);
                }
                var resp = new OpenLayers.Protocol.Response({requestType: "read"});
                resp.priv = OpenLayers.Request.POST({
                    url: options.url,
                    callback: this.createCallback(this.handleRead, resp, options),
                    data: OpenLayers.Util.getParameterString(options.params),
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRFToken": $('input[name=csrfmiddlewaretoken]').val()
                    }
                });
                return resp;
            }
        });
    };

    // Extend the request function on the GetFeature control to allow for
    // dynamic filtering and setting a header needed for CSRF validation
    var filterExtension = {
        request: function (bounds, options) {
            // Allow for dynamic filtering, and extend for CSRF validation headers
            var filter = getVersionAndSubjectFilters(maxExtent, bounds.toGeometry().toString());
            extendReadForCSRF(this.protocol);

            // The rest of this function is exactly the same as the original
            options = options || {};
            OpenLayers.Element.addClass(this.map.viewPortDiv, "olCursorWait");
        
            this.protocol.read({
                filter: filter,
                callback: function(result) {
                    if(result.success()) {
                        if(result.features.length) {
                            if(options.single == true) {
                                this.selectBestFeature(result.features, bounds.getCenterLonLat(), options);
                            } else {
                                this.select(result.features);
                            }
                        } else if(options.hover) {
                            this.hoverSelect();
                        } else {
                            this.events.triggerEvent("clickout");
                            if(this.clickout) {
                                this.unselectAll();
                            }
                        }
                    }
                    OpenLayers.Element.removeClass(this.map.viewPortDiv, "olCursorWait");
                },
                scope: this                        
            });
        }
    };

    // Apply the filter extension to both the get and box controls
    OpenLayers.Util.extend(getControl, filterExtension);
    OpenLayers.Util.extend(boxControl, filterExtension);

    // Reload the information tabs and reload the filters
    var updateInfoDisplay = function() {
        $('#open_statistics_editor').trigger('dirty_cache');
        $('#open_statistics_editor').trigger('refresh_tab');
        $('#map').trigger('resort_by_visibility', [true]);
        districtLayer.filter = getVersionAndSubjectFilters(olmap.getExtent());
        refreshStrategy.refresh();
        $('#map').trigger('draw_highlighted_districts');
    };

    var versionChanged = function(evt, version, updateAssignments) {
        if (version > PLAN_VERSION) {
            // update the max version of this plan
            PLAN_VERSION = version;
            PLAN_HISTORY[PLAN_VERSION] = true;
        }

        // set the version cursor
        $('#history_cursor').val(version);

        if (version == PLAN_VERSION) {
            // update the UI buttons to show that you can
            // perform an undo now, but not a redo
            $('#history_redo').addClass('disabled');
            $('#history_undo').removeClass('disabled');
        }
        else {
            $('#history_redo').removeClass('disabled');
            $('#history_undo').addClass('disabled');
        }

        updateInfoDisplay();
        if (updateAssignments) {
            updateAssignableDistricts();
        }
    };
    $('#map').bind('version_changed', versionChanged);

    var styleChanged = function(evt, newStyle, layername) {
        if (layername == districtLayer.name) {
            districtLayer.styleMap = new OpenLayers.StyleMap(newStyle);
            districtLayer.redraw();

            updateDistrictStyles();
        }
    };
    $('#map').bind('style_changed', styleChanged);

    // Update reference layer on map when the reference layer drop down is changed
    // referenceLayerId is one of: None, plan.XXX, geolevel.XXX
    var currentReferenceLayer;
    var referenceLayerChanged = function(evt, referenceLayerId, referenceLayerName) {
        if (referenceLayerId === 'None') {
            hideCurrentReferenceLayer();
            $('#map').trigger('style_changed', [null, referenceLayerId]);
            return;
        }
            
        var layer = olmap.getLayersByName(referenceLayerId);
        if (layer.length == 0) {
            hideCurrentReferenceLayer();

            layer = createReferenceLayer(referenceLayerId);
            if (layer == undefined) { currentReferenceLayer = undefined; return; }
            olmap.addLayer(layer);
            // slide this layer down the stack
            olmap.raiseLayer(layer, olmap.getLayerIndex(districtLayer) - olmap.getLayerIndex(layer));
            layer.setVisibility(true);
            if (layer.CLASS_NAME === 'OpenLayers.Layer.Vector') {
                layer.refresh();
            }
            currentReferenceLayer = referenceLayerId;
        } else {
            layer = layer[0];
            if (referenceLayerId == currentReferenceLayer) {
                // Already viewing this layer
            } else {
                hideCurrentReferenceLayer();
                layer.setVisibility(true);
                if (layer.CLASS_NAME === 'OpenLayers.Layer.Vector') {
                    layer.refresh();
                }
                currentReferenceLayer = referenceLayerId;
            }
        }
        $('#map').trigger('style_changed', [referenceStyle, layer.id]);
    };
    $('#map').bind('reference_layer_changed', referenceLayerChanged);

    // Update reference layer labels when the label check box changes
    var referenceLayerLabelsChecked = function(evt, isChecked) {
        if (!currentReferenceLayer) { return; }

        var layers = olmap.getLayersByName(currentReferenceLayer);
        if (layers.length == 0) { return; }

        layers[0].styleMap.styles['default'].defaultStyle.label = (isChecked ? "${label}" : "");
        layers[0].redraw();
    };
    $('#map').bind('reference_layer_labels_checked', referenceLayerLabelsChecked);

    // Create a reference layer with the appropriate styling and
    // strategy
    var createReferenceLayer = function(referenceLayerId) {
        var layerIdPattern = /(.+)\.(\d+)$/;
        var matches = layerIdPattern.exec(referenceLayerId);
        var layerType = matches[1];
        var layerId = matches[2];

        if (layerType === 'plan') {
            // get version and subject filters
            var filter = getVersionAndSubjectFilters(maxExtent);
            // remove version criteria
            filter.filters = filter.filters.splice(1);


            return new OpenLayers.Layer.Vector(
                referenceLayerId,
                {
                    strategies: [
                        new OpenLayers.Strategy.BBOX({ratio:2})
                    ],
                    protocol: new OpenLayers.Protocol.HTTP({
                        url: '/districtmapping/plan/' + layerId + '/district/versioned/',
                        format: new OpenLayers.Format.GeoJSON()
                    }),
                    styleMap: new OpenLayers.StyleMap(new OpenLayers.Style(referenceStyle)),
                    projection: projection,
                    filter: filter
                }
            );
        } // otherwise the "geolevel" reference layers are already created
    };

    // Hide the current reference layer and reset the currentReferenceLayer variable
    var hideCurrentReferenceLayer = function() {
        if (currentReferenceLayer) {
            var current = olmap.getLayersByName(currentReferenceLayer)[0];
            current.setVisibility(false);
            currentReferenceLayer = undefined;
        }
    };

    // Track whether we've already got an outbound request to the server to add districts
    var outboundRequest = false;
    // An assignment function that adds geounits to a district
    var assignOnSelect = function(feature) {
        // If there's an outbound request, hold the user from more clicking
        if (outboundRequest === true) {
            $('<div id="busyDiv" />').text(gettext('Please wait until your previous changes have been accepted.')).dialog({
                modal: true,
                autoOpen: true,
                title: gettext('Busy'),
                buttons: [{
                    text: gettext('OK'),
                    click: function() {
                        $('#busyDiv').remove();
                    }
                }]
            });
            return false;
        }

        if (selection.features.length == 0) {
            $('#assign_district').val('-1');
            return;
        }

        outboundRequest = true;

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
            url: '/districtmapping/plan/' + PLAN_ID + '/district/' + district_id + '/add/',
            data: {
                geolevel: geolevel_id,
                geounits: geounit_ids,
                version: getPlanVersion()
            },
            success: function(data, textStatus, xhr) {
                var mode = data.success ? 'select' : 'error';
                outboundRequest = false;
                if (data.success) {
                    // if no districts were updated, display a warning
                    if (!data.updated) {
                        OpenLayers.Element.removeClass(olmap.viewPortDiv, 'olCursorWait');
                        $('#working').dialog('close');
                        $('<div id="errorDiv" />').text(gettext('No districts were updated')).dialog({
                            modal: true,
                            autoOpen: true,
                            title: gettext('Error'),
                            buttons: [{
                                text: gettext('OK'),
                                click: function() {
                                    $('#errorDiv').remove();
                                }
                            }]
                        });
                        updateInfoDisplay();
                    } else {
                        var updateAssignments = false;
                        $('#map').trigger('version_changed', [data.version, updateAssignments]);
                        $('#saveplaninfo').trigger('planSaved', [ data.edited ]);
                    }
                }
                else {
                    if ('redirect' in data) {
                        window.location.href = data.redirect;
                        return;
                    }
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
                outboundRequest = false;
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
                $('<div  id="toomanyfeaturesdialog" />').text(gettext('You cannot select that many features at once.\n\nConsider drawing a smaller area with the selection tool.')).dialog({
                    modal: true,
                    autoOpen: true,
                    title: gettext('Sorry'),
                    buttons: [{
                        text: gettext('OK'),
                        click: function() {
                            $('#toomanyfeaturesdialog').remove();
                        }
                    }]
                });
                return;
            } else if (features.length + selection.features.length > FEATURE_LIMIT) {
                $('<div id="toomanyfeaturesdialog" />').text(gettext('You cannot select any more features.\n\nConsider assigning your current selection to a district first.')).dialog({
                    modal: true,
                    autoOpen: true,
                    title: gettext('Sorry'),
                    buttons: [{
                        text: gettext('OK'),
                        click: function() {
                            $('#toomanyfeaturesdialog').remove();
                        }
                    }]
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
            if (parseInt(d_id,10) > -1) {
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

            $(document).bind('keyup', cancelDragDrop);

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
                getControl.protocol = new OpenLayers.Protocol.HTTP( newOpts );
                extendReadForCSRF(getControl.protocol);
                
                getControl.protocol.read({
                    filter: getVersionAndSubjectFilters(maxExtent, feature.geometry),
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
    }, 1000);

    // Create a tooltip inside of the map div
    var tipdiv = createMapTipDiv();
    olmap.div.insertBefore(tipdiv,olmap.div.firstChild);

    // Create a control that shows the details of the district
    // underneath the cursor.
    var idControl = new IdGeounit({
        autoActivate: false,
        protocol: idProtocol
    });

    var districtSelectTool = new OpenLayers.Control.SelectFeature(
        districtLayer,
        {
            hover: false,
            clickFeature: function(feature, event) {
                // Show a dialog asking to unmerge
                // to combine with unassigned
                var buttons = [
                    { 
                        text: gettext('OK'),
                        click: function() {
                            $(this).dialog('close');
                            // submit an ajax call to the handler
                            $('#working').dialog('open');
                            $.ajax({
                                type: 'POST',
                                url: '/districtmapping/plan/' + PLAN_ID + '/combinedistricts/',
                                data: {
                                    from_district_id: feature.attributes.district_id,
                                    to_district_id: 0, /*Always Unassigned */
                                    version: getPlanVersion()
                                },
                                success: function(data, textStatus, xhr) {
                                    $('#working').dialog('close');
                                    if (data.success == true) {
                                        var updateAssignments = true;
                                        $('#map').trigger('version_changed', [data.version, updateAssignments]);
                                    } else {
                                        $('<div class="error" />').attr('title', gettext('Sorry'))
                                            .text(gettext('Unable to combine districts: ') + 
                                            data.message ).dialog({
                                                modal: true,
                                                autoOpen: true,
                                                resizable: false
                                        });
                                    }
                                }
                            });
                        }
                    },{
                        text: gettext('No'),
                        click: function() {
                            $(this).dialog('close');
                        }
                    }
                ];

                $('<div id="unassign_district" />').text(
                        gettext('Would you like to unassign the geography in ') + 
                        feature.attributes.name + '?').dialog({
                    resizable: false,
                    modal: true,
                    buttons: buttons,
                    modal: true
                }); // end dialog
        }
    });


    var districtIdDiv = createDistrictTipDiv();
    olmap.div.insertBefore(districtIdDiv,olmap.div.firstChild);

    var districtIdControl = new OpenLayers.Control.SelectFeature(
        districtLayer,
        {
            hover: false,
            onSelect: (function(){
                var showTip = function(tipFeature, pixel) {
                    $(districtIdDiv.firstChild).text(tipFeature.attributes.label);

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

    var districtComment = $('#districtComment');
    var districtCommentErr = $('#districtCommentError');
    var infoErrorCallback = function(xhr, textStatus, message) {
        districtComment.dialog('close');
        districtCommentErr.dialog('open');
    };

    var infoSuccessCallback = function(data, textStatus, xhr) {
        if (xhr.status == 200 && data.success) {
            if ($('#id_district_pk').val() == '0') {
                var mode = data.success ? 'select' : 'error';
                for (var i = 0; i < selection.features.length; i++) { 
                    selection.drawFeature(selection.features[i], mode);
                }
            }
            else {
                districtComment.dialog('close');
            }

            PLAN_VERSION = data.version;
            var updateAssignments = true;
            $('#map').trigger('version_changed', [data.version,updateAssignments]);
            $('#working').dialog('close');
            OpenLayers.Element.removeClass(olmap.viewPortDiv,'olCursorWait'); 
        }
        else {
            infoErrorCallback(xhr, textStatus, gettext('Sorry, your information could not be saved. Please try again later.'));
        }
    };

    var postInfo = function(evt) {
        var label_field = $('#id_label');
        if (label_field.val() == '') {
            label_field.removeClass('field');
            label_field.addClass('error');
            evt.stopPropagation();
            return false;
        }

        var data = {
            district_id: $('#id_district_id').val(),
            district_short: label_field.val(),
            district_long: label_field.val(),
            comment: $('#id_comment').val(),
            type: $('#id_type').val().split(','),
            version: getPlanVersion()
        };
        var typeList = $('#id_typelist');
        for (var i = 0; i < data.type.length; i++) {
            var type = data.type[i].trim();
            data.type[i] = type;
            if (!typeList.children().is('*[value="' + escape(type) + '"]')) {
                var newopt = $('<option/>')
                    .text(type)
                    .attr('value', type);
                $('#id_typelist').append(newopt);
            }
        }
        
        var url = '/districtmapping/plan/' + PLAN_ID + '/district/';

        if ($('#id_district_pk').val() == '0') {
            // creating a new district
            var geounit_ids = [];
            for (var i = 0; i < selection.features.length; i++) {
                geounit_ids.push( selection.features[i].attributes.id );
            }
            geounit_ids = geounit_ids.join('|');
            $.extend(data, {
                geolevel: selection.features[0].attributes.geolevel_id,
                geounits: geounit_ids
            });
            url += 'new/';
        }
        else {
            // editing an existing district
            url += data.district_id + '/info/';
            $.extend(data, {
                object_pk: $('#id_district_pk').val()
            });
        }

        OpenLayers.Element.addClass(olmap.viewPortDiv,'olCursorWait');
        if ($('#id_district_pk').val() == '0') {
            districtComment.dialog('close');
            $('#working').dialog('open');
        }

        $.ajax({
            type: 'POST',
            url: url,
            data: data,
            success: infoSuccessCallback,
            error: infoErrorCallback
        });

        evt.stopPropagation();
        return false;
    }

    districtComment.dialog({
        resizable: false,
        modal: true,
        draggable: true,
        autoOpen: false,
        buttons: [{
            text: gettext('Save'),
            click: postInfo
        }],
        open: function(){
            var typeRE = new RegExp('([^,]+)','g');
            var label_field = $('#id_label');
            label_field.removeClass('error');
            label_field.addClass('field');

            // cache this every time the dialog is opened
            var opts = $('#id_typelist option');

            // fetch all types specified in this plan -- they may have
            // been added dynamically, and not come from the DB
            var typeValues = $('.districtComment input.infoType');
            for (var i = 0; i < typeValues.length; i++) {
                if (typeValues[i].value.trim().length == 0) {
                    continue;
                }
                var exists = false;
                var vals = typeValues[i].value.split(',');
                for (var j = 0; j < vals.length; j++) {
                    for (var k = 0; k < opts.length; k++) {
                        exists = exists || (vals[j].toLowerCase() == opts[k].value.toLowerCase());
                    }
                }
                if (!exists) {
                    var newopt = $('<option />')
                        .text(typeValues[i].value)
                        .attr('value', typeValues[i].value);
                    $('#id_typelist').append(newopt);
                }
            }

            opts = $('#id_typelist option');

            var types = $('#id_type').val().match(typeRE);
            if (types != null) {
                var selection = [];
                for (var i = 0; i < types.length; i++) {
                    var exists = false;
                    var type = types[i].trim();
                    for (var j = 0; j < opts.length; j++) {
                        exists = exists ||
                            (type.toLowerCase() == 
                             opts[j].value.toLowerCase());
                    }
                    if (!exists) {
                        var newopt = $('<option />')
                            .text(type)
                            .attr('value', type);
                        $('#id_typelist').append(newopt);
                    }
                    selection.push(type);
                }
                $('#id_typelist').val(selection);
            }

            opts = $('#id_typelist option');

            // select any tags like this one (case insensitive match)
            $('#id_type').keyup(function(evt){
                var keytypes = $(this).val().match(typeRE);
                if (keytypes != null) {
                    var selection = [];
                    for(var i = 0; i < opts.length; i++) {
                        var selected = false;
                        for (var j = 0; j < keytypes.length; j++) {
                            selected = selected || 
                                (opts[i].value.toLowerCase() == 
                                 keytypes[j].trim().toLowerCase());
                        }
                        if (selected) {
                            selection.push(opts[i].value);
                        }
                    }
                    $('#id_typelist').val(selection);
                }
            });

            $('#id_typelist').change(function(evt){
                var selection = $(this).val() || [];
                $('#id_type').val( selection.join(', ') );
            });
        }
    });
    districtCommentErr.dialog({
        resizable: false,
        modal: true,
        draggable: true,
        autoOpen: false,
        buttons: [{
            text: gettext('Close'),
            click: function() {
                districtCommentErr.dialog('close');
            }
        }]
    });

    // Create a tool that toggles whether a district is locked when clicked on.
    var lockDistrictControl = new OpenLayers.Control.SelectFeature(
        districtLayer,
        {
            clickFeature: function(feature) {
                $.ajax({
                    type: 'POST',
                    url: '/districtmapping/plan/' + PLAN_ID + '/district/' + feature.attributes.district_id + '/lock/',
                    data: {
                        lock: !feature.attributes.is_locked,
                        version: getPlanVersion()
                    },
                    success: function(data, textStatus, xhr) {
                        selection.removeFeatures(selection.features);
                        refreshStrategy.refresh();
                    }
                });
            }
        }
    );

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
                if (dist != null) {
                    $('#assign_district').val(dist.data.district_id);
                }
                else {
                    $('#assign_district').val('-1');
                }
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

    // canel callback for ESC button
    var cancelDragDrop = function(evt) {
        var KEYCODE_ESC = 27;
        if (evt.keyCode == KEYCODE_ESC) {
            selection.removeFeatures(selection.features);

            $('#assign_district').val('-1');
            dragdropControl.deactivate();
            dragdropControl.resumeTool.activate();
        }
    };

    var getMinMaxGeolevels = function(snapToLayer) {
        // get the range of geolevels
        var maxGeolevel = 0, minGeolevel = 9999;
        for (var i = 0; i < SNAP_LAYERS.length; i++) {
            if (snapToLayer == 'simple_' + SNAP_LAYERS[i].level) {
                minGeolevel = SNAP_LAYERS[i].geolevel;
            }
            maxGeolevel = Math.max(maxGeolevel, SNAP_LAYERS[i].geolevel);
        }

        return {
            'min': minGeolevel,
            'max': maxGeolevel
        }
    };

    // A callback to create a popup window on the map after a piece
    // of geography is selected.
    var idFeature = function(e) {
        var minGeolevel = geolevelRange.min;
        var maxGeolevel = geolevelRange.max;

        // get the breadcrumbs to this geounit, starting at the
        // largest area (lowest geolevel) first, down to the
        // most specific geolevel
        var crumbs = {};
        var ctics = [];
        var tipFeature = e.features[0];
        for (var glvl = maxGeolevel; glvl >= minGeolevel; glvl--) {
            for (var feat = 0; feat < e.features.length; feat++) {
                if (parseInt(e.features[feat].data.geolevel_id) === glvl) {
                    crumbs[e.features[feat].data.id] = e.features[feat].data.name;
                    if (glvl === minGeolevel) {
                        tipFeature = e.features[feat];
                        for (var demo = 0; demo < DEMOGRAPHICS.length; demo++) {
                            if (parseInt(tipFeature.data.subject_id) === DEMOGRAPHICS[demo].id) {
                                var text = DEMOGRAPHICS[demo].text;
                                text = DB.util.startsWith(text, '% ') ? text.substr(2) : text;
                                ctics.push({ lbl: text, val:parseFloat(tipFeature.data.number) });
                            }
                        }
                    }
                }
            }
        }

        // Now, get the full version, with geometry included, so that we can calculate the centroid
        idProtocol.read({
            filter: new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                value: tipFeature.data.id,
                property: 'id'
            }),
            maxFeatures: 1,
            callback: function(resp) {
                tipFeature = resp.features[0];
                tipdiv.style.display = 'none';

                // Clear out the map tip div
                $(tipdiv).find('.demographic').remove();

                // sort the characteristics alphabetically by label
                ctics = $(ctics).sort(function(a, b) { return a.lbl > b.lbl; });

                // truncate the breadcrumbs into a single string
                var place = [];
                for (var key in crumbs) {
                    place.push(crumbs[key]);
                }
                place = place.join(' / ');

                var centroid = tipFeature.geometry.getCentroid();
                var lonlat = new OpenLayers.LonLat( centroid.x, centroid.y );
                var pixel = olmap.getPixelFromLonLat(lonlat);
                $(tipdiv).find('h1').text(place);
                var select = $('#districtby')[0];
                var value = parseInt(tipFeature.attributes.number, 10);

                if (ctics.length > 0) {
                    $(ctics).each(function(i, obj) {
                        try {
                            var demographic = $('<div class="demographic"/>').html(
                                obj.lbl + ': ' + Math.round(obj.val).toLocaleString()
                            );
                            $(tipdiv).append(demographic);
                        } catch (exception) {
                            // too many characteristics
                        }
                    });

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
                    tipdiv.style.display = 'block';
                } else {
                    $("<div>Couldn't retrieve demographic info for that geounit. " +
                            "Please select another.</div>").dialog({
                        title: 'No demographics available',
                        resizable: false,
                        modal: true
                    });
                }

                if (tipdiv.pending) {
                    clearTimeout(tipdiv.timeout);
                    tipdiv.pending = false;
                }

                // hide the other tip
                districtIdDiv.style.display = 'none';
            }
        });

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
                var offset = $('.map_menu_content').offset();
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

    /**
     * Generic compute average function designed to compute averages of features
     * from a list of items.
     * 
     * @param {array} features list of objects with a feature to compute average from
     * @param {string} featureName attribute to calculate average from item
     */
    var computeAvg = (function () {

        var scoreCache = {};

        var average = function(a){
            //+ Carlos R. L. Rodrigues
            //@ http://jsfromhell.com/array/average [rev. #1]
            var r = {mean: 0, variance: 0, deviation: 0}, t = a.length;
            for(var m, s = 0, l = t; l--; s += a[l]);
            for(m = r.mean = s / t, l = t, s = 0; l--; s += Math.pow(a[l] - m, 2));
            return r.deviation = Math.sqrt(r.variance = s / t), r;
        };

        var compute = function(features, featureName) {
            // reduce features to id:adjacency
            var scores = [];
            $.each(features,function(index,item){
                scores.push(item.attributes[featureName]);
            });
            return average(scores);
        };

        return compute;
        
    })();

    var updatingAssigned = false;
    var updateAssignableDistricts = function() {
        if (updatingAssigned)
            return;
        updatingAssigned = true;

        var version = getPlanVersion();
        $.ajax({
            type:'GET',
            url:'../districts/',
            data: {version:version},
            success: function(data,txtStatus,xhr){
                updatingAssigned = false;
                // do nothing if this call did not succeed
                if (!data.success) {
                    if ('redirect' in data) {
                        window.location.href = data.redirect;
                    }
                    return;
                }

                var currentDist = $('#assign_district').val();

                $('#assign_district option').detach();
                $('#assign_district')
                    .append('<option value="-1">-- ' + gettext('Select One') + ' --</option>')
                    .append('<option value="0">' + gettext('Unassigned') + '</option>');

                // get the maximum version of all districts. If walking 
                // backward, it may be possible that the version you 
                // requested (let's say you requested version 3 of a plan)
                // doesn't have any districts. This will happen if a user 
                // performs many undo steps, then edits the plan. In this
                // case, the maximum version will be LESS than the version
                // requested.
                var max_version = 0;
                for (var d in data.districts) {
                    var district = data.districts[d];
                    max_version = Math.max(district.version,max_version);

                    if (district.long_label != gettext('Unassigned')) {
                        $('#assign_district')
                            .append('<option value="' + district.id + '">' + district.long_label + '</option>');
                    }
                }

                if ($('#assign_district option').length < MAX_DISTRICTS + 1) {

                    $('#assign_district')
                        .append('<option value="new">' + gettext('New ') + BODY_MEMBER_LONG + '</option>');
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

                // ensures that '-- Select One --' is selected
                $('#assign_district').val(-1);
                
                if (assignMode == 'anchor') {
                    // ONLY IF the district exists, and is in the option 
                    // list will this change the current selection in the
                    // dropdown
                    $('#assign_district').val(currentDist);

                    if ($('#assign_district').val() != currentDist) {
                        $('#anchor_tool').removeClass('toggle');
                        assignMode = null;
                    }
                }

                // set the version cursor to the max version. In situations
                // where there has been an edit on an undo, the version 
                // cursor in not continuous across all versions of the 
                // plan.
                var cursor = $('#history_cursor');
                if (version != max_version) {
                    // Purge all versions that are in the history that are
                    // missing. You can get here after editing a plan for 
                    // a while, then performing some undos, then editing 
                    // again. You will be bumped up to the latest version 
                    // of the plan, but there will be 'phantom' versions 
                    // between the undo version basis and the current 
                    // plan version.
                    while (version > max_version && version >= 0) {
                        delete PLAN_HISTORY[version--];
                    }
                }

                PLAN_HISTORY[max_version] = true;
                cursor.val(max_version);

                if (!data.canUndo) {
                    $('#history_undo').addClass('disabled');
                }
                // Update the "available districts" shown in the copy/paste dialog
                $('#copy_paste_tool').trigger('available_districts_updated', [data.available]);
            }
        });
    };

    // Connect an event to the district layer that updates the 
    // list of possible districts to assign to.
    // TODO: this doesn't account for districts with null geometries
    // which will not come back from the WFS query
    var updateLevel = getSnapLayer().geolevel;
    var updateDistrictScores = function(){
        var geolevel = getSnapLayer().geolevel;
        if (selection.features.length > 0 && 
            (geolevel != updateLevel || selection.features[0].renderIntent == 'select')) {
            updateLevel = geolevel;
            selection.removeFeatures(selection.features);

            // since we are removing features, terminate any controls that
            // may be in limbo (dragdropControl, I'm looking at you)
            if (assignMode == 'dragdrop') {
                dragdropControl.deactivate();
                dragdropControl.resumeTool.activate();
            }
        }
        
        var sorted = districtLayer.features.slice(0,districtLayer.features.length);
        sorted.sort(function(a,b){
            return a.attributes.name > b.attributes.name;
        });
        computeAvg(sorted, 'compactness');

        var working = $('#working');
        if (working.dialog('isOpen')) {
            working.dialog('close');
        }

        OpenLayers.Element.removeClass(olmap.viewPortDiv, 'olCursorWait');
    };

    // When the navigate map tool is clicked, disable all the 
    // controls except the navigation control.
    $('.navigate_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        $(document).unbind('keyup', cancelDragDrop);
        navigate.activate();
        $('.navigate_map_tool').addClass('toggle');
        $('#dragdrop_tool').removeClass('toggle');
        $('#anchor_tool').removeClass('toggle');
        assignMode = null;
        $('#assign_district').val(-1);
        tipdiv.style.display = 'none';
        districtIdDiv.style.display = 'none';
    });

    // When the identify map tool is clicked, disable all the
    // controls except the identify control.
    $('.identify_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        $(document).unbind('keyup', cancelDragDrop);
        idControl.activate();
        $('.identify_map_tool').addClass('toggle');
        $('#dragdrop_tool').removeClass('toggle');
        $('#anchor_tool').removeClass('toggle');
        assignMode = null;
        $('#assign_district').val(-1);
    });

    // When the district id map tool is clicked, disable all the
    // controls except the district id control.
    $('#district_id_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        $(document).unbind('keyup', cancelDragDrop);
        districtIdControl.activate();
        $('#dragdrop_tool').removeClass('toggle');
        $('#anchor_tool').removeClass('toggle');
        assignMode = null;
        $('#assign_district').val(-1);
    });

    // When the district unassign tool is clicked, disable all the
    // controls except the unassign tool control.
    $('#district_select_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        $(document).unbind('keyup', cancelDragDrop);
        districtSelectTool.activate();
        $('#dragdrop_tool').removeClass('toggle');
        $('#anchor_tool').removeClass('toggle');
        assignMode = null;
        $('#assign_district').val(-1);
    });

    // When the lock district map tool is clicked, disable all the
    // controls except the lock district control.
    $('#lock_district_map_tool').click(function(evt){
        var active = olmap.getControlsBy('active',true);
        for (var i = 0; i < active.length; i++) {
            if (active[i].CLASS_NAME != 'OpenLayers.Control.KeyboardDefaults') {
                active[i].deactivate();
            }
        }
        $(document).unbind('keyup', cancelDragDrop);
        lockDistrictControl.activate();
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
        $(document).unbind('keyup', cancelDragDrop);
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
        $(document).unbind('keyup', cancelDragDrop);
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
        $(document).unbind('keyup', cancelDragDrop);
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
            $(document).unbind('keyup', cancelDragDrop);
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
                $(document).bind('keyup', cancelDragDrop);

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
        $('#district_select').removeClass('toggle');
        districtSelectTool.deactivate();
        $('#lock_district_map_tool').removeClass('toggle');
        lockDistrictControl.deactivate();
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
        $('#lock_district_map_tool').removeClass('toggle');
        lockDistrictControl.deactivate();
        $('#district_select_tool').removeClass('toggle');
        districtSelectTool.deactivate();
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
        districtSelectTool,
        lockDistrictControl,
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
        var callbackSnap = function(sld) {
            var userStyle = getDefaultStyle(sld,getShowBy());

            // the legend title should match what is displayed in the thematic map dropdown
            // (which already takes care of translation). this used to be set to the title 
            // within the SLD, but that causes hard-to-solve translation issues.
            $('#legend_title').empty().append($('#showby').find(':selected').text());

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
            vislayers = olmap.getLayersBy('visibility',true);
            for (var i = 0; i < vislayers.length; i++ ) {
                if (DB.util.startsWith(vislayers[i].name, NAMESPACE)) {
                    vislayers = vislayers[i].name;
                    break;
                }
            }
            $('#map').trigger('style_changed', [userStyle, vislayers]); 
        };

        var getLockedRules = function() {
            var lockedColor = $('.locked').css('background-color');

            rules = [];
            rules.push(new OpenLayers.Rule({
                filter: new OpenLayers.Filter.Comparison({
                    type: OpenLayers.Filter.Comparison.EQUAL_TO,
                    property: 'is_locked',
                    value: true
                }),
                symbolizer: {
                    //Line: {
                        strokeColor: lockedColor,
                        strokeWidth: 2,
                        strokeOpacity: 0.75
                    //}
                }
            }));
            rules.push(new OpenLayers.Rule({
                filter: new OpenLayers.Filter.Comparison({
                    type: OpenLayers.Filter.Comparison.NOT_EQUAL_TO,
                    property: 'is_locked',
                    value: true
                })
            }));
        
            return rules;
        };

        var callbackDistrict = function(sld) {
            var userStyle = getDefaultStyle(sld,getDistrictBy().name);
            var newStyle = new OpenLayers.Style(districtStyle, {
                title: userStyle.title, 
                rules: userStyle.rules.concat(getLockedRules())
            });
            $('#map').trigger('style_changed', [newStyle, districtLayer.name]); 
         };

        var callbackContiguity = function() {
            var newOptions = OpenLayers.Util.extend({}, districtStyle);
            var fill = $('.farover').first().css('background-color');
            
            var rules = [
                new OpenLayers.Rule({
                    title: 'Non-contiguous',
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.EQUAL_TO,
                        property: 'contiguous',
                        value: false
                    }),
                    symbolizer: {
                        //Polygon: {
                            fillColor: fill,
                            fillOpacity: 0.5,
                            strokeColor: newOptions.strokeColor,
                            strokeOpacity: newOptions.strokeOpacity,
                            strokeWidth: newOptions.strokeWidth
                        //}
                    }
                }),
                new OpenLayers.Rule({
                    title: 'Contiguous',
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.NOT_EQUAL_TO,
                        property: 'contiguous',
                        value: false
                    }),
                    symbolizer: {
                        //Polygon: {
                            fillColor: '#ffffff',
                            fillOpacity: 0.01,
                            strokeColor: newOptions.strokeColor,
                            strokeOpacity: newOptions.strokeOpacity,
                            strokeWidth: newOptions.strokeWidth
                        //}
                    }
                })
            ];
            rules = rules.concat(getLockedRules());
            var newStyle = new OpenLayers.Style(newOptions,{
                title:'Contiguity',
                rules: rules
            });
            $('#map').trigger('style_changed', [newStyle, districtLayer.name]);
        };

        /** 
         * Function that handles styling of choropleths for district scores that 
         * are continuous. 
         *
         * Currently used for compactness and adjacency scores.
         *
         * @param {number} scalingConstant amount to scale standard deviation breaks for high/avg/low categories
         *     for continous distributions
         * @param {string} featureName string that is the feature name of the continous feature in the returned
         *     GEOJson from the districtLayer protocol
         */
        var callbackContinuous = function(scalingConstant, featureName) {

            var newOptions = OpenLayers.Util.extend({}, districtStyle);
            var computedAvg = computeAvg(districtLayer.features, featureName);
            var upper = computedAvg.mean + (computedAvg.deviation) * scalingConstant;  
            var lower = computedAvg.mean - (computedAvg.deviation) * scalingConstant; 
            var highestColor = $('.farover').first().css('background-color');
            var lowestColor = $('.farunder').first().css('background-color');

            var rules = [
                new OpenLayers.Rule({
                    title: 'High Numbers',
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.LESS_THAN,
                        property: featureName,
                        value: lower 
                    }),
                    symbolizer: {
                        fillColor: lowestColor,
                        fillOpacity: 0.5,
                        strokeColor: newOptions.strokeColor,
                        strokeWidth: newOptions.strokeWidth,
                        strokeOpacity: newOptions.strokeOpacity
                    }
                }),
                new OpenLayers.Rule({
                    title: 'Average',
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.BETWEEN,
                        property: featureName,
                        lowerBoundary: lower,
                        upperBoundary: upper
                    }),
                    symbolizer: {
                        fillColor: '#ffffff',
                        fillOpacity: 0.01,
                        strokeColor: newOptions.strokeColor,
                        strokeWidth: newOptions.strokeWidth,
                        strokeOpacity: newOptions.strokeOpacity
                    }
                }),
                new OpenLayers.Rule({
                    title: 'Low Numbers',
                    filter: new OpenLayers.Filter.Comparison({
                        type: OpenLayers.Filter.Comparison.GREATER_THAN,
                        property: featureName,
                        value: upper 
                    }),
                    symbolizer: {
                        fillColor: highestColor,
                        fillOpacity: 0.5,
                        strokeColor: newOptions.strokeColor,
                        strokeWidth: newOptions.strokeWidth,
                        strokeOpacity: newOptions.strokeOpacity
                    }
                })
            ];
            rules = rules.concat(getLockedRules());
            var newStyle = new OpenLayers.Style(newOptions,{
                title:'Continuous Measurement' + featureName,
                rules: rules
            });
            $('#map').trigger('style_changed', [newStyle, districtLayer.name]);
        };

        return function(snap, show) {
            if (snap == gettext('Contiguity')) {
                callbackContiguity();
                return;
            }
            if (snap == gettext('Compactness')) {
                callbackContinuous(1, 'compactness');
                return;
            }
            if (snap == gettext('Adjacency')) {
                callbackContinuous(0.5, 'adjacency');
                return;
            }
            if (snap == gettext('Convex Hull Ratio')) {
                callbackContinuous(1, 'convexhull');
                return;
            };
            if (snap == gettext('None')) {
                var newOptions = OpenLayers.Util.extend({}, districtStyle);
                var newStyle = new OpenLayers.Style(newOptions,{
                    title:'Districts',
                    rules: getLockedRules()
                });
                $('#map').trigger('style_changed', [newStyle, districtLayer.name]);
                return;
            }
            var styleUrl = '/sld/' + NAMESPACE + ':' + snap + '_' + show + '.sld';

            var isSnap = false;
            for (var i = 0; i < SNAP_LAYERS.length; i++) {
                isSnap = isSnap || (SNAP_LAYERS[i].level == snap);
            }
            
            var callback = isSnap ? callbackSnap : callbackDistrict;

            if (styleUrl in styleCache) {
                if (styleCache[styleUrl]) {
                    callback(styleCache[styleUrl]);
                    return;
                }
            } else {
                styleCache[styleUrl] = false;
            }

            $.ajax({
                url: styleUrl,
                type: 'GET',
                success: function(data,txtStatus,xhr){
                    var sld = sldFormat.read(data);
                    styleCache[styleUrl] = sld;
                    callback(sld);
                }
            });
        };
    })();

    //
    // Update the styles of the districts based on the 'Show District By'
    // dropdown in the menu.
    //
    var makeDistrictLegendRow = function(id, cls, label, noBorder) {
        var div = $('<div id="' + id + '">&nbsp;</div>');
        div.addClass('swatch');
        if (noBorder != true) {
            div.addClass('district_swatch');
        }
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

        if (distDisplay.by == 0) {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_within','target',gettext('Boundary'));

            lbody.append(row);
        }
        else if (distDisplay.by == -2) {
            lbody.empty();
            var row = makeDistrictLegendRow('district_swatch_farover','farover',gettext('Noncontiguous'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target',gettext('Contiguous'));
            lbody.append(row);
        }
        else if (distDisplay.by == -1) {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_farover','farover',gettext('Very Compact'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target',gettext('Average'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_farunder','farunder',gettext('Hardly Compact'));
            lbody.append(row);
        }
        else if (distDisplay.by == -3) {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_farover','farover',gettext('Hardly Adjacent'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target',gettext('Average Adjacency'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_farunder','farunder',gettext('Very Adjacent'));
            lbody.append(row);
        }
        else if (distDisplay.by == -4) {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_farover','farover',gettext('Above Average Ratio'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target',gettext('Average Ratio'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_farunder','farunder',gettext('Below Average Ratio'));
            lbody.append(row);
        }
        else {
            lbody.empty();

            var row = makeDistrictLegendRow('district_swatch_farover','farover',gettext('Far Over Target'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_over','over',gettext('Over Target'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_within','target',gettext('Within Target'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_under','under',gettext('Under Target'));
            lbody.append(row);
            row = makeDistrictLegendRow('district_swatch_farunder','farunder',gettext('Far Under Target'));
            lbody.append(row);
        }
    };

    // Logic for the 'Snap Map to' dropdown, note that this logic
    // calls the boundsforChange callback
    var changingSnap = false;
    var changeSnapLayer = function(evt) {
        if (changingSnap)
            return;
        changingSnap = true;

        var newOpts = getControl.protocol.options;
        var show = getShowBy();
        var snap = getSnapLayer();
        var layername = NAMESPACE + ':demo_' + snap.level + '_' + show;
        var layers = olmap.getLayersByName(layername);

        newOpts.featureType = snap.layer;
        getControl.protocol = 
            boxControl.protocol = new OpenLayers.Protocol.HTTP( newOpts );
        setThematicLayer(layers[0]);
        doMapStyling();
        $('#layer_type').text(snap.display);
        $('#currently_viewing').text(snap.display);
        getMapStyles(getSnapLayer().layer.split('simple_')[1],getShowBy());

        if (olmap.center !== null) {
            districtLayer.filter = getVersionAndSubjectFilters(olmap.getExtent());
            refreshStrategy.refresh();

            // get a new set of filters, so we don't muddy the districtLayer
            var filter = getVersionAndSubjectFilters(olmap.getExtent());
            // remove version criteria
            filter.filters = filter.filters.splice(1);

            var refLayers = olmap.getLayersByName(new RegExp('^plan\.\d*'));
            for (var i = 0; i < refLayers.length; i++) {
                refLayers[i].filter = filter;
                refLayers[i].strategies[0].update({force:true});
            }
            $('#map').trigger('draw_highlighted_districts');
        }

        geolevelRange = getMinMaxGeolevels(snap.layer);

        changingSnap = false;
    };

    // Logic for the 'Show Map by' dropdown
    $('#showby').change(function(evt){
        var snap = getSnapLayer();
        var show = evt.target.value;
        var layername = NAMESPACE + ':demo_' + snap.name + '_' + show;

        var layers = olmap.getLayersByName(layername);
        setThematicLayer(layers[0]);
        doMapStyling();
        getMapStyles(getSnapLayer().layer.split('simple_')[1],getShowBy());

        // Since keyboard defaults are on, if focus remains on this
        // dropdown after change, the keyboard may change the selection
        // inadvertently
        $('#showby').blur();
    });

    // Logic for the 'Show Districts by' dropdown
    $('#districtby').change(function(evt){
        if (evt.target.value == '-3') {
            getMapStyles(gettext('Adjacency'), '');
        }
        else if (evt.target.value == '-2') {
            getMapStyles(gettext('Contiguity'),'');
        }
        else if (evt.target.value == '-1') {
            getMapStyles(gettext('Compactness'),'');
        }
        else if (evt.target.value == '0') {
            getMapStyles(gettext('None'), '');
        }
        else if (evt.target.value == '-4') {
            getMapStyles(gettext('Convex Hull Ratio'), '');
        }
        else {
            var dby = getDistrictBy();
            var visualize = (dby.by > 0) ? LEGISLATIVE_BODY : dby.name;

            var dff = districtLayer.filter.filters;
            var sameSubj = false;
            for (var i = 0; i < dff.length && !sameSubj; i++) {
                if (dff[i].property == 'subject'&& 
                    dff[i].subject == dby.by) {
                    sameSubj = true;
                }
            }
            getMapStyles(visualize, dby.name);
        }

        // Since keyboard defaults are on, if focus remains on this
        // dropdown after change, the keyboard may change the selection
        // inadvertently
        $('#districtby').blur();
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
        districtComment.dialog('close');
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
            updateAssignableDistricts();
        }
    });

    // Logic for history redo button
    $('#history_redo').click(function(evt){
        districtComment.dialog('close');
        var cursor = $('#history_cursor');
        var ver = cursor.val();
        if (ver < PLAN_VERSION) {
            ver++;
            while (!(ver in PLAN_HISTORY) && ver <= PLAN_VERSION) {
                ver++;
            }
            if (ver == PLAN_VERSION) {
                $(this).addClass('disabled');
            }
            cursor.val(ver);

            $('#history_undo').removeClass('disabled');

            updateInfoDisplay();
            updateAssignableDistricts();
        }
    });

    // Storage for districts that are to be highlighted
    var highlightedDistricts = [];
    
    /**
     * Highlights districts -- both in district row, and on map
     */
    var drawHighlightedDistricts = function(evt, onlyUpdateRows) {
        // Unselect all rows
        $('#demographics_table tr').removeClass('selected');

        // Add selected class for each selected district
        $(highlightedDistricts).each(function(i, district_id) {
            $('.inforow_' + district_id).addClass('selected');
        });

        // Update layer
        if (!onlyUpdateRows) {
            highlightLayer.filter = getVersionAndSubjectFilters(olmap.getExtent(), null, highlightedDistricts);
            highlightLayer.strategies[0].update({force:true});
        }
    };

    /**
     * Sets all highlighted districts
     */
    var setHighlightedDistricts = function(districts) {
        highlightedDistricts = districts;
        drawHighlightedDistricts();
    };

    /**
     * Updates highlighted districts array, and then calls function to highlight them
     */
    var toggleDistrictHighlighting = function(evt, district_id) {
        var index = $.inArray(district_id, highlightedDistricts);
        if (index < 0) {
            highlightedDistricts.push(district_id);
        } else {
            highlightedDistricts.splice(index, 1);
        }
        $('#map').trigger('draw_highlighted_districts');
    };

    /**
     * Zooms to the extent of a district by district_id
     */
    var zoomToDistrictExtent = function(evt, district_id) {
        var dby = getDistrictBy();
        $.ajax({
            type:'GET',
            url: '/districtmapping/plan/' + PLAN_ID + '/district/versioned/',
            data: {
                district_ids__eq: district_id,
                version__eq: getPlanVersion(),
                level__eq: getSnapLayer().geolevel,
                subject__eq: (dby.by > 0) ? dby.by : 1
            },
            success: function(featureCollection){
                if (featureCollection) {
                    var geojson = new OpenLayers.Format.GeoJSON();
                    var features = geojson.read(featureCollection);
                    if (features && features.length > 0) {
                        var bounds = features[0].geometry.getBounds();
                        olmap.zoomToExtent(bounds);
                    }
                 }
            }
        });
    };

    // Bind to events that need refreshes
    $(this).bind('toggle_highlighting', toggleDistrictHighlighting);
    $(this).bind('zoom_to_district', zoomToDistrictExtent);
        
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
        var createDistrict = function(district_id, district_label) {
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
                url: '/districtmapping/plan/' + PLAN_ID + '/district/new/',
                data: {
                    district_id: district_id,
                    district_name: district_label,
                    geolevel: geolevel_id,
                    geounits: geounit_ids,
                    version: getPlanVersion()
                },
                success: function(data, textStatus, xhr) {
                    var mode = data.success ? 'select' : 'error';
                    for (var i = 0; i < selection.features.length; i++) { 
                        selection.drawFeature(selection.features[i], mode);
                    } 

                    if (!data.success && 'redirect' in data) {
                        window.location.href = data.redirect;
                        return;
                    }

                    var updateAssignments = true;
                    $('#map').trigger('version_changed', [data.version, updateAssignments]);


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
                dtaken = dtaken || (parseInt(options[o].value,10) == d)
            }
            if (!dtaken) {
                if (PLAN_TYPE == 'plan') {
                    var lbl = BODY_MEMBER_LONG.charAt(0).toUpperCase()+BODY_MEMBER_LONG.substring(1)+' '+d;
                    avail.push('<option value="'+d+';'+lbl+'">'+lbl+'</option>');
                }
                else {
                    avail.push(d);
                    d = MAX_DISTRICTS;
                }
            }
        }

        if (PLAN_TYPE == 'plan') {
            var i18nParams = {
                bml: BODY_MEMBER_LONG.toLowerCase()
            };
            var markup = $('<div id="newdistrictdialog" />')
                .text(printFormat(gettext('Please select a name for the %(bml)s'), i18nParams));
            markup.append($('<br/><select id="newdistrictname">' + avail.join('') + '</select>'));

            var buttons = [
                {
                    label: gettext('OK'),
                    text: gettext('OK'),
                    click: function() { 
                        var did, dname;
                        var dinfo = $('#newdistrictname').val().split(';');
                        did = dinfo[0];
                        dname = dinfo[1];
                        createDistrict(did, dname);
                        $(this).dialog("close"); 
                        $('#newdistrictdialog').remove(); 
                    }
                },{
                    label: gettext('Cancel'),
                    text: gettext('Cancel'),
                    click: function() { 
                        $(this).dialog("close"); 
                        $('#newdistrictdialog').remove(); 
                        $('#assign_district').val('-1');
                    }
                }
            ];

            // Create a dialog to get the new district's name from the user.
            // On close, destroy the dialog.
            markup.dialog({
                modal: true,
                autoOpen: true,
                title: gettext('New ')+BODY_MEMBER_LONG,
                width: 330,
                buttons: buttons
            });
        }
        else {
            var h3 = districtComment.find('h3');
            $(h3[0]).text('1. ' + gettext('Community Label') + ':');
            $(h3[1]).text('2. ' + gettext('Community Type') + ':');

            districtComment.dialog('open');
            $('#id_label').val('');
            $('#id_type').val('');
            $('#id_typelist').val([]);
            $('#id_comment').val('');
            $('#id_district_pk').val('0');
            $('#id_district_id').val(avail[0]);
            $('#assign_district').val('-1');
        }
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
        $('#demographics_table tr').data('isVisibleOnMap', false);

        for (feature in districtLayer.features) {
            var feature = districtLayer.features[feature];
            var inforow = $('.inforow_' + feature.attributes.district_id);
            if (featureOnScreen(feature, getVisibleBounds())) {
                inforow.data('isVisibleOnMap', true);
                visibleDistricts += feature.id;
            }
        }
        if (visibleDistricts != olmap.prevVisibleDistricts || force) {
            var demosorter = viewablesorter({ target: '#demographics_table tbody' }).init();
            demosorter.sortTable();
            olmap.prevVisibleDistricts = visibleDistricts;
        }

        updateDistrictStyles();
    };

    $('#map').bind('resort_by_visibility', sortByVisibility);
    $('#map').bind('draw_highlighted_districts', drawHighlightedDistricts);
   
    // triggering this event here will configure the map to correspond
    // with the initial dropdown values (jquery will set them to different
    // values than the default on a reload). A desirable side effect is
    // that the map styling and legend info will get loaded, too, so there
    // is no need to explicitly perform doMapStyling() or getMapStyles()
    // in this init method.
    changeSnapLayer();

    // Set the initial map extents to the bounds around the study area.
    olmap.zoomToExtent(STUDY_BOUNDS);
    OpenLayers.Element.addClass(olmap.viewPortDiv, 'olCursorWait');

    // set up sizing for dynamic map size that fills the pg
    initializeResizeFix();

    districtLayer.events.register('loadend', districtLayer, sortByVisibility);
    districtLayer.events.register('loadend', districtLayer, updateDistrictScores);

    olmap.events.register('movestart',olmap,function(){
        districtIdDiv.style.display = 'none';
        tipdiv.style.display = 'none';
    });
    olmap.events.register('moveend', olmap, sortByVisibility);
    
    // Add the listeners for editing whenever a base layer is changed
    // or the zoom level is changed
    olmap.events.register('changebaselayer', olmap, changeSnapLayer);
    olmap.events.register('zoomend', olmap, changeSnapLayer);

    PLAN_HISTORY[PLAN_VERSION] = true;

    $(document.body).trigger('mapready', olmap);
    var dby = getDistrictBy();
    var visualize = (dby.by > 0) ? LEGISLATIVE_BODY : dby.name;

    if (visualize == 'Compactness') {
        computeAvg(context.features, 'compactness');
    }
    if (visualize == 'Adjacency') {
        computeAvg(context.features, 'adjacency');
    }

    getMapStyles(visualize, dby.name);
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
        //this.EVENT_TYPES =
        //    OpenLayers.Control.GetFeature.prototype.EVENT_TYPES.concat(
        //    OpenLayers.Control.prototype.EVENT_TYPES
        //);

        options.handlerOptions = options.handlerOptions || {};

        OpenLayers.Control.prototype.initialize.apply(this, [options]);
        
        this.features = {};

        this.handlers = {};
        
        this.handlers.click = new OpenLayers.Handler.Click(this,
            {click: this.selectClick}, this.handlerOptions.click || {});
    },

    // This is unfortunately basically a copy-paste from the OpenLayers source code, but I couldn't
    // figure out any other way to pass the propertyNames option to the protocol.
    request: function(bounds, options) {
        options = options || {};
        var spatialFilter = new OpenLayers.Filter.Spatial({
            type: this.filterType,
            value: bounds
        });
        var minGeolevelFilter = new OpenLayers.Filter.Comparison({
            type: OpenLayers.Filter.Comparison.GREATER_THAN_OR_EQUAL_TO,
            value: geolevelRange.min,
            property: 'geolevel_id'
        });
        var maxGeolevelFilter = new OpenLayers.Filter.Comparison({
            type: OpenLayers.Filter.Comparison.LESS_THAN_OR_EQUAL_TO,
            value: geolevelRange.max,
            property: 'geolevel_id'
        });
        var filters = new OpenLayers.Filter.Logical({
            type: OpenLayers.Filter.Logical.AND,
            filters: [
                spatialFilter,
                minGeolevelFilter,
                maxGeolevelFilter
            ]
        });


        // Set the cursor to "wait" to tell the user we're working.
        OpenLayers.Element.addClass(this.map.viewPortDiv, "olCursorWait");

        var response = this.protocol.read({
            maxFeatures: options.single == true ? this.maxFeatures : undefined,
            filter: filters,
            // Limit to non-geom properties so that we don't get back a multi-megabyte response
            propertyNames: ['id', 'name', 'percentage', 'number', 'geolevel_id', 'subject_id'],
            callback: function(result) {
                if(result.success()) {
                    if(result.features.length) {
                        if(options.single == true) {
                            this.selectBestFeature(result.features,
                                bounds.getCenterLonLat(), options);
                        } else {
                            this.select(result.features);
                        }
                    } else if(options.hover) {
                        this.hoverSelect();
                    } else {
                        this.events.triggerEvent("clickout");
                        if(this.clickout) {
                            this.unselectAll();
                        }
                    }
                }
                // Reset the cursor.
                OpenLayers.Element.removeClass(this.map.viewPortDiv, "olCursorWait");
            },
            scope: this
        });
        if(options.hover == true) {
            this.hoverResponse = response;
        }
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
        // This has been changed to use the map's maxExtent rather than just performing a
        // zoomToMaxExtent, because maxExtent is broken on the OSM layer
        this.map.zoomToExtent(STUDY_BOUNDS);
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

// Modify the spherical mercator initialization function so projection
// is not hardcoded, but instead set in the layer options. This is needed,
// because otherwise 900913 is always used, when we want 3785. This causes
// a slight difference which results in the map being offset.
OpenLayers.Layer.SphericalMercator.initMercatorParameters = function() {
    this.RESOLUTIONS = [];
    var maxResolution = 156543.0339;
    for(var zoom = 0; zoom <= this.MAX_ZOOM_LEVEL; ++zoom) {
        this.RESOLUTIONS[zoom] = maxResolution / Math.pow(2, zoom);
    }
};

// Modify the OSM layer to add support for minZoomLevel
OpenLayers.Layer.XYZ = OpenLayers.Class(OpenLayers.Layer.XYZ, {     
    initialize: function(name, url, options) {
        var minZoom = 0;
        if (options.minZoomLevel) {
            minZoom = options.minZoomLevel;
        }
        if (options && options.sphericalMercator || this.sphericalMercator) {
            options = OpenLayers.Util.extend({
                maxExtent: new OpenLayers.Bounds(
                    -128 * 156543.0339,
                    -128 * 156543.0339,
                    128 * 156543.0339,
                    128 * 156543.0339
                ),
                maxResolution: 156543.0339 / Math.pow(2, minZoom),
                numZoomLevels: 19,
                units: "m",
                projection: "EPSG:3785"
            }, options);
        }
        url = url || this.url;
        name = name || this.name;
        var newArguments = [name, url, {}, options];
        OpenLayers.Layer.Grid.prototype.initialize.apply(this, newArguments);
    },
    getURL: function (bounds) {
        var res = this.map.getResolution();
        var x = Math.round((bounds.left - this.maxExtent.left) / (res * this.tileSize.w));
        var y = Math.round((this.maxExtent.top - bounds.top) / (res * this.tileSize.h));
        var z = this.map.getZoom() + this.minZoomLevel;
        var url = this.url;
        var s = '' + x + y + z;
        if (url instanceof Array) {
            url = this.selectUrl(s, url);
        }
        var path = OpenLayers.String.format(url, {'x': x, 'y': y, 'z': z});
        return path;
    }
});
OpenLayers.Layer.OSM = OpenLayers.Class(OpenLayers.Layer.XYZ, {
    name: "OpenStreetMap",
    attribution: "Data CC-By-SA by <a href='http://openstreetmap.org/'>OpenStreetMap</a>",
    sphericalMercator: true,
    url: 'http://tile.openstreetmap.org/${z}/${x}/${y}.png',
    CLASS_NAME: "OpenLayers.Layer.OSM"
});
