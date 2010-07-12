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
 * Resize the map. This is a fix for IE, which does not assign a height
 * to the map div if it is not explicitly set.
 */
function resizemap() {
    var mapElem = document.getElementById('mapandmenu');
    if(!window.innerHeight) {
        mapElem.style.height = (window.document.body.clientHeight - 76) + 'px';
    }
    else {
        mapElem.style.height = (window.innerHeight - 79) + 'px';
    }
}

/*
 * Initialize the map. This method is called by the onload page event.
 */
function init() {
    OpenLayers.ProxyHost= "/proxy?url=";

    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

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

    // Create a slippy map.
    var olmap = new OpenLayers.Map('map', {
        // The resolutions here must match the settings in geowebcache.
        // TODO Fetch these resolutions from geowebcache
        resolutions: [2240.375, 1120.1875, 560.09375,
            280.046875, 140.0234375, 70.01171875,
            35.005859375, 17.5029296875, 8.75146484375,
            4.375732421875, 2.1878662109375, 1.09393310546875,
            0.546966552734375, 0.2734832763671875, 0.13674163818359375,
            0.06837081909179688, 0.03418540954589844,
            0.01709270477294922, 0.00854635238647461, 0.004273176193237305,
            0.0021365880966186523, 0.0010682940483093262,
            5.341470241546631E-4, 2.6707351207733154E-4, 1.3353675603866577E-4],
        maxExtent: layerExtent,
        projection: projection,
        units: 'm'
    });

    // These layers are dependent on the layers available in geowebcache
    // TODO Fetch a list of layers from geowebcache
    var layers = [];
    for (layer in MAP_LAYERS) {
        layers.push(createLayer( MAP_LAYERS[layer], MAP_LAYERS[layer], layerExtent ));
    }

    var match = window.location.href.match(new RegExp('/plan\/(\\d+)\/edit/'));
    var plan_id = match[1];
    
    var districtLayer = new OpenLayers.Layer.Vector(
        'Current Plan',
        {
            strategies: [
                new OpenLayers.Strategy.BBOX(),
                new OpenLayers.Strategy.Refresh()
            ],
            protocol: new OpenLayers.Protocol.WFS({
                url: 'http://' + MAP_SERVER + '/geoserver/wfs',
                featureType: 'district',
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
/*
    var districtLayer = new OpenLayers.Layer.WMS(
        'Current Plan',
        'http://' + MAP_SERVER + '/geoserver/wms',
        { srs: 'EPSG:3785',
          layers: 'gmu:gmu_plan',
          format: 'image/png',
          cql_Filter: 'plan_id=1'  
        },
        {
            singleTile: true,
            buffer: 0,
            projection: projection,
            isBaseLayer: false,
            opacity: 0.5
        }
    );
*/

    var selection = new OpenLayers.Layer.Vector('Selection');

    layers.push(districtLayer);
    layers.push(selection);
    olmap.addLayers(layers);

    var getControl = new OpenLayers.Control.GetFeature({
        protocol: new OpenLayers.Protocol.WFS({
            url: 'http://' + MAP_SERVER + '/geoserver/wfs',
            featureType: 'county',
            featureNS: 'http://gmu.azavea.com/',
            featurePrefix: 'gmu',
            srsName: 'EPSG:3785',
            geometryName: 'geom'
        })
    });

    getControl.events.register('featureselected', this, function(e){
        selection.addFeatures([e.feature]);
    });
    getControl.events.register('featureunselected', this, function(e){
        selection.removeFeatures([e.feature]);
    });

    olmap.events.register('changelayer', getControl, function(e){
        if ( e.layer.isBaseLayer && e.layer[e.property]) {
            var newOpts = getControl.protocol.options;
            newOpts.featureType = e.layer.name.substring( getControl.protocol.featurePrefix.length + 1 );
            getControl.protocol = new OpenLayers.Protocol.WFS( newOpts );
        }
    });

    olmap.addControls([
        new OpenLayers.Control.LayerSwitcher(),
        getControl
    ]);

    getControl.activate();

    // Set the initial map extents to the bounds around the study area.
    // TODO Make these configurable.
    olmap.zoomToExtent(new OpenLayers.Bounds(-9467000,4570000,-8930000,5170000));
}
