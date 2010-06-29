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

function init() {
    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

    var layerExtent = new OpenLayers.Bounds(-9928290.0,4104345.0,-8278222.0,5754413.0);

    var olmap = new OpenLayers.Map('map', {
	resolutions: [6445.578125, 3222.7890625, 1611.39453125, 805.697265625, 402.8486328125, 201.42431640625, 100.712158203125, 50.3560791015625, 25.17803955078125, 12.589019775390625, 6.2945098876953125, 3.1472549438476562, 1.5736274719238281, 0.7868137359619141, 0.39340686798095703, 0.19670343399047852, 0.09835171699523926, 0.04917585849761963, 0.024587929248809814, 0.012293964624404907, 0.006146982312202454, 0.003073491156101227, 0.0015367455780506134, 7.683727890253067E-4, 3.8418639451265335E-4],

        maxExtent: layerExtent,
        projection: new OpenLayers.Projection('EPSG:3785'),
        units: 'm'
    });

    var layers = [
        createLayer( 'Counties & Districts', 'gmu_district_county', 
            layerExtent ),
        createLayer( 'Counties', 'gmu:census_county',
            layerExtent ),
        createLayer( 'Census Tracts & Districts', 'gmu_district_tract', 
            layerExtent ),
        createLayer( 'Census Tracts', 'gmu:census_tract', 
            layerExtent ),
        createLayer( 'Districts', 'gmu:gmu_districts_demo',
            layerExtent ) 
    ];

    olmap.addLayers(layers);
    olmap.addControls([new OpenLayers.Control.LayerSwitcher()]);
    olmap.zoomToExtent(new OpenLayers.Bounds(-9467000,4570000,-8930000,5170000));
}

function resizemap() {
    var mapElem = document.getElementById('mapandmenu');
    if(!window.innerHeight) {
        mapElem.style.height = (window.document.body.clientHeight - 76) + 'px';
    }
    else {
        mapElem.style.height = (window.innerHeight - 79) + 'px';
    }
}
