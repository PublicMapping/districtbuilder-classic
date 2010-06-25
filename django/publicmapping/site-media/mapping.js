function init() {
    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

    var olmap = new OpenLayers.Map('map', {
        maxExtent: new OpenLayers.Bounds( -9442153.668, 
            4636574.817, -8963245.402, 5210110.14 ),
        maxResolution: 2240.3723554687494,
        projection: 'EPSG:900913',
        units: 'm'
    });

    var layer = new OpenLayers.Layer.WMS('PublicMapping',
        'http://10.0.0.10:8080/geoserver/gwc/service/wms',
        { srs: 'EPSG:900913',
          layers: 'oh_group',
          tiles: 'true',
          tilesOrigin: olmap.maxExtent.left + ',' + olmap.maxExtent.bottom,
          format: 'image/png'
        }
    );
    olmap.addLayers([layer]);

    olmap.zoomToExtent(olmap.maxExtent);
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
