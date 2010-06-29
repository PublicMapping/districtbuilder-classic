function createLayer( name, layer, extents ) {
    return new OpenLayers.Layer.WMS( name,
        'http://' + MAP_SERVER + '/geoserver/gwc/service/wms',
        { srs: 'EPSG:3785',
          layers: layer,
          tiles: 'true',
          tilesOrigin: extents.left + ',' + extents.bottom,
          format: 'image/png'
        }
    );
}

function init() {
    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

    var olmap = new OpenLayers.Map('map', {
        resolutions: [2240.372355468753, 1120.1861777343765, 560.0930888671883, 280.04654443359414, 140.02327221679707, 70.01163610839853, 35.00581805419927, 17.502909027099633, 8.751454513549817, 4.375727256774908, 2.187863628387454, 1.093931814193727, 0.5469659070968635, 0.2734829535484318, 0.1367414767742159, 0.06837073838710794, 0.03418536919355397, 0.017092684596776986, 0.008546342298388493, 0.0042731711491942465, 0.0021365855745971232, 0.0010682927872985616, 5.341463936492808E-4, 2.670731968246404E-4, 1.335365984123202E-4],
        maxExtent: new OpenLayers.Bounds(-9442153.668,4636574.817,-8868618.344999999,5210110.140000001),
        projection: new OpenLayers.Projection('EPSG:3785'),
        units: 'm'
    });

    var layers = [
        createLayer( 'Counties & Districts', 'gmu_district_county', 
            olmap.maxExtent ),
        createLayer( 'Counties', 'gmu:census_county',
            olmap.maxExtent ),
        createLayer( 'Census Tracts & Districts', 'gmu_district_tract', 
            olmap.maxExtent ),
        createLayer( 'Census Tracts', 'gmu:census_tract', 
            olmap.maxExtent ),
        createLayer( 'Districts', 'gmu:gmu_districts_demo',
            olmap.maxExtent ) 
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
