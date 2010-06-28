function init() {
    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

    var olmap = new OpenLayers.Map('map', {
        maxExtent: new OpenLayers.Bounds( -9622972.99062,4506926.66005,-8828643.30791,6095586.025469999 ),
        resolutions: [3102.850323085935, 1551.4251615429675, 775.7125807714838, 387.8562903857419, 193.92814519287094, 96.96407259643547, 48.482036298217736, 24.241018149108868, 12.120509074554434, 6.060254537277217, 3.0301272686386085, 1.5150636343193042, 0.7575318171596521, 0.37876590857982606, 0.18938295428991303, 0.09469147714495652, 0.04734573857247826, 0.02367286928623913, 0.011836434643119564, 0.005918217321559782, 0.002959108660779891, 0.0014795543303899455, 7.397771651949728E-4, 3.698885825974864E-4, 1.849442912987432E-4],
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
