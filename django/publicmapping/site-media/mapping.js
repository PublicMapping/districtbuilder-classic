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

function getSnapLayer() {
    return $('#snapto').val();
}

function getShowBy() {
    return $('#showby').val();
}

function getBoundLayer() {
    return $('#boundfor').val();
}

/* USING CSS METHODS INSTEAD
 * Resize the map. This is a fix for IE, which does not assign a height
 * to the map div if it is not explicitly set.
 */
/* function resizemap() {
    var mapElem = document.getElementById('mapandmenu');
    if(!window.innerHeight) {
        mapElem.style.height = (window.document.body.clientHeight - 76) + 'px';
    }
    else {
        mapElem.style.height = (window.innerHeight - 79) + 'px';
    }
} */

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

    var navigate = new OpenLayers.Control.Navigation({
        autoActivate: true,
        handleRightClicks: true
    });

    // Create a slippy map.
    var olmap = new OpenLayers.Map('map', {
        // The resolutions here must match the settings in geowebcache.
        // TODO Fetch these resolutions from geowebcache
        resolutions: [2240.375, 1120.1875, 560.09375,
            280.046875, 140.0234375, 70.01171875,
            35.005859375, 17.5029296875, 8.75146484375,
            4.375732421875, 2.1878662109375, 1.09393310546875,
            0.546966552734375, 0.2734832763671875, 0.13674163818359375
        ],
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

    var match = window.location.href.match(new RegExp('/plan\/(\\d+)\/edit/'));
    var plan_id = match[1];
    var districtStrategy = new OpenLayers.Strategy.Fixed({preload:true});
    
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
            styleMap: new OpenLayers.StyleMap({
                fill: false,
                strokeColor: '#ee9900',
                strokeOpacity: 1,
                strokeWidth: 2
            }),
            projection:projection,
            filter: new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'plan_id',
                value: plan_id
            })
        }
    );

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
            )
        })
    });

    layers.push(districtLayer);
    layers.push(selection);
    olmap.addLayers(layers);

    var getProtocol = new OpenLayers.Protocol.WFS({
        url: 'http://' + MAP_SERVER + '/geoserver/wfs',
        featureType: getSnapLayer(),
        featureNS: 'http://gmu.azavea.com/',
        featurePrefix: 'gmu',
        srsName: 'EPSG:3785',
        geometryName: 'geom'
    });

    var getControl = new OpenLayers.Control.GetFeature({
        autoActivate: false,
        protocol: getProtocol,
        multipleKey: 'shiftKey'
    });

    var boxControl = new OpenLayers.Control.GetFeature({
        autoActivate: false,
        protocol: getProtocol,
        box: true
    });

    var polyControl = new OpenLayers.Control.DrawFeature( 
        selection,
        OpenLayers.Handler.Polygon,
        {
            featureAdded: function(feature){
                getProtocol.read({
                    filter: new OpenLayers.Filter.Spatial({
                        type: OpenLayers.Filter.Spatial.INTERSECTS,
                        value: feature.geometry,
                        projection: getProtocol.options.srsName
                    }),
                    callback: function(rsp){
                        selection.removeFeatures(selection.features);
                        selection.addFeatures(rsp.features);
                    }
                });
            }
        }
    );


    var featureSelected = function(e){
        selection.addFeatures([e.feature]);
    };
    getControl.events.register('featureselected', this, featureSelected);
    boxControl.events.register('featureselected', this, featureSelected);

    var featureUnselected = function(e){
        selection.removeFeatures([e.feature]);
    };
    getControl.events.register('featureunselected', this, featureUnselected);
    boxControl.events.register('featureunselected', this, featureUnselected);

    districtLayer.events.register('loadstart',districtLayer,function(){
        OpenLayers.Element.addClass(olmap.viewPortDiv, 'olCursorWait');
    });
    districtLayer.events.register('loadend',districtLayer,function(){
        OpenLayers.Element.removeClass(olmap.viewPortDiv, 'olCursorWait');
        selection.removeFeatures(selection.features);
    });

    var jsonParser = new OpenLayers.Format.JSON();

    $('#navigate_map_tool').click(function(evt){
        navigate.activate();
        getControl.deactivate();
        boxControl.deactivate();
        polyControl.deactivate();
        selection.removeFeatures(selection.features);
    });

    $('#single_drawing_tool').click(function(evt){
        getControl.activate();
        boxControl.deactivate();
        navigate.deactivate();
        polyControl.deactivate();
        selection.removeFeatures(selection.features);
    });

    $('#rectangle_drawing_tool').click(function(evt){
        boxControl.activate();
        getControl.deactivate();
        navigate.deactivate();
        polyControl.deactivate();
        selection.removeFeatures(selection.features);
    });

    $('#polygon_drawing_tool').click(function(evt){
        boxControl.deactivate();
        getControl.deactivate();
        navigate.deactivate();
        polyControl.activate();
        selection.removeFeatures(selection.features);
    });

/*
    assignControl.events.register('geounitadded', this, fu
    getControl.deactivate();
    getControl.deactivate();
    getControl.deactivate();
    getControl.deactivate();n
    getControl.deactivate();
    getControl.deactivate();c
    getControl.deactivate();tion(e){
        var district_id = e.district;
        var feature = e.selection[0];
        OpenLayers.Element.addClass(olmap.viewPortDiv,'olCursorWait');
        OpenLayers.Request.POST({
            method: 'POST',
            url: '/districtmapping/plan/' + plan_id + '/district/' + district_id + '/add',
            params: {
                geolevel: feature.attributes.geolevel_id,
                geounits: feature.attributes.id
            },
            success: function(xhr) {
                var data = jsonParser.read(xhr.responseText);
                if (data.success) {
                    districtStrategy.load();
                }
                selection.drawFeature(selection.features[0], 'select');
            },
            failure: function(xhr) {
                assignControl.reset();
            }
        });
    });
*/
    olmap.addControls([
        getControl,
        boxControl,
        polyControl
    ]);

    $('#snapto').change(function(evt){
        var newOpts = getControl.protocol.options;
        newOpts.featureType = getSnapLayer();
        getControl.protocol = new OpenLayers.Protocol.WFS( newOpts );
    });

    $('#showby').change(function(evt){
        var boundary = getBoundLayer();
        var layers = olmap.getLayersByName('gmu:demo_' + boundary + '_' + evt.target.value);
        olmap.setBaseLayer(layers[0]);
    });

    $('#boundfor').change(function(evt){
        var show = getShowBy();
        var layers = olmap.getLayersByName('gmu:demo_' + evt.target.value + '_' + show);
        olmap.setBaseLayer(layers[0]);
    });

    // Set the initial map extents to the bounds around the study area.
    // TODO Make these configurable.
    olmap.zoomToExtent(new OpenLayers.Bounds(-9467000,4570000,-8930000,5170000));
    OpenLayers.Element.addClass(olmap.viewPortDiv, 'olCursorWait');
}
