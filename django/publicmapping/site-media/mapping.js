function init() {
    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

    var olmap = new OpenLayers.Map('map', {
        resolutions: [2630.997355468753, 1315.4986777343765, 657.7493388671883, 328.87466943359414, 164.43733471679707, 82.21866735839853, 41.10933367919927, 20.554666839599633, 10.277333419799817, 5.138666709899908, 2.569333354949954, 1.284666677474977, 0.6423333387374885, 0.3211666693687443, 0.16058333468437214, 0.08029166734218607, 0.040145833671093034, 0.020072916835546517, 0.010036458417773259, 0.005018229208886629, 0.0025091146044433146, 0.0012545573022216573, 6.272786511108287E-4, 3.1363932555541433E-4, 1.5681966277770716E-4],
        maxExtent: new OpenLayers.Bounds(-9542153.668,4536574.817,-8868618.344999999,5210110.140000001),
        projection: new OpenLayers.Projection('EPSG:3785'),
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
