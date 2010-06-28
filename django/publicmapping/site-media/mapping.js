function init() {
    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

    var olmap = new OpenLayers.Map('map', {
        maxExtent: new OpenLayers.Bounds(
            -9442153.668,4636574.817,-8868618.344999999,5210110.140000001),
        resolutions: [2240.372355468753, 1120.1861777343765, 560.0930888671883, 280.04654443359414, 140.02327221679707, 70.01163610839853, 35.00581805419927, 17.502909027099633, 8.751454513549817, 4.375727256774908, 2.187863628387454, 1.093931814193727, 0.5469659070968635, 0.2734829535484318, 0.1367414767742159, 0.06837073838710794, 0.03418536919355397, 0.017092684596776986, 0.008546342298388493, 0.0042731711491942465, 0.0021365855745971232, 0.0010682927872985616, 5.341463936492808E-4, 2.670731968246404E-4, 1.335365984123202E-4],
        projection: 'EPSG:3785',
        units: 'm'
    });

    var layer = new OpenLayers.Layer.WMS('PublicMapping',
        'http://' + MAP_SERVER + '/geoserver/gwc/service/wms',
        { srs: 'EPSG:3785',
          layers: 'oh_group',
          tiles: 'true',
          tilesOrigin: olmap.maxExtent.left + ',' + olmap.maxExtent.bottom,
          format: 'image/png'
        },
        {
            buffer: 1,
            displayOutsideMaxExtent: true
        }
    );
    olmap.addLayers([layer]);

    olmap.zoomToExtent(new OpenLayers.Bounds(-9438350,4627300,-8962000,5165600));
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
