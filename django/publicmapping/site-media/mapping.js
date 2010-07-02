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
        -9928290.0,
        4104345.0,
        -8278222.0,
        5754413.0
    );

    // This projection is web mercator
    var projection = new OpenLayers.Projection('EPSG:3785');

    // Create a slippy map.
    var olmap = new OpenLayers.Map('map', {
        // The resolutions here must match the settings in geowebcache.
        // TODO Fetch these resolutions from geowebcache
	resolutions: [
            6445.578125, 3222.7890625, 1611.39453125, 
            805.697265625, 402.8486328125, 201.42431640625, 
            100.712158203125, 50.3560791015625, 25.17803955078125, 
            12.589019775390625, 6.2945098876953125, 3.1472549438476562, 
            1.5736274719238281, 0.7868137359619141, 0.39340686798095703, 
            0.19670343399047852, 0.09835171699523926, 0.04917585849761963, 
            0.024587929248809814, 0.012293964624404907, 0.006146982312202454, 
            0.003073491156101227, 0.0015367455780506134, 7.683727890253067E-4, 
            3.8418639451265335E-4],
        maxExtent: layerExtent,
        projection: projection,
        units: 'm'
    });

    // These layers are dependent on the layers available in geowebcache
    // TODO Fetch a list of layers from geowebcache
    var countyLayer = createLayer( 'Counties', 'gmu_basemap_county',
            layerExtent );
    var tractLayer = createLayer( 'Census Tracts', 'gmu_basemap_tract', 
            layerExtent );
    var blockLayer = createLayer( 'Census Blocks', 'gmu_basemap_block',
            layerExtent );
    
    var districtLayer = new OpenLayers.Layer.Vector(
        'Current Plan',
        {
            strategies: [
                new OpenLayers.Strategy.BBOX(),
                new OpenLayers.Strategy.Refresh()
            ],
            protocol: new OpenLayers.Protocol.WFS({
                url: 'http://' + MAP_SERVER + '/geoserver/wfs',
                featureType: 'gmu_plan',
                featureNS: 'http://gmu.azavea.com/',
                geometryName: 'geom'
            }),
            styleMap: new OpenLayers.StyleMap({
                fill: false,
                strokeColor: '#ee9900',
                strokeOpacity: 1,
                strokeWidth: 2
            }),
            projection:projection 
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

    olmap.addLayers([selection, districtLayer, countyLayer, tractLayer, blockLayer]);

    var getControl = new OpenLayers.Control.GetFeature({
        protocol: new OpenLayers.Protocol.WFS({
            url: 'http://' + MAP_SERVER + '/geoserver/wfs',
            featureType: 'gmu_county',
            featureNS: 'http://gmu.azavea.com/',
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

    olmap.addControls([
        new OpenLayers.Control.LayerSwitcher(),
        //new OpenLayers.Control.SelectFeature(districtLayer),
        getControl
    ]);

    getControl.activate();

    // Set the initial map extents to the bounds around the study area.
    // TODO Make these configurable.
    olmap.zoomToExtent(new OpenLayers.Bounds(-9467000,4570000,-8930000,5170000));
}
